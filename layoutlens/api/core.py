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
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

# Import LiteLLM directly
try:
    import litellm
    from litellm import acompletion
except ImportError as e:
    raise ImportError("litellm is required. Install with: pip install litellm") from e

# Import deterministic accessibility engine
from ..a11y import AXE_VERSION, A11yReport, AxeAuditor

# Import shared browser lifecycle (single-session hybrid audits)
from ..browser import open_page

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

# Import types
from ..types import (
    CacheType,
    ComplianceLevel,
    ComplianceLevelType,
    Expert,
    ExpertType,
    Viewport,
    ViewportType,
)

# Maps the provider strings accepted by LayoutLens(provider=...) to the
# environment variable that holds credentials for that provider. ``litellm`` maps
# to ``None``: it is a passthrough provider with no single canonical key, so
# LiteLLM resolves credentials from its own per-model env conventions at call time.
PROVIDER_API_KEY_ENV_VARS: dict[str, str | None] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GEMINI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "litellm": None,
}


def _dataclass_to_json(obj: Any) -> str:
    """Serialize a dataclass instance to an indented JSON string."""
    return json.dumps(asdict(obj), indent=2, default=str)


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
        return _dataclass_to_json(self)


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
        return _dataclass_to_json(self)


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
        return _dataclass_to_json(self)


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
            ConfigurationError: If invalid provider or configuration is specified.

        Notes:
            A missing API key does NOT raise here. The requirement is deferred to
            the first LLM call (see :meth:`_ensure_api_key`) so that deterministic,
            keyless operations such as ``check_accessibility(..., mode="axe")`` work
            without any credentials configured.
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

        # Determine API key based on provider. A missing key is tolerated here and
        # only enforced when an LLM call is actually made.
        self.api_key = api_key or self._get_api_key_for_provider(provider)

        self.model = model
        self.provider = provider
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        self.logger.info(f"Initialized LayoutLens with {provider} provider using {model} model")
        self.logger.debug(f"Output directory: {self.output_dir}")

        # Components will be created as needed (no persistent instances)
        self.logger.debug("LayoutLens core initialized - components created on demand")

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
        """Get appropriate API key based on provider.

        For the ``litellm`` passthrough provider this returns ``None`` even when
        ``OPENAI_API_KEY`` happens to be set, so an OpenAI key is never silently
        forwarded to, say, an Anthropic model. LiteLLM resolves credentials from
        its own env conventions in that case.
        """
        env_var = PROVIDER_API_KEY_ENV_VARS.get(provider, "OPENAI_API_KEY")
        if env_var is None:
            return None
        return os.getenv(env_var)

    def _ensure_api_key(self) -> None:
        """Enforce that an API key is available before making an LLM call.

        The key requirement is deferred from construction to first LLM use so
        deterministic-only operations (e.g. axe-based accessibility) stay keyless.
        The ``litellm`` passthrough provider is exempt: it has no single
        canonical key, so LiteLLM is left to resolve credentials from its own
        per-model env conventions (its auth errors are already surfaced).

        Raises:
            AuthenticationError: If no API key is configured for a mapped provider.
        """
        if self.provider == "litellm":
            return
        if not self.api_key:
            env_var = PROVIDER_API_KEY_ENV_VARS.get(self.provider, "OPENAI_API_KEY")
            self.logger.error(f"No API key found for {self.provider} provider")
            raise AuthenticationError(
                f"API key required for {self.provider} provider. Set {env_var} env var or pass api_key parameter."
            )

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
        # Enforce the API-key requirement at the first point of LLM use. Raised
        # (not swallowed) so it propagates through analyze as an AuthenticationError.
        self._ensure_api_key()

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

            completion_kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                        ],
                    }
                ],
                "max_tokens": 1000,
                "temperature": 0.1,
                "timeout": 30.0,
            }
            # Only pass api_key when we actually resolved one; otherwise let
            # LiteLLM fall back to its own provider-specific env resolution.
            if self.api_key:
                completion_kwargs["api_key"] = self.api_key

            response = await acompletion(**completion_kwargs)

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
        viewport: ViewportType = "desktop",
        context: dict[str, Any] | None = None,
        instructions: Instructions | None = None,
        max_concurrent: int = 5,
    ) -> AnalysisResult | BatchResult:
        """Smart analyze method that handles single or multiple sources and queries.

        Args:
            source: Single URL/path or list of URLs/paths to analyze.
            query: Single question or list of questions about the UI.
            viewport: Viewport for capture (Viewport.DESKTOP, "desktop", etc.).
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
        # Handle enum/string for viewport
        viewport_value = viewport.value if isinstance(viewport, Viewport) else str(viewport)

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
            viewport=viewport_value,
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
                    source=str(source), query=query, viewport=viewport_value, context=context
                )
                # ``AnalysisCache.get`` returns a defensive deep copy, so mutating
                # the result here (and by downstream callers such as the hybrid
                # axe override) can never corrupt the shared cached entry.
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
                        capture_engine = Capture(output_dir=self.output_dir / "screenshots")
                        screenshot_paths = await capture_engine.screenshots([str(source)], viewport_value)
                        screenshot_path = screenshot_paths[0]
                        self.logger.info(f"Successfully captured screenshot: {screenshot_path}")
                    elif self._is_html_file(source):
                        self.logger.debug(f"Capturing screenshot from HTML file: {source}")
                        screenshot_path = await self.capture(source, viewport=viewport)
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
                        viewport=viewport_value,
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
        viewport: ViewportType = "desktop",
        context: dict[str, Any] | None = None,
        instructions: Instructions | None = None,
    ) -> ComparisonResult:
        """Compare multiple URLs or screenshots.

        Args:
            sources: List of URLs or screenshot paths to compare.
            query: Natural language question for comparison.
            viewport: Viewport for captures (Viewport.DESKTOP or string).
            context: Additional context for analysis.
            instructions: Rich instructions for expert analysis.

        Returns:
            Comparison analysis with overall assessment.

        Example:
            >>> result = await lens.compare([
            ...     "https://mysite.com/before",
            ...     "https://mysite.com/after"
            ... ], "Did the redesign improve the user experience?")
        """
        # Handle enum/string for viewport
        viewport_value = viewport.value if isinstance(viewport, Viewport) else str(viewport)

        start_time = time.time()

        log_function_call(
            "LayoutLens.compare",
            sources=[str(s)[:30] + "..." if len(str(s)) > 30 else str(s) for s in sources],
            query=query[:100] + "..." if len(query) > 100 else query,
            viewport=viewport_value,
        )

        self.logger.info(f"Starting comparison of {len(sources)} sources")

        try:
            # Analyze each source individually first
            individual_results = []
            screenshot_paths = []

            for i, source in enumerate(sources):
                self.logger.debug(f"Processing source {i + 1}/{len(sources)}: {str(source)[:50]}...")
                if self._is_url(source):
                    capture_engine = Capture(output_dir=self.output_dir / "screenshots")
                    screenshot_paths_batch = await capture_engine.screenshots([str(source)], viewport_value)
                    screenshot_path = screenshot_paths_batch[0]  # Get first (and only) result
                elif self._is_html_file(source):
                    # Render local HTML to a real screenshot; otherwise the raw
                    # HTML bytes would be base64-encoded and sent to the vision
                    # API mislabeled as a PNG (garbage comparative analysis).
                    screenshot_path = await self._serve_html_and_capture(source, viewport_value)
                else:
                    # Existing image file passes through unchanged.
                    screenshot_path = str(source)

                screenshot_paths.append(screenshot_path)

                # Individual analysis
                individual_result = await self.analyze(source, query, viewport_value, context)
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
                viewport=viewport_value,
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

    # Recognized raster/vector image extensions treated as pre-rendered screenshots.
    _IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".svg"})

    def _is_image_file(self, source: str | Path) -> bool:
        """Check if source is an image file (a pre-rendered screenshot).

        Image sources have no DOM, so the deterministic axe engine cannot audit
        them — accessibility modes must reject or skip them rather than audit a
        garbage document served as HTML.
        """
        if self._is_url(source):
            return False

        return Path(source).suffix.lower() in self._IMAGE_SUFFIXES

    async def _serve_html_and_capture(
        self,
        html_file_path: str | Path,
        viewport: ViewportType = "desktop",
        wait_for_selector: str | None = None,
        wait_time: int | None = None,
    ) -> str:
        """Serve a local HTML file and capture a screenshot.

        Serving is delegated to :func:`layoutlens.browser.open_page` (used by
        the capture engine), which stands up a temporary local HTTP server so
        relative CSS/JS/image references resolve correctly.
        """
        html_file_path = Path(html_file_path).resolve()
        if not html_file_path.exists():
            raise LayoutFileNotFoundError(
                f"HTML file not found: {html_file_path}",
                file_path=str(html_file_path),
            )

        capture_engine = Capture(output_dir=self.output_dir / "screenshots")
        screenshot_paths = await capture_engine.screenshots(
            [str(html_file_path)], viewport, wait_for_selector=wait_for_selector, wait_time=wait_time
        )
        screenshot_path = screenshot_paths[0]
        self.logger.info(f"Successfully captured HTML file: {html_file_path.name}")
        return screenshot_path

    # Unified Capture Method

    async def capture(
        self,
        source: str | Path | list[str | Path],
        viewport: ViewportType = "desktop",
        wait_for_selector: str | None = None,
        wait_time: int | None = None,
        max_concurrent: int = 3,
    ) -> str | dict[str, str]:
        """Smart capture method that handles single or multiple sources uniformly.

        Args:
            source: Single URL/path or list of URLs/paths to capture.
            viewport: Viewport for capture (Viewport.DESKTOP, "desktop", etc.).
            wait_for_selector: CSS selector to wait for before capturing.
            wait_time: Additional wait time in milliseconds.
            max_concurrent: Maximum concurrent captures for multiple sources.

        Returns:
            Single source: Returns screenshot path as string.
            Multiple sources: Returns dict mapping source to screenshot path.

        Examples:
            # Single URL
            >>> path = await lens.capture("https://example.com")
            # Returns: "/path/to/screenshot.png"

            # Multiple URLs
            >>> paths = await lens.capture(["https://site1.com", "https://site2.com"])
            # Returns: {"https://site1.com": "/path1.png", "https://site2.com": "/path2.png"}

            # HTML files
            >>> path = await lens.capture("page.html")
            >>> paths = await lens.capture(["page1.html", "page2.html"])

            # Existing images (validation)
            >>> path = await lens.capture("screenshot.png")
        """
        # Handle enum/string for viewport
        viewport_value = viewport.value if isinstance(viewport, Viewport) else str(viewport)

        # Normalize input to determine return type
        is_single_source = not isinstance(source, list)
        sources = [source] if is_single_source else source

        start_time = time.time()

        log_function_call(
            "LayoutLens.capture",
            source_count=len(sources),
            is_single_source=is_single_source,
            viewport=viewport_value,
            max_concurrent=max_concurrent,
        )

        self.logger.info(f"Starting capture of {len(sources)} source(s)")

        results = {}
        failed_count = 0

        # Separate sources by type for optimal processing
        urls_to_capture = [s for s in sources if self._is_url(s)]
        html_files = [s for s in sources if self._is_html_file(s)]
        existing_files = [s for s in sources if not (self._is_url(s) or self._is_html_file(s))]

        # Validate existing files (images)
        for file_path in existing_files:
            file_path_obj = Path(file_path)
            if file_path_obj.exists():
                results[str(file_path)] = str(file_path)
                self.logger.debug(f"Using existing file: {file_path}")
            else:
                failed_count += 1
                results[str(file_path)] = f"Error: File not found"
                self.logger.warning(f"File not found: {file_path}")

        # Capture URLs using efficient batch processing
        if urls_to_capture:
            try:
                # Create Capture instance for URL processing
                capture_engine = Capture(output_dir=self.output_dir / "screenshots")
                screenshot_paths = await capture_engine.screenshots(
                    urls_to_capture, viewport_value, max_concurrent, wait_for_selector, wait_time
                )

                # Map results back
                for i, url in enumerate(urls_to_capture):
                    screenshot_path = screenshot_paths[i]
                    if screenshot_path.startswith("Error:"):
                        failed_count += 1
                    results[str(url)] = screenshot_path

                self.logger.info(f"Captured {len(urls_to_capture)} URL screenshots")

            except Exception as e:
                self.logger.error(f"URL capture failed: {e}")
                for url in urls_to_capture:
                    failed_count += 1
                    results[str(url)] = f"Error: {str(e)}"

        # Capture HTML files individually (they need special serving)
        if html_files:
            semaphore = asyncio.Semaphore(max_concurrent)

            async def capture_html_file(html_path):
                async with semaphore:
                    try:
                        return await self._serve_html_and_capture(
                            html_path, viewport_value, wait_for_selector, wait_time
                        )
                    except Exception as e:
                        self.logger.warning(f"HTML capture failed for {html_path}: {e}")
                        return f"Error: {str(e)}"

            # Process HTML files concurrently
            html_tasks = [capture_html_file(html_path) for html_path in html_files]
            html_results = await asyncio.gather(*html_tasks, return_exceptions=True)

            for i, result in enumerate(html_results):
                html_path = html_files[i]
                if isinstance(result, Exception) or (isinstance(result, str) and result.startswith("Error:")):
                    failed_count += 1
                    results[str(html_path)] = f"Error: {str(result)}" if isinstance(result, Exception) else result
                else:
                    results[str(html_path)] = result

            self.logger.info(f"Captured {len(html_files)} HTML file screenshots")

        execution_time = time.time() - start_time
        successful_count = len(sources) - failed_count

        # Log performance metrics
        log_performance_metric(
            operation="capture_unified",
            duration=execution_time,
            total_sources=len(sources),
            successful_captures=successful_count,
            failed_captures=failed_count,
            viewport=viewport_value,
            max_concurrent=max_concurrent,
        )

        self.logger.info(
            f"Capture completed: {successful_count}/{len(sources)} successful, time: {execution_time:.2f}s"
        )

        # Return format based on input type
        if is_single_source:
            # Single source: return the path directly
            return results[str(sources[0])]
        else:
            # Multiple sources: return the full mapping
            return results

    # Deterministic accessibility helpers

    @staticmethod
    def _axe_run_only_for_level(compliance_level: str) -> list[str]:
        """Map a WCAG compliance level to the axe tags to run.

        A -> ``["wcag2a"]``, AA -> ``["wcag2a", "wcag2aa"]``,
        AAA -> ``["wcag2a", "wcag2aa", "wcag2aaa"]``.
        """
        tags = ["wcag2a"]
        if compliance_level in ("AA", "AAA"):
            tags.append("wcag2aa")
        if compliance_level == "AAA":
            tags.append("wcag2aaa")
        return tags

    @staticmethod
    def _wcag_level_label(run_only: list[str] | None) -> str:
        """Return the WCAG level label covered by an axe ``run_only`` tag list.

        ``["wcag2a"]`` -> "WCAG A", ``["wcag2a", "wcag2aa"]`` -> "WCAG A/AA",
        adding ``"wcag2aaa"`` -> "WCAG A/AA/AAA".
        """
        tags = set(run_only or [])
        if "wcag2aaa" in tags:
            return "WCAG A/AA/AAA"
        if "wcag2aa" in tags:
            return "WCAG A/AA"
        return "WCAG A"

    @staticmethod
    def _axe_answer(report: A11yReport, level_label: str = "WCAG A/AA") -> str:
        """Phrase a natural-language yes/no answer from an axe report.

        ``level_label`` names the WCAG level(s) actually audited (see
        :meth:`_wcag_level_label`) so the answer never overstates coverage.
        """
        if report.violations:
            rule_ids = ", ".join(sorted({f.rule_id for f in report.violations}))
            return f"No — axe-core found {len(report.violations)} {level_label} violation(s): {rule_ids}"
        return f"Yes — axe-core found no {level_label} violations"

    def _build_axe_result(
        self,
        source: str | Path,
        query: str,
        viewport_value: str,
        report: A11yReport,
        mode: str,
        run_only: list[str] | None = None,
    ) -> AnalysisResult:
        """Build a deterministic AnalysisResult from an axe report (no LLM)."""
        return AnalysisResult(
            source=str(source),
            query=query,
            answer=self._axe_answer(report, self._wcag_level_label(run_only)),
            confidence=1.0,
            reasoning=report.summary(),
            viewport=viewport_value,
            metadata={
                "a11y": asdict(report),
                "mode": mode,
                "engine": f"axe-core {AXE_VERSION}",
                "provider": self.provider,
                "model": self.model,
            },
        )

    def _apply_axe_override(
        self,
        result: AnalysisResult,
        report: A11yReport,
        mode: str,
        run_only: list[str] | None = None,
    ) -> AnalysisResult:
        """Apply the deterministic override to a hybrid LLM result.

        If axe found violations, the final answer is forced to "no" with full
        confidence and reasoning that combines axe findings with the LLM's
        assessment. If axe found none, the LLM's answer/confidence are kept.
        The axe report is always attached under ``metadata["a11y"]``.
        """
        if report.violations:
            result.answer = self._axe_answer(report, self._wcag_level_label(run_only))
            result.confidence = 1.0
            result.reasoning = f"{report.summary()}\n\nLLM assessment:\n{result.reasoning}"
        result.metadata["a11y"] = asdict(report)
        result.metadata["mode"] = mode
        result.metadata["engine"] = f"axe-core {AXE_VERSION}"
        return result

    @staticmethod
    def _inject_axe_context(query: str, report: A11yReport) -> str:
        """Append a deterministic axe-core context block to an LLM query."""
        return (
            f"{query}\n\n"
            f"Deterministic axe-core scan results for this page:\n{report.summary()}\n"
            "Assess additional visual/contextual accessibility issues that automated rules cannot catch."
        )

    async def _run_a11y_check(
        self,
        source: str | Path,
        query: str,
        viewport_value: str,
        run_only: list[str],
        mode: str,
        instructions: Instructions | None = None,
    ) -> AnalysisResult:
        """Shared axe/hybrid execution for the accessibility entry points.

        Handles the image-source guard, the deterministic ``axe`` path, and the
        single-session ``hybrid`` path. ``llm`` mode is handled entirely by the
        callers and never reaches here.

        Raises:
            ValidationError: In ``axe`` mode when ``source`` is an image, which
                has no DOM for axe to audit.
        """
        # Image sources are pre-rendered screenshots with no DOM; axe would
        # otherwise be handed a garbage document served as HTML and report a
        # false "compliant" at full confidence.
        if self._is_image_file(source):
            if mode == "axe":
                raise ValidationError(
                    f"axe mode cannot audit an image source ({source}) — it has no DOM. "
                    "Provide a URL or HTML file, or use mode='llm' for vision-only analysis.",
                    field="source",
                    value=str(source),
                )
            # hybrid: fall back to vision-only and record why axe was skipped.
            self.logger.warning(
                f"Image source {source} has no DOM; falling back to llm-only for hybrid accessibility check."
            )
            result = await self.analyze(source, query, viewport=viewport_value, instructions=instructions)
            result.metadata["mode"] = "llm"
            result.metadata["a11y_skipped"] = "image source"
            return result

        if mode == "axe":
            report = await AxeAuditor(run_only=run_only).audit(source, viewport_value)
            return self._build_axe_result(source, query, viewport_value, report, mode, run_only)

        return await self._hybrid_a11y(source, query, viewport_value, run_only, mode, instructions)

    async def _hybrid_a11y(
        self,
        source: str | Path,
        query: str,
        viewport_value: str,
        run_only: list[str],
        mode: str,
        instructions: Instructions | None = None,
    ) -> AnalysisResult:
        """Run one browser session for the screenshot + axe audit, then the LLM.

        A single :func:`open_page` session yields the exact page the screenshot
        is taken from AND the DOM axe audits, so the pixels the LLM sees and the
        DOM axe scores can never diverge (and only one browser is launched).
        Results are cached under a key that includes the a11y mode so llm-mode
        and hybrid-mode results for the same source never collide. If axe fails,
        the check degrades gracefully to LLM-only with an ``a11y_error`` note.
        """
        cache_key = self.cache.get_analysis_key(
            source=str(source), query=query, viewport=viewport_value, context={"a11y_mode": mode}
        )
        # ``AnalysisCache.get`` already hands back a defensive deep copy.
        cached = self.cache.get(cache_key)
        if cached and isinstance(cached, AnalysisResult):
            cached.metadata["cache_hit"] = True
            return cached

        start_time = time.time()
        capture_engine = Capture(output_dir=self.output_dir / "screenshots")
        screenshot_path = capture_engine.output_dir / capture_engine._generate_filename(str(source), viewport_value)

        report: A11yReport | None = None
        axe_error: str | None = None
        async with open_page(source, viewport_value) as page:
            await page.screenshot(path=str(screenshot_path), full_page=True)
            try:
                report = await AxeAuditor(run_only=run_only).audit_page(
                    page, source=str(source), viewport=viewport_value
                )
            except Exception as e:  # noqa: BLE001 - degrade to LLM-only on axe failure
                axe_error = str(e)
                self.logger.warning(f"axe audit failed in hybrid mode; proceeding LLM-only: {e}")

        llm_query = self._inject_axe_context(query, report) if report is not None else query
        vision_response = await self._call_vision_api(
            image_path=str(screenshot_path), query=llm_query, instructions=instructions
        )

        result = AnalysisResult(
            source=str(source),
            query=query,
            answer=str(vision_response["answer"]),
            confidence=float(vision_response["confidence"]),
            reasoning=str(vision_response["reasoning"]),
            screenshot_path=str(screenshot_path),
            viewport=viewport_value,
            execution_time=time.time() - start_time,
            metadata={
                **vision_response["metadata"],
                "provider": self.provider,
                "model": self.model,
            },
        )

        if report is not None:
            result = self._apply_axe_override(result, report, mode, run_only)
        else:
            result.metadata["mode"] = mode
            result.metadata["a11y_error"] = axe_error

        self.cache.set(cache_key, result)
        return result

    # Developer convenience methods
    async def check_accessibility(
        self,
        source: str | Path,
        viewport: ViewportType = "desktop",
        mode: Literal["hybrid", "axe", "llm"] = "hybrid",
    ) -> AnalysisResult:
        """Accessibility check with deterministic axe-core, LLM vision, or both.

        Args:
            source: URL or file path to analyze.
            viewport: Viewport for capture/audit.
            mode: ``"hybrid"`` (default) runs deterministic axe-core WCAG A/AA
                checks and LLM vision analysis, forcing a "no" verdict when axe
                finds any violation. ``"axe"`` runs axe-core only (no API key
                required, no LLM call). ``"llm"`` runs the legacy vision-only
                analysis.

        Returns:
            AnalysisResult. In axe/hybrid modes ``metadata["a11y"]`` holds the
            full axe report, ``metadata["mode"]`` the mode, and
            ``metadata["engine"]`` the axe-core version.
        """
        viewport_value = viewport.value if isinstance(viewport, Viewport) else str(viewport)
        query = """
        Analyze this page for accessibility issues. Check:
        1. Color contrast and readability
        2. Button and link sizing for touch targets
        3. Visual hierarchy and heading structure
        4. Form labels and input clarity
        5. Overall usability for users with disabilities

        Provide specific feedback on what works well and what needs improvement.
        """

        if mode == "llm":
            result = await self.analyze(source, query, viewport_value)
            result.metadata["mode"] = mode
            return result

        return await self._run_a11y_check(source, query, viewport_value, ["wcag2a", "wcag2aa"], mode)

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

    async def check_conversion_optimization(
        self, source: str | Path, viewport: ViewportType = "desktop"
    ) -> AnalysisResult:
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
        self,
        source: str | Path,
        standards: list[str] = None,
        compliance_level: ComplianceLevelType = "AA",
        viewport: ViewportType = "desktop",
        mode: Literal["hybrid", "axe", "llm"] = "hybrid",
    ) -> AnalysisResult:
        """Professional accessibility audit using WCAG expert knowledge.

        Args:
            source: URL or file path to analyze
            standards: Accessibility standards to apply (default: WCAG 2.1, Section 508)
            compliance_level: WCAG compliance level (ComplianceLevel.AA or string)
            viewport: Viewport for analysis (Viewport.DESKTOP or string)
            mode: ``"hybrid"`` (default) combines deterministic axe-core checks with
                LLM analysis (axe violations force a "no" verdict). ``"axe"`` runs
                axe-core only (no API key required). ``"llm"`` runs the legacy
                vision-only audit. The axe run honors ``compliance_level``:
                A -> ``wcag2a``, AA -> ``wcag2a``+``wcag2aa``, AAA additionally
                includes ``wcag2aaa``.

        Returns:
            Detailed accessibility assessment with specific WCAG guidance

        Raises:
            ValueError: If compliance_level is not a valid WCAG level
        """
        from ..prompts import Instructions

        # Validate and normalize compliance level
        if isinstance(compliance_level, ComplianceLevel):
            compliance_level_value = compliance_level.value
        else:
            # Handle string input and validate
            compliance_level_upper = compliance_level.upper()
            try:
                compliance_level_enum = ComplianceLevel(compliance_level_upper)
                compliance_level_value = compliance_level_enum.value
            except ValueError:
                valid_levels = [level.value for level in ComplianceLevel]
                raise ValueError(f"compliance_level must be one of {valid_levels}, got: '{compliance_level}'") from None

        viewport_value = viewport.value if isinstance(viewport, Viewport) else str(viewport)
        instructions = Instructions.for_accessibility_audit(
            standards=standards, compliance_level=compliance_level_value
        )
        query = f"Perform a comprehensive accessibility audit for WCAG {compliance_level_value} compliance"

        if mode == "llm":
            result = await self.analyze(source, query, viewport=viewport_value, instructions=instructions)
            result.metadata["mode"] = mode
            return result

        run_only = self._axe_run_only_for_level(compliance_level_value)
        return await self._run_a11y_check(source, query, viewport_value, run_only, mode, instructions=instructions)

    async def optimize_conversions(
        self,
        source: str | Path,
        business_goals: list[str] = None,
        industry: str = None,
        target_audience: str = None,
        viewport: ViewportType = "desktop",
    ) -> AnalysisResult:
        """Conversion rate optimization analysis using CRO expert knowledge.

        Args:
            source: URL or file path to analyze
            business_goals: Business objectives (e.g., reduce_cart_abandonment)
            industry: Industry context for specialized recommendations
            target_audience: Target audience for optimization focus
            viewport: Viewport for analysis (Viewport.DESKTOP or string)

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
        viewport: ViewportType = "desktop",
    ) -> AnalysisResult:
        """E-commerce UX audit using retail expert knowledge.

        Args:
            source: URL or file path to analyze
            page_type: Type of e-commerce page (product_page, checkout, homepage)
            business_model: Business model (b2c, b2b)
            viewport: Viewport for analysis (Viewport.DESKTOP or string)

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
        expert_persona: ExpertType,
        focus_areas: list[str] = None,
        user_context: dict[str, Any] = None,
        viewport: ViewportType = "desktop",
    ) -> AnalysisResult:
        """Analyze using a specific domain expert persona.

        Args:
            source: URL or file path to analyze
            query: Question to analyze
            expert_persona: Expert to use (Expert.ACCESSIBILITY or string)
            focus_areas: Specific areas to focus analysis on
            user_context: Rich context about users and requirements
            viewport: Viewport for analysis (Viewport.DESKTOP or string)

        Returns:
            Expert-level analysis with domain-specific recommendations
        """
        from ..prompts import Instructions, UserContext

        # Handle enum/string for expert_persona
        expert_persona_value = expert_persona.value if isinstance(expert_persona, Expert) else str(expert_persona)

        # Handle enum/string for viewport
        viewport_value = viewport.value if isinstance(viewport, Viewport) else str(viewport)

        # Convert user_context dict to UserContext object if provided
        context_obj = None
        if user_context:
            context_obj = UserContext(**user_context)

        instructions = Instructions(
            expert_persona=expert_persona_value, focus_areas=focus_areas or [], user_context=context_obj
        )

        return await self.analyze(source, query, viewport=viewport_value, instructions=instructions)

    async def compare_with_expert(
        self,
        sources: list[str | Path],
        query: str,
        expert_persona: ExpertType,
        focus_areas: list[str] = None,
        viewport: ViewportType = "desktop",
    ) -> ComparisonResult:
        """Compare multiple sources using domain expert knowledge.

        Args:
            sources: List of URLs or file paths to compare
            query: Comparison question
            expert_persona: Expert to use for comparison (Expert.ACCESSIBILITY or string)
            focus_areas: Specific areas to focus comparison on
            viewport: Viewport for analysis (Viewport.DESKTOP or string)

        Returns:
            Expert comparison with domain-specific insights
        """
        from ..prompts import Instructions

        # Handle enum/string for expert_persona
        expert_persona_value = expert_persona.value if isinstance(expert_persona, Expert) else str(expert_persona)

        # Handle enum/string for viewport
        viewport_value = viewport.value if isinstance(viewport, Viewport) else str(viewport)

        instructions = Instructions(expert_persona=expert_persona_value, focus_areas=focus_areas or [])

        return await self.compare(sources, query, viewport=viewport_value, instructions=instructions)

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
