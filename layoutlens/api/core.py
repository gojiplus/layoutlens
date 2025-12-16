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
        provider: str = "openrouter",
        output_dir: str = "layoutlens_output",
        cache_enabled: bool = True,
        cache_type: str = "memory",
        cache_ttl: int = 3600,
    ):
        """
        Initialize LayoutLens with AI provider credentials.

        Parameters
        ----------
        api_key : str, optional
            API key for the provider. If not provided, will try OPENAI_API_KEY or OPENROUTER_API_KEY env vars
        model : str, default "gpt-4o-mini"
            Model to use for analysis (provider-specific naming)
        provider : str, default "openrouter"
            AI provider to use ("openrouter", "openai", "anthropic", "google")
        output_dir : str, default "layoutlens_output"
            Directory for storing screenshots and results
        cache_enabled : bool, default True
            Whether to enable result caching for performance
        cache_type : str, default "memory"
            Type of cache backend: "memory" or "file"
        cache_ttl : int, default 3600
            Cache time-to-live in seconds (1 hour default)
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
                f"API key required for {provider} provider. "
                f"Set OPENAI_API_KEY/OPENROUTER_API_KEY env var or pass api_key parameter."
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
            self.logger.debug("Initialized capture and comparator components")
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
        if provider.lower() in (
            "openrouter",
            "openai",
            "anthropic",
            "google",
            "gemini",
        ):
            # OpenRouter can be used for all providers
            return os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        return None

    def analyze(
        self,
        source: str | Path,
        query: str,
        viewport: str = "desktop",
        context: dict[str, Any] | None = None,
    ) -> AnalysisResult:
        """
        Analyze a URL or screenshot with a natural language query.

        Parameters
        ----------
        source : str or Path
            URL to analyze or path to screenshot image
        query : str
            Natural language question about the UI
        viewport : str, default "desktop"
            Viewport size for URL capture ("desktop", "mobile", "tablet")
        context : dict, optional
            Additional context for analysis (user_type, browser, etc.)

        Returns
        -------
        AnalysisResult
            Detailed analysis with answer, confidence, and reasoning

        Examples
        --------
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
            # Determine if source is URL or image file
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
        """
        Compare multiple URLs or screenshots.

        Parameters
        ----------
        sources : list[str or Path]
            List of URLs or screenshot paths to compare
        query : str, default "Are these layouts consistent?"
            Natural language question for comparison
        viewport : str, default "desktop"
            Viewport size for URL captures
        context : dict, optional
            Additional context for analysis

        Returns
        -------
        ComparisonResult
            Comparison analysis with overall assessment

        Examples
        --------
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
                self.logger.debug(f"Processing source {i+1}/{len(sources)}: {str(source)[:50]}...")
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
        """
        Analyze multiple sources with multiple queries efficiently.

        Parameters
        ----------
        sources : list[str or Path]
            List of URLs or screenshot paths
        queries : list[str]
            List of natural language queries
        viewport : str, default "desktop"
            Viewport size for URL captures
        context : dict, optional
            Additional context for analysis

        Returns
        -------
        BatchResult
            Batch analysis results with aggregated metrics
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
                        f"Batch analysis {len(results)+1}/{len(sources)*len(queries)}: {str(source)[:30]}..."
                    )
                    result = self.analyze(source, query, viewport, context)
                    results.append(result)
                except Exception as e:
                    failed_count += 1
                    self.logger.warning(f"Batch analysis failed for {source} + query {j+1}: {e}")
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
        """
        Async version of analyze method for concurrent processing.

        Parameters
        ----------
        source : str or Path
            URL or path to screenshot file
        query : str
            Natural language query about the UI
        viewport : str, default "desktop"
            Viewport size for URL captures ("desktop", "mobile_portrait", etc.)
        context : dict, optional
            Additional context for analysis

        Returns
        -------
        AnalysisResult
            Analysis result with answer, confidence, and metadata
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
        """
        Analyze multiple sources with multiple queries concurrently.

        Parameters
        ----------
        sources : list[str or Path]
            List of URLs or screenshot paths
        queries : list[str]
            List of natural language queries
        viewport : str, default "desktop"
            Viewport size for URL captures
        context : dict, optional
            Additional context for analysis
        max_concurrent : int, default 5
            Maximum number of concurrent analyses

        Returns
        -------
        BatchResult
            Batch analysis results with aggregated metrics
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
