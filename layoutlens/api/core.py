"""
Simple LayoutLens API for natural language UI testing.

This is the main entry point for the new simplified API that focuses on
real-world developer workflows and live website testing.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# Import LiteLLM directly
try:
    import litellm
    from litellm import acompletion
except ImportError as e:
    raise ImportError("litellm is required. Install with: pip install litellm") from e

# Import caching
from ..cache import create_cache

# Import vision components
from ..capture import Capture

# Import custom exceptions
from ..exceptions import (
    AnalysisError,
    AuthenticationError,
    LayoutFileNotFoundError,
    LayoutLensError,
    ScreenshotError,
    ValidationError,
    wrap_exception,
)

# Import logging
from ..logger import get_logger, log_function_call, log_performance_metric

# Import enhanced prompt system
from ..prompts import Instructions, get_expert


@dataclass(slots=True)
class AnalysisResult:
    """Result from analyzing a single URL or screenshot."""

    source: str
    query: str
    answer: str
    confidence: float
    reasoning: str
    screenshot_path: str | None = None
    viewport: str = "desktop"
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    execution_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Export result to JSON string."""
        import json
        from dataclasses import asdict

        return json.dumps(asdict(self), indent=2, default=str)


@dataclass(slots=True)
class ComparisonResult:
    """Result from comparing multiple sources."""

    sources: list[str]
    query: str
    answer: str
    confidence: float
    reasoning: str
    individual_analyses: list[AnalysisResult] = field(default_factory=list)
    screenshot_paths: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    execution_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Export result to JSON string."""
        import json
        from dataclasses import asdict

        return json.dumps(asdict(self), indent=2, default=str)


@dataclass(slots=True)
class BatchResult:
    """Result from batch analysis."""

    results: list[AnalysisResult]
    total_queries: int
    successful_queries: int
    average_confidence: float
    total_execution_time: float
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))

    def to_json(self) -> str:
        """Export result to JSON string."""
        import json
        from dataclasses import asdict

        return json.dumps(asdict(self), indent=2, default=str)


class LayoutLens:
    """
    Simple API for AI-powered UI testing with natural language.

    This class provides an intuitive interface for analyzing websites and
    screenshots using natural language queries, designed for developer
    workflows and CI/CD integration.

    Examples
    --------
    >>> lens = LayoutLens(api_key="sk-...")
    >>> result = lens.analyze("https://example.com", "Is the navigation clearly visible?")
    >>> print(result.answer)

    >>> # Compare two designs
    >>> result = lens.compare(
    ...     ["before.png", "after.png"],
    ...     "Are these layouts consistent?"
    ... )
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        provider: str = "openai",
        output_dir: str = "layoutlens_output",
        cache_enabled: bool = True,
        cache_type: str = "memory",
        cache_ttl: int = 3600,
    ):
        """Initialize LayoutLens with AI provider credentials.

        Args:
            api_key: API key for the provider. If not provided, will try OPENAI_API_KEY
                environment variable.
            model: Model to use for analysis (LiteLLM naming: "gpt-4o", "anthropic/claude-3-5-sonnet", "google/gemini-1.5-pro").
            provider: AI provider to use ("openai", "anthropic", "google", "gemini", "litellm").
            output_dir: Directory for storing screenshots and results.
            cache_enabled: Whether to enable result caching for performance.
            cache_type: Type of cache backend: "memory" or "file".
            cache_ttl: Cache time-to-live in seconds (1 hour default).

        Raises:
            AuthenticationError: If no valid API key is found.
            ConfigurationError: If invalid provider or configuration is specified.
        """
        # Initialize logger
        self.logger = get_logger("api.core")

        log_function_call(
            "LayoutLens.__init__",
            model=model,
            provider=provider,
            output_dir=output_dir,
            cache_enabled=cache_enabled,
            cache_type=cache_type,
            cache_ttl=cache_ttl,
        )

        # Determine API key based on provider
        self.api_key = api_key or self._get_api_key_for_provider(provider)
        if not self.api_key:
            self.logger.error(f"No API key found for {provider} provider")
            raise AuthenticationError(
                f"API key required for {provider} provider. Set OPENAI_API_KEY env var or pass api_key parameter."
            )

        self.model = model
        self.provider = provider
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        self.logger.info(f"Initialized LayoutLens with {provider} provider using {model} model")
        self.logger.debug(f"Output directory: {self.output_dir}")

        # Initialize components (no provider needed)
        try:
            self.capture = Capture(output_dir=str(self.output_dir / "screenshots"))

            self.logger.debug("Initialized capture and vision components")
        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            raise

        # Initialize cache
        cache_dir = str(self.output_dir / "cache") if cache_type == "file" else "cache"
        try:
            self.cache = create_cache(
                cache_type=cache_type,
                cache_dir=cache_dir,
                default_ttl=cache_ttl,
                enabled=cache_enabled,
            )
            self.logger.info(f"Initialized {cache_type} cache (enabled: {cache_enabled})")
        except Exception as e:
            self.logger.error(f"Failed to initialize cache: {e}")
            raise

    def _get_api_key_for_provider(self, provider: str) -> str | None:
        """Get appropriate API key based on provider."""
        return os.getenv("OPENAI_API_KEY")

    def _encode_image(self, image_path: str | Path) -> str:
        """Encode image to base64."""
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def _format_query_prompt(
        self, query: str, context: dict[str, Any] | None = None, instructions: Instructions | None = None
    ) -> str:
        """Format the query into a proper prompt using enhanced instruction system."""
        # Use enhanced prompt system if instructions provided
        if instructions and instructions.expert_persona:
            expert = get_expert(instructions.expert_persona)
            if expert:
                system_prompt, user_prompt = expert.analyze(query, instructions)
                # Combine system and user prompts for the current API
                return f"{system_prompt}\n\nUSER QUERY: {user_prompt}"

        # Fallback to original prompt format for backward compatibility
        prompt = f"""
Analyze this UI screenshot and answer the following question:

Question: {query}

Please provide:
1. A direct answer to the question
2. Your confidence level (0.0 to 1.0)
3. Detailed reasoning for your assessment

Focus on:
- Visual layout and design elements
- User experience and usability
- Accessibility considerations
- Overall quality and professionalism
"""

        # Add context from either instructions or legacy context dict
        if instructions:
            if instructions.focus_areas:
                prompt += f"\n\nFocus areas: {', '.join(instructions.focus_areas)}"
            if instructions.evaluation_criteria:
                prompt += f"\n\nEvaluation criteria: {instructions.evaluation_criteria}"
            if instructions.user_context:
                context_str = instructions.user_context.to_prompt_text()
                if context_str:
                    prompt += f"\n\nUser context: {context_str}"
        elif context:
            context_str = ", ".join(f"{k}: {v}" for k, v in context.items())
            prompt += f"\n\nAdditional context: {context_str}"

        prompt += "\n\nRespond in this JSON format:\n"
        prompt += '{"answer": "your answer", "confidence": 0.0-1.0, "reasoning": "detailed explanation"}'

        return prompt

    def _parse_structured_response(self, content: str) -> tuple[str, float, str]:
        """Parse structured response and return answer, confidence, and reasoning."""
        # Try to extract JSON from response first
        json_match = re.search(r'\{[^{}]*"answer"[^{}]*\}', content)

        if json_match:
            try:
                parsed = json.loads(json_match.group())
                return (
                    parsed.get("answer", content),
                    float(parsed.get("confidence", 0.5)),
                    parsed.get("reasoning", "Analysis completed"),
                )
            except (json.JSONDecodeError, ValueError):
                pass

        # Fallback: parse confidence from text patterns
        confidence = 0.5
        confidence_patterns = [
            r"confidence[:\s]+(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)(?:\s*(?:%|percent))?[^\w]*confident",
            r"certainty[:\s]+(\d+(?:\.\d+)?)",
        ]

        for pattern in confidence_patterns:
            match = re.search(pattern, content.lower())
            if match:
                try:
                    confidence = float(match.group(1))
                    if confidence > 1.0:
                        confidence = confidence / 100.0
                    break
                except (ValueError, IndexError):
                    continue

        # Extract answer and reasoning (simplified)
        answer = content.strip()[:200] if len(content) > 200 else content.strip()
        reasoning = content.strip()

        return answer, confidence, reasoning

    async def _call_vision_api(
        self,
        image_path: str,
        query: str,
        context: dict[str, Any] | None = None,
        instructions: Instructions | None = None,
    ) -> dict[str, Any]:
        """Call LiteLLM vision API directly."""
        # Encode image
        try:
            image_b64 = self._encode_image(image_path)
            self.logger.debug(f"Image encoded successfully: {len(image_b64)} characters")
        except Exception as e:
            self.logger.error(f"Image encoding failed: {e}")
            return {
                "answer": f"Error during analysis: Image encoding failed: {e}",
                "confidence": 0.0,
                "reasoning": f"Analysis failed: Image encoding failed: {e}",
                "metadata": {"error": str(e), "error_type": "encoding_error"},
            }

        # Build prompt
        prompt = self._format_query_prompt(query, context, instructions)

        try:
            self.logger.debug(f"Making API call with LiteLLM to model: {self.model}")

            response = await acompletion(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                        ],
                    }
                ],
                max_tokens=1000,
                temperature=0.1,
                api_key=self.api_key,
                timeout=30.0,
            )

            self.logger.debug(f"API call successful")

            # Extract content
            content = response.choices[0].message.content or ""
            tokens_used = (
                getattr(response.usage, "total_tokens", 0) if hasattr(response, "usage") and response.usage else 0
            )

            # Parse structured response
            answer, confidence, reasoning = self._parse_structured_response(content)

            self.logger.debug(f"Parsed response - confidence: {confidence:.2f}")

            return {
                "answer": answer,
                "confidence": confidence,
                "reasoning": reasoning,
                "metadata": {
                    "raw_response": content,
                    "tokens_used": tokens_used,
                    "model_used": self.model,
                    "provider": "litellm",
                },
            }

        except Exception as e:
            self.logger.error(f"LiteLLM API call failed: {e}")
            return {
                "answer": f"Error during analysis: API call failed: {e}",
                "confidence": 0.0,
                "reasoning": f"Analysis failed: API call failed: {e}",
                "metadata": {"error": str(e), "error_type": "api_error"},
            }

    async def analyze(
        self,
        source: str | Path | list[str | Path],
        query: str | list[str],
        viewport: str = "desktop",
        context: dict[str, Any] | None = None,
        instructions: Instructions | None = None,
        max_concurrent: int = 5,
    ) -> AnalysisResult | BatchResult:
        """Smart analyze method that handles single or multiple sources and queries.

        Args:
            source: Single URL/path or list of URLs/paths to analyze.
            query: Single question or list of questions about the UI.
            viewport: Viewport size for URL capture ("desktop", "mobile", "tablet").
            context: Additional context for analysis (user_type, browser, etc.). Legacy format.
            instructions: Rich instruction set with expert personas and structured context.
                         Takes precedence over context if both provided.
            max_concurrent: Maximum concurrent operations for batch analysis.

        Returns:
            AnalysisResult for single source+query, BatchResult for multiple.

        Examples:
            # Single analysis
            >>> result = await lens.analyze("https://github.com", "Is it accessible?")

            # Multiple queries on one source
            >>> result = await lens.analyze("https://github.com", ["Is it accessible?", "Mobile-friendly?"])

            # Multiple sources, one query
            >>> result = await lens.analyze(["page1.html", "page2.html"], "Is it good?")

            # Multiple sources and queries
            >>> result = await lens.analyze(["page1.html", "page2.html"], ["Accessible?", "Mobile?"])
        """
        # Normalize inputs to lists
        sources = [source] if not isinstance(source, list) else source
        queries = [query] if not isinstance(query, list) else query

        # Determine if we should return single result or batch result
        is_single_result = len(sources) == 1 and len(queries) == 1

        start_time = time.time()

        log_function_call(
            "LayoutLens.analyze",
            source_count=len(sources),
            query_count=len(queries),
            total_combinations=len(sources) * len(queries),
            viewport=viewport,
            is_single_result=is_single_result,
        )

        # Input validation for all queries
        for q in queries:
            if not q or not q.strip():
                self.logger.error(f"Empty query provided: '{q}'")
                raise ValidationError("Query cannot be empty", field="query", value=q)

        # Use unified batch processing logic for all cases
        # Create semaphore to limit concurrent operations
        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_single_combination(source: str | Path, query: str) -> AnalysisResult:
            """Analyze single source+query combination with concurrency control."""
            async with semaphore:
                combination_start_time = time.time()

                # Check cache first
                cache_key = self.cache.get_analysis_key(
                    source=str(source), query=query, viewport=viewport, context=context
                )
                cached_result = self.cache.get(cache_key)
                if cached_result and isinstance(cached_result, AnalysisResult):
                    cached_result.execution_time = time.time() - combination_start_time
                    cached_result.metadata["cache_hit"] = True
                    self.logger.info(f"Cache hit for {str(source)[:50]}... - confidence: {cached_result.confidence}")
                    return cached_result

                try:
                    # Determine if source is URL, HTML file, or image file
                    if self._is_url(source):
                        self.logger.debug(f"Capturing screenshot from URL: {source}")
                        screenshot_paths = await self.capture.screenshots([str(source)], viewport)
                        screenshot_path = screenshot_paths[0]
                        self.logger.info(f"Successfully captured screenshot: {screenshot_path}")
                    elif self._is_html_file(source):
                        self.logger.debug(f"Capturing screenshot from HTML file: {source}")
                        screenshot_path = await self.capture_only(source, viewport=viewport)
                        self.logger.info(f"Successfully captured HTML file screenshot: {screenshot_path}")
                    else:
                        # Use existing image file
                        screenshot_path = str(source)
                        if not Path(screenshot_path).exists():
                            self.logger.error(f"Screenshot file not found: {screenshot_path}")
                            raise LayoutFileNotFoundError(
                                f"Screenshot file not found: {screenshot_path}",
                                file_path=screenshot_path,
                            )
                        self.logger.debug(f"Using existing screenshot: {screenshot_path}")

                    # Analyze with direct API call

                    self.logger.debug(f"Starting vision analysis for query: {query[:50]}...")
                    vision_response = await self._call_vision_api(
                        image_path=screenshot_path,
                        query=query,
                        context=context,
                        instructions=instructions,
                    )
                    self.logger.debug(f"Vision analysis completed with confidence: {vision_response['confidence']}")

                    combination_execution_time = time.time() - combination_start_time

                    result = AnalysisResult(
                        source=str(source),
                        query=query,
                        answer=str(vision_response["answer"]),
                        confidence=float(vision_response["confidence"]),
                        reasoning=str(vision_response["reasoning"]),
                        screenshot_path=screenshot_path,
                        viewport=viewport,
                        execution_time=combination_execution_time,
                        metadata={
                            **vision_response["metadata"],
                            "cache_hit": False,
                            "provider": self.provider,
                            "model": self.model,
                            "pipeline_mode": "unified",
                        },
                    )

                    # Cache the result
                    self.cache.set(cache_key, result)
                    return result

                except Exception as e:
                    if isinstance(e, LayoutLensError):
                        raise
                    self.logger.warning(f"Analysis failed for {source} + query '{query[:50]}...': {e}")
                    return AnalysisResult(
                        source=str(source),
                        query=query,
                        answer=f"Error analyzing {source}: {str(e)}",
                        confidence=0.0,
                        reasoning=f"Analysis failed due to: {str(e)}",
                        execution_time=time.time() - combination_start_time,
                        metadata={
                            "error": str(e),
                            "error_type": type(e).__name__,
                        },
                    )

        # Create tasks for all source/query combinations
        tasks = []
        for source in sources:
            for query in queries:
                task = analyze_single_combination(source, query)
                tasks.append(task)

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and handle any remaining exceptions
        processed_results = []
        for i, result in enumerate(results):
            source_idx = i // len(queries)
            query_idx = i % len(queries)
            source = sources[source_idx]
            query = queries[query_idx]

            if isinstance(result, Exception):
                # Create error result for unexpected exceptions
                self.logger.warning(f"Unexpected error for {source}: {result}")
                error_result = AnalysisResult(
                    source=str(source),
                    query=query,
                    answer=f"Error analyzing {source}: {str(result)}",
                    confidence=0.0,
                    reasoning=f"Analysis failed due to: {str(result)}",
                    metadata={
                        "error": str(result),
                        "error_type": type(result).__name__,
                    },
                )
                processed_results.append(error_result)
            else:
                processed_results.append(result)

        # Determine return type based on input
        if is_single_result:
            # Single source + single query: return AnalysisResult directly
            return processed_results[0]
        else:
            # Multiple combinations: return BatchResult
            successful_results = [r for r in processed_results if r.confidence > 0]
            total_execution_time = time.time() - start_time
            average_confidence = (
                sum(r.confidence for r in successful_results) / len(successful_results) if successful_results else 0.0
            )

            return BatchResult(
                results=processed_results,
                total_queries=len(processed_results),
                successful_queries=len(successful_results),
                average_confidence=average_confidence,
                total_execution_time=total_execution_time,
            )

    async def compare(
        self,
        sources: list[str | Path],
        query: str = "Are these layouts consistent?",
        viewport: str = "desktop",
        context: dict[str, Any] | None = None,
        instructions: Instructions | None = None,
    ) -> ComparisonResult:
        """Compare multiple URLs or screenshots.

        Args:
            sources: List of URLs or screenshot paths to compare.
            query: Natural language question for comparison.
            viewport: Viewport size for URL captures.
            context: Additional context for analysis.
            instructions: Rich instructions for expert analysis.

        Returns:
            Comparison analysis with overall assessment.

        Example:
            >>> result = lens.compare([
            ...     "https://mysite.com/before",
            ...     "https://mysite.com/after"
            ... ], "Did the redesign improve the user experience?")
        """
        start_time = time.time()

        log_function_call(
            "LayoutLens.compare",
            sources=[str(s)[:30] + "..." if len(str(s)) > 30 else str(s) for s in sources],
            query=query[:100] + "..." if len(query) > 100 else query,
            viewport=viewport,
        )

        self.logger.info(f"Starting comparison of {len(sources)} sources")

        try:
            # Analyze each source individually first
            individual_results = []
            screenshot_paths = []

            for i, source in enumerate(sources):
                self.logger.debug(f"Processing source {i + 1}/{len(sources)}: {str(source)[:50]}...")
                if self._is_url(source):
                    screenshot_paths_batch = await self.capture.screenshots([str(source)], viewport)
                    screenshot_path = screenshot_paths_batch[0]  # Get first (and only) result
                else:
                    screenshot_path = str(source)

                screenshot_paths.append(screenshot_path)

                # Individual analysis
                individual_result = await self.analyze(source, query, viewport, context)
                individual_results.append(individual_result)

            # Comparative analysis using first screenshot with comparison query
            self.logger.debug("Starting comparative analysis")
            if len(screenshot_paths) >= 2:
                # Use the first screenshot as the base image and enhance query for comparison
                comparison_query = f"{query}\n\nImages to compare: {', '.join(Path(p).name for p in screenshot_paths)}"
                comparison_response = await self._call_vision_api(
                    image_path=screenshot_paths[0],
                    query=comparison_query,
                    context=context,
                    instructions=instructions,
                )
                comparison = {
                    "answer": comparison_response["answer"],
                    "confidence": comparison_response["confidence"],
                    "reasoning": comparison_response["reasoning"],
                    "metadata": {
                        **comparison_response["metadata"],
                        "screenshot_count": len(screenshot_paths),
                        "context": context or {},
                    },
                }
            else:
                comparison = {
                    "answer": "Need at least 2 sources for comparison",
                    "confidence": 0.0,
                    "reasoning": "Insufficient sources provided for comparison",
                    "metadata": {"error": "insufficient_sources"},
                }

            execution_time = time.time() - start_time

            confidence = comparison.get("confidence", 0.0)

            # Log performance metrics
            log_performance_metric(
                operation="compare",
                duration=execution_time,
                confidence=confidence,
                source_count=len(sources),
                viewport=viewport,
            )

            self.logger.info(
                f"Comparison completed for {len(sources)} sources - confidence: {confidence:.2f}, time: {execution_time:.2f}s"
            )

            return ComparisonResult(
                sources=[str(s) for s in sources],
                query=query,
                answer=comparison["answer"],
                confidence=confidence,
                reasoning=comparison["reasoning"],
                individual_analyses=individual_results,
                screenshot_paths=screenshot_paths,
                execution_time=execution_time,
                metadata=comparison.get("metadata", {}),
            )

        except Exception as e:
            self.logger.error(f"Comparison failed for {len(sources)} sources: {e}")
            execution_time = time.time() - start_time
            return ComparisonResult(
                sources=[str(s) for s in sources],
                query=query,
                answer=f"Error during comparison: {str(e)}",
                confidence=0.0,
                reasoning="Comparison failed due to error",
                execution_time=execution_time,
                metadata={"error": str(e)},
            )

    def _is_url(self, source: str | Path) -> bool:
        """Check if source is a URL or file path."""
        if isinstance(source, Path):
            return False

        parsed = urlparse(str(source))
        return bool(parsed.scheme and parsed.netloc)

    def _is_html_file(self, source: str | Path) -> bool:
        """Check if source is an HTML file."""
        if self._is_url(source):
            return False

        path = Path(source)
        return path.suffix.lower() in [".html", ".htm"]

    def _detect_html_complexity(self, html_file_path: Path) -> bool:
        """Detect if HTML file has external dependencies (CSS, JS, images)."""
        try:
            with open(html_file_path, encoding="utf-8") as f:
                content = f.read().lower()

            # Check for external resources
            external_indicators = [
                "<link",
                "<script src",
                "<img src",
                "url(",
                "href=",
                "src=",
                "@import",
                "background-image",
            ]

            for indicator in external_indicators:
                # Check if indicator is present and it's a relative path (not http/https/data)
                if (
                    indicator in content
                    and "http://" not in content
                    and "https://" not in content
                    and "data:" not in content
                ):
                    return True

            return False
        except Exception:
            # If we can't read the file, assume it's complex
            return True

    async def _serve_html_and_capture(
        self,
        html_file_path: str | Path,
        viewport: str = "desktop",
        wait_for_selector: str | None = None,
        wait_time: int | None = None,
    ) -> str:
        """Serve HTML file locally and capture screenshot."""
        html_file_path = Path(html_file_path).resolve()
        if not html_file_path.exists():
            raise LayoutFileNotFoundError(
                f"HTML file not found: {html_file_path}",
                file_path=str(html_file_path),
            )

        # Try file:// URL first for simple HTML files (faster)
        if not self._detect_html_complexity(html_file_path):
            self.logger.debug(f"Using file:// URL for simple HTML: {html_file_path}")
            try:
                file_url = f"file://{html_file_path}"
                screenshot_paths = await self.capture.screenshots(
                    [file_url], viewport, wait_for_selector=wait_for_selector, wait_time=wait_time
                )
                screenshot_path = screenshot_paths[0]
                self.logger.info(f"Successfully captured HTML file via file:// URL: {html_file_path.name}")
                return screenshot_path
            except Exception as e:
                self.logger.debug(f"file:// URL failed, falling back to HTTP server: {e}")

        # Fall back to HTTP server for complex HTML files
        self.logger.debug(f"Using HTTP server for complex HTML: {html_file_path}")

        import http.server
        import socket
        import socketserver
        import threading
        import time

        # Find available port
        def find_free_port():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("", 0))
                s.listen(1)
                port = s.getsockname()[1]
            return port

        port = find_free_port()

        # Create a handler that serves files from the HTML file's directory
        class LocalFileHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(html_file_path.parent), **kwargs)

            def do_GET(self):
                # If requesting root, serve our HTML file
                if self.path == "/" or self.path == "":
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    with open(html_file_path, "rb") as f:
                        self.wfile.write(f.read())
                else:
                    # Serve other files normally (CSS, JS, images)
                    super().do_GET()

            def log_message(self, format, *args):
                # Suppress server logs
                return

        # Start server in background thread
        httpd = socketserver.TCPServer(("", port), LocalFileHandler)
        server_thread = threading.Thread(target=httpd.serve_forever)
        server_thread.daemon = True
        server_thread.start()

        try:
            # Give server time to start
            await asyncio.sleep(0.5)

            # Capture the served HTML page
            local_url = f"http://localhost:{port}/"
            self.logger.debug(f"Serving HTML file at {local_url}")

            screenshot_paths = await self.capture.screenshots(
                [local_url], viewport, wait_for_selector=wait_for_selector, wait_time=wait_time
            )
            screenshot_path = screenshot_paths[0]

            self.logger.info(f"Successfully captured HTML file via HTTP server: {html_file_path.name}")
            return screenshot_path

        finally:
            # Stop the server
            httpd.shutdown()
            httpd.server_close()
            server_thread.join(timeout=1)

    # Pipeline Mode Methods

    async def capture_only(
        self,
        source: str | Path,
        viewport: str = "desktop",
        wait_for_selector: str | None = None,
        wait_time: int | None = None,
    ) -> str:
        """Capture screenshot only without analysis (Stage 1 of 2-stage pipeline).

        Args:
            source: URL to capture or existing file path to validate.
            viewport: Viewport size for URL capture ("desktop", "mobile", "tablet").
            wait_for_selector: CSS selector to wait for before capturing.
            wait_time: Additional wait time in milliseconds.

        Returns:
            Path to the captured or validated screenshot file.

        Raises:
            ScreenshotError: If URL capture fails.
            LayoutFileNotFoundError: If file doesn't exist.

        Example:
            >>> lens = LayoutLens(api_key="...")
            >>> screenshot_path = lens.capture_only("https://example.com")
            >>> # Later analyze with different queries
            >>> result1 = lens.analyze_screenshot(screenshot_path, "Is it accessible?")
            >>> result2 = lens.analyze_screenshot(screenshot_path, "Is it mobile-friendly?")
        """
        start_time = time.time()

        log_function_call(
            "LayoutLens.capture_only",
            source=str(source)[:50] + "..." if len(str(source)) > 50 else str(source),
            viewport=viewport,
        )

        try:
            if self._is_url(source):
                self.logger.debug(f"Capturing screenshot from URL: {source}")

                # Use simplified async capture interface
                screenshot_paths_batch = await self.capture.screenshots(
                    [str(source)], viewport, wait_for_selector=wait_for_selector, wait_time=wait_time
                )
                screenshot_path = screenshot_paths_batch[0]  # Get first (and only) result

                self.logger.info(f"Successfully captured screenshot: {screenshot_path}")

                # Log performance metrics
                log_performance_metric(
                    operation="capture_only",
                    duration=time.time() - start_time,
                    source_type="url",
                    viewport=viewport,
                )

                return screenshot_path
            elif self._is_html_file(source):
                self.logger.debug(f"Capturing screenshot from HTML file: {source}")

                # HTML files need to be served and captured asynchronously
                # Since this method is async, we can directly await
                screenshot_path = await self._serve_html_and_capture(
                    html_file_path=source,
                    viewport=viewport,
                    wait_for_selector=wait_for_selector,
                    wait_time=wait_time,
                )

                self.logger.info(f"Successfully captured HTML file screenshot: {screenshot_path}")

                # Log performance metrics
                log_performance_metric(
                    operation="capture_only",
                    duration=time.time() - start_time,
                    source_type="html_file",
                    viewport=viewport,
                )

                return screenshot_path
            else:
                # Validate existing file (image)
                screenshot_path = str(source)
                if not Path(screenshot_path).exists():
                    self.logger.error(f"Screenshot file not found: {screenshot_path}")
                    raise LayoutFileNotFoundError(
                        f"Screenshot file not found: {screenshot_path}",
                        file_path=screenshot_path,
                    )

                self.logger.info(f"Validated existing screenshot: {screenshot_path}")
                return screenshot_path

        except LayoutLensError as e:
            self.logger.debug(f"LayoutLens error in capture_only: {type(e).__name__}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error in capture_only: {e}")
            raise wrap_exception(e, "Screenshot capture failed") from e

    async def capture_only_async(
        self,
        source: str | Path,
        viewport: str = "desktop",
        wait_for_selector: str | None = None,
        wait_time: int | None = None,
    ) -> str:
        """Async version of capture_only for CLI use (Stage 1 of 2-stage pipeline)."""
        start_time = time.time()

        log_function_call(
            "LayoutLens.capture_only_async",
            source=str(source)[:50] + "..." if len(str(source)) > 50 else str(source),
            viewport=viewport,
        )

        try:
            if self._is_url(source):
                self.logger.debug(f"Async capturing screenshot from URL: {source}")
                screenshot_paths = await self.capture.screenshots(
                    [str(source)], viewport, wait_for_selector=wait_for_selector, wait_time=wait_time
                )
                screenshot_path = screenshot_paths[0]
                self.logger.info(f"Successfully captured screenshot: {screenshot_path}")

                # Log performance metrics
                log_performance_metric(
                    operation="capture_only_async",
                    duration=time.time() - start_time,
                    source_type="url",
                    viewport=viewport,
                )

                return screenshot_path
            elif self._is_html_file(source):
                self.logger.debug(f"Async capturing screenshot from HTML file: {source}")
                screenshot_path = await self._serve_html_and_capture(
                    html_file_path=source, viewport=viewport, wait_for_selector=wait_for_selector, wait_time=wait_time
                )
                self.logger.info(f"Successfully captured HTML file screenshot: {screenshot_path}")

                # Log performance metrics
                log_performance_metric(
                    operation="capture_only_async",
                    duration=time.time() - start_time,
                    source_type="html_file",
                    viewport=viewport,
                )

                return screenshot_path
            else:
                # Validate existing file (image)
                screenshot_path = str(source)
                if not Path(screenshot_path).exists():
                    self.logger.error(f"Screenshot file not found: {screenshot_path}")
                    raise LayoutFileNotFoundError(
                        f"Screenshot file not found: {screenshot_path}",
                        file_path=screenshot_path,
                    )

                self.logger.info(f"Validated existing screenshot: {screenshot_path}")
                return screenshot_path

        except LayoutLensError as e:
            self.logger.debug(f"LayoutLens error in capture_only_async: {type(e).__name__}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error in capture_only_async: {e}")
            raise wrap_exception(e, "Async screenshot capture failed") from e

    # Developer convenience methods
    async def check_accessibility(self, source: str | Path, viewport: str = "desktop") -> AnalysisResult:
        """Quick accessibility check with common WCAG queries."""
        query = """
        Analyze this page for accessibility issues. Check:
        1. Color contrast and readability
        2. Button and link sizing for touch targets
        3. Visual hierarchy and heading structure
        4. Form labels and input clarity
        5. Overall usability for users with disabilities

        Provide specific feedback on what works well and what needs improvement.
        """
        return await self.analyze(source, query, viewport)

    async def check_mobile_friendly(self, source: str | Path) -> AnalysisResult:
        """Quick mobile responsiveness check."""
        query = """
        Evaluate this page for mobile usability:
        1. Are touch targets large enough (minimum 44px)?
        2. Is text readable without zooming?
        3. Is navigation accessible on small screens?
        4. Does content fit properly without horizontal scrolling?
        5. Are forms easy to use on mobile?

        Rate the mobile experience and suggest improvements.
        """
        return await self.analyze(source, query, "mobile")

    async def check_conversion_optimization(self, source: str | Path, viewport: str = "desktop") -> AnalysisResult:
        """Check for conversion-focused design elements."""
        query = """
        Analyze this page for conversion optimization:
        1. Is the primary call-to-action prominent and clear?
        2. Is the value proposition immediately obvious?
        3. Are there any friction points in the user flow?
        4. Does the design build trust and credibility?
        5. Is the page focused or too cluttered?

        Provide specific recommendations to improve conversions.
        """
        return await self.analyze(source, query, viewport)

    # Enhanced Expert-Based Analysis Methods

    async def audit_accessibility(
        self, source: str | Path, standards: list[str] = None, compliance_level: str = "AA", viewport: str = "desktop"
    ) -> AnalysisResult:
        """Professional accessibility audit using WCAG expert knowledge.

        Args:
            source: URL or file path to analyze
            standards: Accessibility standards to apply (default: WCAG 2.1, Section 508)
            compliance_level: WCAG compliance level (A, AA, AAA)
            viewport: Viewport for analysis

        Returns:
            Detailed accessibility assessment with specific WCAG guidance
        """
        from ..prompts import Instructions

        instructions = Instructions.for_accessibility_audit(standards=standards, compliance_level=compliance_level)

        query = f"Perform a comprehensive accessibility audit for WCAG {compliance_level} compliance"
        return await self.analyze(source, query, viewport=viewport, instructions=instructions)

    async def optimize_conversions(
        self,
        source: str | Path,
        business_goals: list[str] = None,
        industry: str = None,
        target_audience: str = None,
        viewport: str = "desktop",
    ) -> AnalysisResult:
        """Conversion rate optimization analysis using CRO expert knowledge.

        Args:
            source: URL or file path to analyze
            business_goals: Business objectives (e.g., reduce_cart_abandonment)
            industry: Industry context for specialized recommendations
            target_audience: Target audience for optimization focus
            viewport: Viewport for analysis

        Returns:
            Detailed CRO recommendations with A/B testing suggestions
        """
        from ..prompts import Instructions

        instructions = Instructions.for_conversion_optimization(
            business_goals=business_goals, industry=industry, target_audience=target_audience
        )

        query = "Analyze for conversion optimization opportunities with specific recommendations"
        return await self.analyze(source, query, viewport=viewport, instructions=instructions)

    async def analyze_mobile_ux(
        self, source: str | Path, device_types: list[str] = None, performance_focus: bool = True
    ) -> AnalysisResult:
        """Mobile UX analysis using mobile expert knowledge.

        Args:
            source: URL or file path to analyze
            device_types: Target devices (smartphone, tablet)
            performance_focus: Include performance optimization analysis

        Returns:
            Mobile-specific UX recommendations and optimizations
        """
        from ..prompts import Instructions

        instructions = Instructions.for_mobile_optimization(
            device_types=device_types, performance_focus=performance_focus
        )

        query = "Evaluate mobile user experience and provide optimization recommendations"
        return await self.analyze(source, query, viewport="mobile_portrait", instructions=instructions)

    async def audit_ecommerce(
        self,
        source: str | Path,
        page_type: str = "product_page",
        business_model: str = "b2c",
        viewport: str = "desktop",
    ) -> AnalysisResult:
        """E-commerce UX audit using retail expert knowledge.

        Args:
            source: URL or file path to analyze
            page_type: Type of e-commerce page (product_page, checkout, homepage)
            business_model: Business model (b2c, b2b)
            viewport: Viewport for analysis

        Returns:
            E-commerce specific recommendations for conversion improvement
        """
        from ..prompts import Instructions

        instructions = Instructions.for_ecommerce_analysis(page_type=page_type, business_model=business_model)

        query = f"Audit this {page_type} for e-commerce best practices and conversion optimization"
        return await self.analyze(source, query, viewport=viewport, instructions=instructions)

    async def analyze_with_expert(
        self,
        source: str | Path,
        query: str,
        expert_persona: str,
        focus_areas: list[str] = None,
        user_context: dict[str, Any] = None,
        viewport: str = "desktop",
    ) -> AnalysisResult:
        """Analyze using a specific domain expert persona.

        Args:
            source: URL or file path to analyze
            query: Question to analyze
            expert_persona: Expert to use (accessibility_expert, conversion_expert, etc.)
            focus_areas: Specific areas to focus analysis on
            user_context: Rich context about users and requirements
            viewport: Viewport for analysis

        Returns:
            Expert-level analysis with domain-specific recommendations
        """
        from ..prompts import Instructions, UserContext

        # Convert user_context dict to UserContext object if provided
        context_obj = None
        if user_context:
            context_obj = UserContext(**user_context)

        instructions = Instructions(
            expert_persona=expert_persona, focus_areas=focus_areas or [], user_context=context_obj
        )

        return await self.analyze(source, query, viewport=viewport, instructions=instructions)

    async def compare_with_expert(
        self,
        sources: list[str | Path],
        query: str,
        expert_persona: str,
        focus_areas: list[str] = None,
        viewport: str = "desktop",
    ) -> ComparisonResult:
        """Compare multiple sources using domain expert knowledge.

        Args:
            sources: List of URLs or file paths to compare
            query: Comparison question
            expert_persona: Expert to use for comparison
            focus_areas: Specific areas to focus comparison on
            viewport: Viewport for analysis

        Returns:
            Expert comparison with domain-specific insights
        """
        from ..prompts import Instructions

        instructions = Instructions(expert_persona=expert_persona, focus_areas=focus_areas or [])

        return await self.compare(sources, query, viewport=viewport, instructions=instructions)

    # Batch Pipeline Methods

    async def capture_batch(
        self,
        sources: list[str | Path],
        viewport: str = "desktop",
        wait_for_selector: str | None = None,
        wait_time: int | None = None,
        max_concurrent: int = 3,
    ) -> dict[str, str]:
        """Capture screenshots from multiple URLs (Stage 1 of 2-stage pipeline).

        Args:
            sources: List of URLs to capture.
            viewport: Viewport size for captures.
            wait_for_selector: CSS selector to wait for before capturing.
            wait_time: Additional wait time in milliseconds.
            max_concurrent: Maximum concurrent captures.

        Returns:
            Dictionary mapping source URLs to screenshot paths.

        Example:
            >>> lens = LayoutLens(api_key="...")
            >>> screenshots = lens.capture_batch(["https://page1.com", "https://page2.com"])
            >>> # Later analyze with different queries
            >>> for url, path in screenshots.items():
            ...     result = lens.analyze_screenshot(path, "Is it accessible?", source_url=url)
        """
        start_time = time.time()

        log_function_call(
            "LayoutLens.capture_batch",
            source_count=len(sources),
            viewport=viewport,
            max_concurrent=max_concurrent,
        )

        self.logger.info(f"Starting batch capture of {len(sources)} sources")

        results = {}
        failed_count = 0

        # Filter URLs only (skip existing files)
        urls_to_capture = [s for s in sources if self._is_url(s)]
        existing_files = [s for s in sources if not self._is_url(s)]

        # Validate existing files
        for file_path in existing_files:
            if Path(file_path).exists():
                results[str(file_path)] = str(file_path)
                self.logger.debug(f"Using existing file: {file_path}")
            else:
                failed_count += 1
                results[str(file_path)] = f"Error: File not found"
                self.logger.warning(f"File not found: {file_path}")

        # Capture URLs using BatchCapture for efficiency
        if urls_to_capture:
            try:
                batch_capture = Capture(output_dir=str(self.output_dir / "screenshots"))

                # Use unified capture interface
                url_results = batch_capture.capture(
                    urls=urls_to_capture, viewports=[viewport], max_concurrent=max_concurrent
                )

                # Extract results for the specified viewport
                for url, viewport_results in url_results.items():
                    screenshot_path = viewport_results.get(viewport, "")
                    if screenshot_path.startswith("Error:"):
                        failed_count += 1
                        results[url] = screenshot_path
                    else:
                        results[url] = screenshot_path

            except Exception as e:
                self.logger.error(f"Batch capture failed: {e}")
                # Fallback to individual captures
                for url in urls_to_capture:
                    try:
                        screenshot_path = await self.capture_only(url, viewport, wait_for_selector, wait_time)
                        results[url] = screenshot_path
                    except Exception as capture_e:
                        failed_count += 1
                        results[url] = f"Error: {str(capture_e)}"
                        self.logger.warning(f"Individual capture failed for {url}: {capture_e}")

        execution_time = time.time() - start_time
        successful_count = len(sources) - failed_count

        # Log performance metrics
        log_performance_metric(
            operation="capture_batch",
            duration=execution_time,
            total_sources=len(sources),
            successful_captures=successful_count,
            failed_captures=failed_count,
            viewport=viewport,
            max_concurrent=max_concurrent,
        )

        self.logger.info(
            f"Batch capture completed: {successful_count}/{len(sources)} successful, time: {execution_time:.2f}s"
        )

        return results

    async def capture_batch_async(
        self,
        sources: list[str | Path],
        viewport: str = "desktop",
        wait_for_selector: str | None = None,
        wait_time: int | None = None,
        max_concurrent: int = 3,
    ) -> dict[str, str]:
        """Async version of capture_batch for CLI use (Stage 1 of 2-stage pipeline)."""
        start_time = time.time()

        log_function_call(
            "LayoutLens.capture_batch_async",
            source_count=len(sources),
            viewport=viewport,
            max_concurrent=max_concurrent,
        )

        self.logger.info(f"Starting async batch capture of {len(sources)} sources")

        results = {}

        # Filter URLs and HTML files vs existing files
        sources_to_capture = [s for s in sources if (self._is_url(s) or self._is_html_file(s))]
        existing_files = [s for s in sources if not (self._is_url(s) or self._is_html_file(s))]

        # Validate existing files
        for file_path in existing_files:
            if Path(file_path).exists():
                results[str(file_path)] = str(file_path)
                self.logger.debug(f"Using existing file: {file_path}")
            else:
                results[str(file_path)] = f"Error: File not found"
                self.logger.warning(f"File not found: {file_path}")

        # Capture sources concurrently
        if sources_to_capture:
            semaphore = asyncio.Semaphore(max_concurrent)

            async def capture_single(source):
                async with semaphore:
                    try:
                        return await self.capture_only_async(
                            source=source, viewport=viewport, wait_for_selector=wait_for_selector, wait_time=wait_time
                        )
                    except Exception as e:
                        self.logger.warning(f"Async capture failed for {source}: {e}")
                        return f"Error: {str(e)}"

            # Create tasks for all sources
            tasks = [capture_single(source) for source in sources_to_capture]

            # Execute all tasks concurrently
            capture_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for i, result in enumerate(capture_results):
                source = sources_to_capture[i]
                if isinstance(result, Exception):
                    results[str(source)] = f"Error: {str(result)}"
                else:
                    results[str(source)] = result

        execution_time = time.time() - start_time
        successful_count = sum(1 for v in results.values() if not str(v).startswith("Error:"))
        failed_count = len(sources) - successful_count

        # Log performance metrics
        log_performance_metric(
            operation="capture_batch_async",
            duration=execution_time,
            total_sources=len(sources),
            successful_captures=successful_count,
            failed_captures=failed_count,
            viewport=viewport,
            max_concurrent=max_concurrent,
        )

        self.logger.info(
            f"Async batch capture completed: {successful_count}/{len(sources)} successful, time: {execution_time:.2f}s"
        )

        return results

    async def pipeline_batch(
        self,
        sources: list[str | Path],
        queries: list[str],
        viewport: str = "desktop",
        context: dict[str, Any] | None = None,
        wait_for_selector: str | None = None,
        wait_time: int | None = None,
        max_concurrent_capture: int = 3,
    ) -> dict[str, list[AnalysisResult]]:
        """Complete 2-stage pipeline: capture then analyze multiple sources with multiple queries.

        Args:
            sources: List of URLs or paths to analyze.
            queries: List of natural language queries.
            viewport: Viewport size for captures.
            context: Additional context for analysis.
            wait_for_selector: CSS selector to wait for before capturing.
            wait_time: Additional wait time in milliseconds.
            max_concurrent_capture: Maximum concurrent captures.

        Returns:
            Dictionary mapping source names to lists of AnalysisResult objects.

        Example:
            >>> results = lens.pipeline_batch(
            ...     sources=["https://page1.com", "https://page2.com"],
            ...     queries=["Is it accessible?", "Is it responsive?"]
            ... )
            >>> for source, analysis_results in results.items():
            ...     for result in analysis_results:
            ...         print(f"{source}: {result.answer}")
        """
        start_time = time.time()

        log_function_call(
            "LayoutLens.pipeline_batch",
            source_count=len(sources),
            query_count=len(queries),
            total_analyses=len(sources) * len(queries),
            viewport=viewport,
        )

        self.logger.info(f"Starting complete 2-stage pipeline batch processing")

        # Stage 1: Capture all screenshots
        self.logger.debug("Stage 1: Capturing screenshots")
        screenshots = await self.capture_batch(
            sources=sources,
            viewport=viewport,
            wait_for_selector=wait_for_selector,
            wait_time=wait_time,
            max_concurrent=max_concurrent_capture,
        )

        # Stage 2: Analyze all screenshots with all queries
        self.logger.debug("Stage 2: Analyzing screenshots")
        results = self.analyze_captured_batch(
            screenshot_mapping=screenshots,
            queries=queries,
            viewport=viewport,
            context=context,
        )

        execution_time = time.time() - start_time

        # Calculate aggregate metrics
        total_analyses = sum(len(source_results) for source_results in results.values())
        successful_analyses = sum(
            1 for source_results in results.values() for result in source_results if result.confidence > 0
        )

        # Log performance metrics
        log_performance_metric(
            operation="pipeline_batch_complete",
            duration=execution_time,
            total_analyses=total_analyses,
            successful_analyses=successful_analyses,
            source_count=len(sources),
            query_count=len(queries),
            viewport=viewport,
        )

        self.logger.info(
            f"Complete 2-stage pipeline completed: {successful_analyses}/{total_analyses} successful analyses, time: {execution_time:.2f}s"
        )

        return results

    # Cache management methods
    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache performance statistics."""
        return self.cache.stats()

    def clear_cache(self) -> None:
        """Clear all cached analysis results."""
        self.cache.clear()

    def enable_cache(self) -> None:
        """Enable caching."""
        self.cache.enabled = True

    def disable_cache(self) -> None:
        """Disable caching."""
        self.cache.enabled = False
