"""
Type definitions for LayoutLens JSON schemas and API interfaces.

This module provides TypedDict definitions for all JSON inputs and outputs,
ensuring type safety and clear documentation of expected data structures.
"""

from typing import Any, TypedDict


class AnalysisResultJSON(TypedDict):
    """JSON schema for AnalysisResult objects.

    Example:
        {
            "source": "https://example.com",
            "query": "Is this page accessible?",
            "answer": "Yes, the page follows accessibility guidelines.",
            "confidence": 0.85,
            "reasoning": "The page has proper heading structure...",
            "screenshot_path": "/path/to/screenshot.png",
            "viewport": "desktop",
            "timestamp": "2024-01-15T10:30:45",
            "execution_time": 2.3,
            "metadata": {"tokens_used": 150, "cache_hit": false}
        }
    """

    source: str
    query: str
    answer: str
    confidence: float  # 0.0 to 1.0
    reasoning: str
    screenshot_path: str | None
    viewport: str
    timestamp: str
    execution_time: float
    metadata: dict[str, Any]


class ComparisonResultJSON(TypedDict):
    """JSON schema for ComparisonResult objects.

    Example:
        {
            "sources": ["page1.html", "page2.html"],
            "query": "Which design is better?",
            "answer": "The second design is more user-friendly.",
            "confidence": 0.78,
            "reasoning": "Page 2 has better visual hierarchy...",
            "viewport": "desktop",
            "timestamp": "2024-01-15T10:30:45",
            "execution_time": 3.1,
            "metadata": {"comparison_type": "design_quality"}
        }
    """

    sources: list[str]
    query: str
    answer: str
    confidence: float  # 0.0 to 1.0
    reasoning: str
    viewport: str
    timestamp: str
    execution_time: float
    metadata: dict[str, Any]


class BatchResultJSON(TypedDict):
    """JSON schema for BatchResult objects.

    Example:
        {
            "total_queries": 6,
            "successful_queries": 5,
            "failed_queries": 1,
            "success_rate": 0.83,
            "average_confidence": 0.82,
            "execution_time": 12.5,
            "results": [...],  # List of AnalysisResultJSON
            "metadata": {"batch_processing": true, "max_concurrent": 3}
        }
    """

    total_queries: int
    successful_queries: int
    failed_queries: int
    success_rate: float  # 0.0 to 1.0
    average_confidence: float  # 0.0 to 1.0
    execution_time: float
    results: list[AnalysisResultJSON]
    metadata: dict[str, Any]


class UITestCaseJSON(TypedDict):
    """JSON schema for UITestCase objects.

    Example:
        {
            "name": "Homepage Accessibility Test",
            "html_path": "tests/homepage.html",
            "queries": ["Is it accessible?", "Good contrast?"],
            "viewports": ["desktop", "mobile"],
            "metadata": {"priority": "high", "category": "accessibility"}
        }
    """

    name: str
    html_path: str
    queries: list[str]
    viewports: list[str]
    metadata: dict[str, Any]


class UITestSuiteJSON(TypedDict):
    """JSON schema for UITestSuite objects.

    Example:
        {
            "name": "Website Quality Assurance",
            "description": "Comprehensive UI testing suite",
            "test_cases": [...],  # List of UITestCaseJSON
            "metadata": {"version": "1.0", "environment": "production"}
        }
    """

    name: str
    description: str
    test_cases: list[UITestCaseJSON]
    metadata: dict[str, Any]


class UITestResultJSON(TypedDict):
    """JSON schema for UITestResult objects.

    Example:
        {
            "suite_name": "Website QA",
            "test_case_name": "Accessibility Test",
            "total_tests": 4,
            "passed_tests": 3,
            "failed_tests": 1,
            "success_rate": 0.75,
            "duration_seconds": 15.2,
            "results": [...],  # List of AnalysisResultJSON
            "metadata": {"environment": "staging"}
        }
    """

    suite_name: str
    test_case_name: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    success_rate: float  # 0.0 to 1.0
    duration_seconds: float
    results: list[AnalysisResultJSON]
    metadata: dict[str, Any]


class CacheStatsJSON(TypedDict):
    """JSON schema for cache statistics.

    Example:
        {
            "enabled": true,
            "type": "memory",
            "size": 42,
            "max_size": 100,
            "hits": 15,
            "misses": 8,
            "hit_rate": 0.65,
            "memory_usage": "2.3MB"
        }
    """

    enabled: bool
    type: str  # "memory" | "file" | "disabled"
    size: int
    max_size: int | None
    hits: int
    misses: int
    hit_rate: float  # 0.0 to 1.0
    memory_usage: str | None


# Input schemas for API methods


class AnalyzeInput(TypedDict, total=False):
    """Input schema for lens.analyze() method.

    Example:
        {
            "source": "https://example.com",  # Required
            "query": "Is this accessible?",   # Required
            "viewport": "desktop",            # Optional
            "context": {"focus": "navigation"},  # Optional
            "max_concurrent": 3               # Optional (for batch)
        }
    """

    source: str | list[str]  # Required: URL, file path, or list
    query: str | list[str]  # Required: Question(s) to ask
    viewport: str  # Optional: desktop, mobile, tablet
    context: dict[str, Any]  # Optional: Additional context
    max_concurrent: int  # Optional: Batch processing limit


class CompareInput(TypedDict, total=False):
    """Input schema for lens.compare() method.

    Example:
        {
            "sources": ["page1.html", "page2.html"],  # Required
            "query": "Which is better?",              # Required
            "viewport": "desktop",                    # Optional
            "context": {"focus": "usability"}        # Optional
        }
    """

    sources: list[str]  # Required: List of sources to compare
    query: str  # Required: Comparison question
    viewport: str  # Optional: Viewport for analysis
    context: dict[str, Any]  # Optional: Comparison context


class LayoutLensConfigJSON(TypedDict, total=False):
    """Configuration schema for LayoutLens initialization.

    Example:
        {
            "api_key": "sk-...",
            "model": "gpt-4o-mini",
            "output_dir": "screenshots",
            "cache_enabled": true,
            "cache_type": "memory",
            "max_concurrent": 5
        }
    """

    api_key: str  # OpenAI API key
    model: str  # AI model to use
    output_dir: str  # Screenshot output directory
    cache_enabled: bool  # Enable result caching
    cache_type: str  # "memory" | "file"
    max_concurrent: int  # Max concurrent requests


# Export commonly used types
__all__ = [
    "AnalysisResultJSON",
    "ComparisonResultJSON",
    "BatchResultJSON",
    "UITestCaseJSON",
    "UITestSuiteJSON",
    "UITestResultJSON",
    "CacheStatsJSON",
    "AnalyzeInput",
    "CompareInput",
    "LayoutLensConfigJSON",
]
