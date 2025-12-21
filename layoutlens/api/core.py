"""
Simple LayoutLens API for natural language UI testing.

This is the main entry point for the new simplified API that focuses on
real-world developer workflows and live website testing.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# Import caching
from ..cache import create_cache

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

# Import provider components
from ..providers import VisionProvider, create_provider

# Import vision components
from ..vision.capture import URLCapture
from ..vision.comparator import LayoutComparator


@dataclass
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


@dataclass
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


@dataclass
class BatchResult:
    """Result from batch analysis."""

    results: list[AnalysisResult]
    total_queries: int
    successful_queries: int
    average_confidence: float
    total_execution_time: float
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))


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

        # Initialize provider
        try:
            self.vision_provider = create_provider(
                provider_name=provider,
                api_key=self.api_key,
                model=self.model,
            )
            self.logger.debug(f"Created {provider} vision provider")
        except Exception as e:
            self.logger.error(f"Failed to create vision provider: {e}")
            raise

        # Initialize components
        try:
            self.capture = URLCapture(output_dir=str(self.output_dir / "screenshots"))
            self.comparator = LayoutComparator(vision_provider=self.vision_provider)

            # Initialize screenshot manager for 2-stage pipeline support
            from ..utils import ScreenshotManager

            self.screenshot_manager = ScreenshotManager(output_dir=self.output_dir)

            self.logger.debug("Initialized capture, comparator, and screenshot manager components")
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

    def analyze(
        self,
        source: str | Path,
        query: str,
        viewport: str = "desktop",
        context: dict[str, Any] | None = None,
    ) -> AnalysisResult:
        """Analyze a URL or screenshot with a natural language query.

        Args:
            source: URL to analyze or path to screenshot image.
            query: Natural language question about the UI.
            viewport: Viewport size for URL capture ("desktop", "mobile", "tablet").
            context: Additional context for analysis (user_type, browser, etc.).

        Returns:
            Detailed analysis with answer, confidence, and reasoning.

        Example:
            >>> result = lens.analyze("https://github.com", "Is the search bar easy to find?")
            >>> result = lens.analyze("screenshot.png", "Are the buttons large enough for mobile?")
        """
        start_time = time.time()

        log_function_call(
            "LayoutLens.analyze",
            source=str(source)[:50] + "..." if len(str(source)) > 50 else str(source),
            query=query[:100] + "..." if len(query) > 100 else query,
            viewport=viewport,
        )

        # Input validation
        if not query or not query.strip():
            self.logger.error(f"Empty query provided for source: {source}")
            raise ValidationError("Query cannot be empty", field="query", value=query)

        # Check cache first
        cache_key = self.cache.get_analysis_key(source=str(source), query=query, viewport=viewport, context=context)

        cached_result = self.cache.get(cache_key)
        if cached_result and isinstance(cached_result, AnalysisResult):
            # Update execution time and return cached result
            cached_result.execution_time = time.time() - start_time
            cached_result.metadata["cache_hit"] = True
            self.logger.info(f"Cache hit for source: {str(source)[:50]}... - confidence: {cached_result.confidence}")
            return cached_result

        try:
            # Determine if source is URL, HTML file, or image file
            if self._is_url(source):
                self.logger.debug(f"Capturing screenshot from URL: {source}")
                # Capture screenshot from URL
                try:
                    screenshot_path = self.capture.capture_url(url=str(source), viewport=viewport)
                    self.logger.info(f"Successfully captured screenshot: {screenshot_path}")
                except Exception as e:
                    self.logger.error(f"Screenshot capture failed for {source}: {e}")
                    raise ScreenshotError(
                        f"Failed to capture screenshot from URL: {str(e)}",
                        source=str(source),
                        viewport=viewport,
                    ) from e
            elif self._is_html_file(source):
                self.logger.debug(f"Capturing screenshot from HTML file: {source}")
                # HTML files need special handling - use the capture_only method
                try:
                    screenshot_path = self.capture_only(source, viewport=viewport)
                    self.logger.info(f"Successfully captured HTML file screenshot: {screenshot_path}")
                except Exception as e:
                    self.logger.error(f"HTML file capture failed for {source}: {e}")
                    raise ScreenshotError(
                        f"Failed to capture screenshot from HTML file: {str(e)}",
                        source=str(source),
                        viewport=viewport,
                    ) from e
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

            # Analyze with vision provider
            try:
                from ..providers import VisionAnalysisRequest

                self.logger.debug(f"Starting vision analysis for query: {query[:50]}...")
                request = VisionAnalysisRequest(
                    image_path=screenshot_path,
                    query=query,
                    context=context,
                    source_url=str(source) if self._is_url(source) else None,
                    viewport=viewport,
                )

                vision_response = self.vision_provider.analyze_image(request)
                self.logger.debug(f"Vision analysis completed with confidence: {vision_response.confidence}")

                analysis = {
                    "answer": vision_response.answer,
                    "confidence": vision_response.confidence,
                    "reasoning": vision_response.reasoning,
                    "metadata": vision_response.metadata,
                }

            except Exception as e:
                self.logger.error(f"Vision analysis failed for {source}: {e}")
                raise AnalysisError(
                    f"Failed to analyze screenshot: {str(e)}",
                    query=query,
                    source=str(source),
                    confidence=0.0,
                ) from e

            execution_time = time.time() - start_time

            # Safe type conversion
            confidence_value = analysis.get("confidence", 0.8)
            confidence = float(confidence_value) if isinstance(confidence_value, int | float) else 0.8

            metadata_dict = analysis.get("metadata", {})
            if not isinstance(metadata_dict, dict):
                metadata_dict = {}

            result = AnalysisResult(
                source=str(source),
                query=query,
                answer=str(analysis.get("answer", "")),
                confidence=confidence,
                reasoning=str(analysis.get("reasoning", "")),
                screenshot_path=screenshot_path,
                viewport=viewport,
                execution_time=execution_time,
                metadata={
                    **metadata_dict,
                    "cache_hit": False,
                    "provider": self.provider,
                    "model": self.model,
                    "pipeline_mode": "one-shot",
                },
            )

            # Log performance metrics
            log_performance_metric(
                operation="analyze",
                duration=execution_time,
                confidence=confidence,
                source_type="url" if self._is_url(source) else "file",
                viewport=viewport,
                cache_hit=False,
            )

            self.logger.info(
                f"Analysis completed for {str(source)[:50]}... - confidence: {confidence:.2f}, time: {execution_time:.2f}s"
            )

            # Cache the result
            self.cache.set(cache_key, result)

            return result

        except LayoutLensError as e:
            # Re-raise our custom exceptions
            self.logger.debug(f"LayoutLens error in analyze: {type(e).__name__}")
            raise
        except Exception as e:
            # Wrap other exceptions
            self.logger.error(f"Unexpected error in analyze: {e}")
            raise wrap_exception(e, "Analysis failed") from e

    def compare(
        self,
        sources: list[str | Path],
        query: str = "Are these layouts consistent?",
        viewport: str = "desktop",
        context: dict[str, Any] | None = None,
    ) -> ComparisonResult:
        """Compare multiple URLs or screenshots.

        Args:
            sources: List of URLs or screenshot paths to compare.
            query: Natural language question for comparison.
            viewport: Viewport size for URL captures.
            context: Additional context for analysis.

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
                    screenshot_path = self.capture.capture_url(str(source), viewport)
                else:
                    screenshot_path = str(source)

                screenshot_paths.append(screenshot_path)

                # Individual analysis
                individual_result = self.analyze(source, query, viewport, context)
                individual_results.append(individual_result)

            # Comparative analysis
            self.logger.debug("Starting comparative analysis")
            comparison = self.comparator.compare_layouts(
                screenshot_paths=screenshot_paths, query=query, context=context or {}
            )

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

    def analyze_batch(
        self,
        sources: list[str | Path],
        queries: list[str],
        viewport: str = "desktop",
        context: dict[str, Any] | None = None,
    ) -> BatchResult:
        """Analyze multiple sources with multiple queries efficiently.

        Args:
            sources: List of URLs or screenshot paths.
            queries: List of natural language queries.
            viewport: Viewport size for URL captures.
            context: Additional context for analysis.

        Returns:
            Batch analysis results with aggregated metrics.
        """
        start_time = time.time()

        log_function_call(
            "LayoutLens.analyze_batch",
            source_count=len(sources),
            query_count=len(queries),
            total_combinations=len(sources) * len(queries),
            viewport=viewport,
        )

        self.logger.info(
            f"Starting batch analysis: {len(sources)} sources × {len(queries)} queries = {len(sources) * len(queries)} total analyses"
        )

        results: list[AnalysisResult] = []
        failed_count = 0

        for source in sources:
            for j, query in enumerate(queries):
                try:
                    self.logger.debug(
                        f"Batch analysis {len(results) + 1}/{len(sources) * len(queries)}: {str(source)[:30]}..."
                    )
                    result = self.analyze(source, query, viewport, context)
                    results.append(result)
                except Exception as e:
                    failed_count += 1
                    self.logger.warning(f"Batch analysis failed for {source} + query {j + 1}: {e}")
                    # Create error result for failed analysis
                    error_result = AnalysisResult(
                        source=str(source),
                        query=query,
                        answer=f"Error analyzing {source}: {str(e)}",
                        confidence=0.0,
                        reasoning=f"Analysis failed due to: {str(e)}",
                        metadata={
                            "error": str(e),
                            "error_type": type(e).__name__,
                        },
                    )
                    results.append(error_result)

        # Calculate aggregate metrics
        successful_results = [r for r in results if r.confidence > 0]
        total_execution_time = time.time() - start_time
        average_confidence = (
            sum(r.confidence for r in successful_results) / len(successful_results) if successful_results else 0.0
        )

        # Log performance metrics
        log_performance_metric(
            operation="analyze_batch",
            duration=total_execution_time,
            total_analyses=len(results),
            successful_analyses=len(successful_results),
            failed_analyses=failed_count,
            average_confidence=average_confidence,
            viewport=viewport,
        )

        self.logger.info(
            f"Batch analysis completed: {len(successful_results)}/{len(results)} successful, "
            f"avg confidence: {average_confidence:.2f}, time: {total_execution_time:.2f}s"
        )

        return BatchResult(
            results=results,
            total_queries=len(results),
            successful_queries=len(successful_results),
            average_confidence=average_confidence,
            total_execution_time=total_execution_time,
        )

    async def analyze_async(
        self,
        source: str | Path,
        query: str,
        viewport: str = "desktop",
        context: dict[str, Any] | None = None,
    ) -> AnalysisResult:
        """Async version of analyze method for concurrent processing.

        Args:
            source: URL or path to screenshot file.
            query: Natural language query about the UI.
            viewport: Viewport size for URL captures ("desktop", "mobile_portrait", etc.).
            context: Additional context for analysis.

        Returns:
            Analysis result with answer, confidence, and metadata.

        Raises:
            ValidationError: If query is empty or invalid.
            LayoutFileNotFoundError: If screenshot file doesn't exist.
            AnalysisError: If analysis fails.
        """
        # Input validation
        if not query or not query.strip():
            raise ValidationError("Query cannot be empty", field="query", value=query)

        start_time = time.time()

        # Check cache first
        cache_key = self.cache.get_analysis_key(source=str(source), query=query, viewport=viewport, context=context)

        cached_result = self.cache.get(cache_key)
        if cached_result and isinstance(cached_result, AnalysisResult):
            cached_result.execution_time = time.time() - start_time
            cached_result.metadata["cache_hit"] = True
            return cached_result

        try:
            # Handle URL vs file path
            if self._is_url(source):
                # For now, run capture in thread pool (Playwright isn't fully async here)
                loop = asyncio.get_event_loop()
                screenshot_path = await loop.run_in_executor(None, self.capture.capture_url, str(source), viewport)
            else:
                screenshot_path = str(source)
                if not Path(screenshot_path).exists():
                    raise LayoutFileNotFoundError(
                        f"Screenshot file not found: {screenshot_path}",
                        file_path=screenshot_path,
                    )

            # Use provider's async analysis
            from ..providers import VisionAnalysisRequest

            request = VisionAnalysisRequest(
                image_path=screenshot_path,
                query=query,
                context=context,
                source_url=str(source) if self._is_url(source) else None,
                viewport=viewport,
            )

            vision_response = await self.vision_provider.analyze_image_async(request)

            execution_time = time.time() - start_time

            result = AnalysisResult(
                source=str(source),
                query=query,
                answer=vision_response.answer,
                confidence=vision_response.confidence,
                reasoning=vision_response.reasoning,
                screenshot_path=screenshot_path,
                viewport=viewport,
                execution_time=execution_time,
                metadata={
                    **vision_response.metadata,
                    "cache_hit": False,
                    "provider": self.provider,
                    "model": self.model,
                },
            )

            # Cache the result
            self.cache.set(cache_key, result)
            return result

        except Exception as e:
            if isinstance(e, LayoutLensError):
                raise
            raise AnalysisError(
                f"Failed to analyze screenshot: {str(e)}",
                query=query,
                source=str(source),
                confidence=0.0,
            ) from e

    async def analyze_batch_async(
        self,
        sources: list[str | Path],
        queries: list[str],
        viewport: str = "desktop",
        context: dict[str, Any] | None = None,
        max_concurrent: int = 5,
    ) -> BatchResult:
        """Analyze multiple sources with multiple queries concurrently.

        Args:
            sources: List of URLs or screenshot paths.
            queries: List of natural language queries.
            viewport: Viewport size for URL captures.
            context: Additional context for analysis.
            max_concurrent: Maximum number of concurrent analyses.

        Returns:
            Batch analysis results with aggregated metrics.
        """
        start_time = time.time()

        # Create semaphore to limit concurrent operations
        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_single(source: str | Path, query: str) -> AnalysisResult:
            async with semaphore:
                return await self.analyze_async(source, query, viewport, context)

        # Create tasks for all source/query combinations
        tasks = []
        for source in sources:
            for query in queries:
                task = asyncio.create_task(analyze_single(source, query))
                tasks.append(task)

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Create error result for failed analysis
                source_idx = i // len(queries)
                query_idx = i % len(queries)
                source = sources[source_idx]
                query = queries[query_idx]

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
                # result should be AnalysisResult here
                assert isinstance(result, AnalysisResult), f"Expected AnalysisResult, got {type(result)}"
                processed_results.append(result)

        # Calculate aggregate metrics
        successful_results = [r for r in processed_results if r.confidence > 0]
        total_execution_time = time.time() - start_time

        return BatchResult(
            results=processed_results,
            total_queries=len(processed_results),
            successful_queries=len(successful_results),
            average_confidence=(
                sum(r.confidence for r in successful_results) / len(successful_results) if successful_results else 0.0
            ),
            total_execution_time=total_execution_time,
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
                screenshot_path = await self.capture.capture_url_async(
                    url=file_url, viewport=viewport, wait_for_selector=wait_for_selector, wait_time=wait_time
                )
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

            screenshot_path = await self.capture.capture_url_async(
                url=local_url, viewport=viewport, wait_for_selector=wait_for_selector, wait_time=wait_time
            )

            self.logger.info(f"Successfully captured HTML file via HTTP server: {html_file_path.name}")
            return screenshot_path

        finally:
            # Stop the server
            httpd.shutdown()
            httpd.server_close()
            server_thread.join(timeout=1)

    # Pipeline Mode Methods

    def capture_only(
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

                # Try to detect if we're in an async context for better handling
                try:
                    import asyncio

                    asyncio.get_running_loop()
                    # We're in async context, but capture_url handles this now
                    screenshot_path = self.capture.capture_url(
                        url=str(source), viewport=viewport, wait_for_selector=wait_for_selector, wait_time=wait_time
                    )
                except RuntimeError:
                    # No event loop, proceed normally
                    screenshot_path = self.capture.capture_url(
                        url=str(source), viewport=viewport, wait_for_selector=wait_for_selector, wait_time=wait_time
                    )

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
                # For sync context, we need to handle this differently
                try:
                    import asyncio

                    asyncio.get_running_loop()
                    # We're in an event loop, can't use asyncio.run
                    # This case should use the async method instead
                    raise RuntimeError("HTML file capture requires async context - use capture_only_async")
                except RuntimeError as e:
                    if "requires async context" in str(e):
                        raise
                    # No event loop, use asyncio.run
                    screenshot_path = asyncio.run(
                        self._serve_html_and_capture(
                            html_file_path=source,
                            viewport=viewport,
                            wait_for_selector=wait_for_selector,
                            wait_time=wait_time,
                        )
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
                screenshot_path = await self.capture.capture_url_async(
                    url=str(source), viewport=viewport, wait_for_selector=wait_for_selector, wait_time=wait_time
                )
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

    def analyze_screenshot(
        self,
        screenshot_path: str | Path,
        query: str,
        context: dict[str, Any] | None = None,
        source_url: str | None = None,
        viewport: str = "desktop",
    ) -> AnalysisResult:
        """Analyze existing screenshot with natural language query (Stage 2 of 2-stage pipeline).

        Args:
            screenshot_path: Path to existing screenshot image.
            query: Natural language question about the UI.
            context: Additional context for analysis.
            source_url: Original URL if available (for metadata).
            viewport: Viewport that was used for capture (for metadata).

        Returns:
            Detailed analysis with answer, confidence, and reasoning.

        Raises:
            ValidationError: If query is empty.
            LayoutFileNotFoundError: If screenshot doesn't exist.
            AnalysisError: If analysis fails.

        Example:
            >>> result = lens.analyze_screenshot("screenshot.png", "Is the navigation centered?")
            >>> result = lens.analyze_screenshot("mobile_screenshot.png", "Are buttons touch-friendly?")
        """
        start_time = time.time()

        log_function_call(
            "LayoutLens.analyze_screenshot",
            screenshot_path=str(screenshot_path),
            query=query[:100] + "..." if len(query) > 100 else query,
        )

        # Input validation
        if not query or not query.strip():
            self.logger.error(f"Empty query provided for screenshot: {screenshot_path}")
            raise ValidationError("Query cannot be empty", field="query", value=query)

        screenshot_path = str(screenshot_path)
        if not Path(screenshot_path).exists():
            self.logger.error(f"Screenshot file not found: {screenshot_path}")
            raise LayoutFileNotFoundError(
                f"Screenshot file not found: {screenshot_path}",
                file_path=screenshot_path,
            )

        # Check cache first (use consistent cache key format)
        cache_source = source_url or screenshot_path
        cache_key = self.cache.get_analysis_key(source=cache_source, query=query, viewport=viewport, context=context)

        cached_result = self.cache.get(cache_key)
        if cached_result and isinstance(cached_result, AnalysisResult):
            cached_result.execution_time = time.time() - start_time
            cached_result.metadata["cache_hit"] = True
            self.logger.info(
                f"Cache hit for screenshot: {Path(screenshot_path).name} - confidence: {cached_result.confidence}"
            )
            return cached_result

        try:
            # Analyze with vision provider
            from ..providers import VisionAnalysisRequest

            self.logger.debug(f"Starting vision analysis for screenshot: {Path(screenshot_path).name}")
            request = VisionAnalysisRequest(
                image_path=screenshot_path,
                query=query,
                context=context,
                source_url=source_url,
                viewport=viewport,
            )

            vision_response = self.vision_provider.analyze_image(request)
            self.logger.debug(f"Vision analysis completed with confidence: {vision_response.confidence}")

            execution_time = time.time() - start_time

            # Safe type conversion
            confidence_value = vision_response.confidence
            confidence = float(confidence_value) if isinstance(confidence_value, int | float) else 0.8

            metadata_dict = vision_response.metadata or {}
            if not isinstance(metadata_dict, dict):
                metadata_dict = {}

            result = AnalysisResult(
                source=source_url or screenshot_path,
                query=query,
                answer=str(vision_response.answer),
                confidence=confidence,
                reasoning=str(vision_response.reasoning),
                screenshot_path=screenshot_path,
                viewport=viewport,
                execution_time=execution_time,
                metadata={
                    **metadata_dict,
                    "cache_hit": False,
                    "provider": self.provider,
                    "model": self.model,
                    "pipeline_mode": "2-stage",
                    "source_url": source_url,
                },
            )

            # Log performance metrics
            log_performance_metric(
                operation="analyze_screenshot",
                duration=execution_time,
                confidence=confidence,
                source_type="screenshot",
                viewport=viewport,
                cache_hit=False,
            )

            self.logger.info(
                f"Screenshot analysis completed for {Path(screenshot_path).name} - confidence: {confidence:.2f}, time: {execution_time:.2f}s"
            )

            # Cache the result
            self.cache.set(cache_key, result)

            return result

        except LayoutLensError as e:
            self.logger.debug(f"LayoutLens error in analyze_screenshot: {type(e).__name__}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error in analyze_screenshot: {e}")
            raise wrap_exception(e, "Screenshot analysis failed") from e

    # Developer convenience methods
    def check_accessibility(self, source: str | Path, viewport: str = "desktop") -> AnalysisResult:
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
        return self.analyze(source, query, viewport)

    def check_mobile_friendly(self, source: str | Path) -> AnalysisResult:
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
        return self.analyze(source, query, "mobile")

    def check_conversion_optimization(self, source: str | Path, viewport: str = "desktop") -> AnalysisResult:
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
        return self.analyze(source, query, viewport)

    # Batch Pipeline Methods

    def capture_batch(
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
                from ..vision.capture import BatchCapture

                batch_capture = BatchCapture(output_dir=str(self.output_dir / "screenshots"))

                # Use single viewport batch capture
                url_results = batch_capture.capture_url_list(
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
                        screenshot_path = self.capture_only(url, viewport, wait_for_selector, wait_time)
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

    def analyze_captured_batch(
        self,
        screenshot_mapping: dict[str, str],
        queries: list[str],
        viewport: str = "desktop",
        context: dict[str, Any] | None = None,
    ) -> dict[str, list[AnalysisResult]]:
        """Analyze batch of captured screenshots with multiple queries (Stage 2 of 2-stage pipeline).

        Args:
            screenshot_mapping: Dictionary mapping source URLs/names to screenshot paths.
            queries: List of natural language queries to analyze.
            viewport: Viewport that was used for capture (for metadata).
            context: Additional context for analysis.

        Returns:
            Dictionary mapping source names to lists of AnalysisResult objects.

        Example:
            >>> screenshots = lens.capture_batch(["https://page1.com", "https://page2.com"])
            >>> queries = ["Is it accessible?", "Is it mobile-friendly?"]
            >>> results = lens.analyze_captured_batch(screenshots, queries)
            >>> for source, analysis_results in results.items():
            ...     for result in analysis_results:
            ...         print(f"{source}: {result.answer}")
        """
        start_time = time.time()

        log_function_call(
            "LayoutLens.analyze_captured_batch",
            screenshot_count=len(screenshot_mapping),
            query_count=len(queries),
            total_analyses=len(screenshot_mapping) * len(queries),
        )

        self.logger.info(
            f"Starting batch analysis of {len(screenshot_mapping)} screenshots × {len(queries)} queries = {len(screenshot_mapping) * len(queries)} total analyses"
        )

        results = {}
        total_failed = 0

        for source_name, screenshot_path in screenshot_mapping.items():
            source_results = []

            # Skip failed captures
            if isinstance(screenshot_path, str) and screenshot_path.startswith("Error:"):
                for query in queries:
                    error_result = AnalysisResult(
                        source=source_name,
                        query=query,
                        answer=f"Cannot analyze: {screenshot_path}",
                        confidence=0.0,
                        reasoning="Screenshot capture failed",
                        viewport=viewport,
                        metadata={
                            "error": screenshot_path,
                            "pipeline_mode": "2-stage",
                        },
                    )
                    source_results.append(error_result)
                    total_failed += 1

                results[source_name] = source_results
                continue

            # Analyze with each query
            for query in queries:
                try:
                    result = self.analyze_screenshot(
                        screenshot_path=screenshot_path,
                        query=query,
                        context=context,
                        source_url=source_name if self._is_url(source_name) else None,
                        viewport=viewport,
                    )
                    source_results.append(result)
                except Exception as e:
                    total_failed += 1
                    self.logger.warning(f"Analysis failed for {source_name} + query '{query[:50]}...': {e}")
                    error_result = AnalysisResult(
                        source=source_name,
                        query=query,
                        answer=f"Error analyzing screenshot: {str(e)}",
                        confidence=0.0,
                        reasoning=f"Analysis failed due to: {str(e)}",
                        screenshot_path=screenshot_path,
                        viewport=viewport,
                        metadata={
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "pipeline_mode": "2-stage",
                        },
                    )
                    source_results.append(error_result)

            results[source_name] = source_results

        execution_time = time.time() - start_time
        total_analyses = len(screenshot_mapping) * len(queries)
        successful_analyses = total_analyses - total_failed

        # Log performance metrics
        log_performance_metric(
            operation="analyze_captured_batch",
            duration=execution_time,
            total_analyses=total_analyses,
            successful_analyses=successful_analyses,
            failed_analyses=total_failed,
            viewport=viewport,
        )

        self.logger.info(
            f"Batch analysis completed: {successful_analyses}/{total_analyses} successful, time: {execution_time:.2f}s"
        )

        return results

    def pipeline_batch(
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
        screenshots = self.capture_batch(
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
