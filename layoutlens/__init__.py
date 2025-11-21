"""LayoutLens: AI-Enabled UI Test System

A production-ready AI-powered UI testing framework that enables natural language visual testing.
"""

# Import the main API
from .api.core import LayoutLens, AnalysisResult, ComparisonResult, BatchResult
from .api.test_suite import TestCase, TestSuite, TestResult
from .config import Config
from .exceptions import (
    LayoutLensError, APIError, ScreenshotError, ConfigurationError, 
    ValidationError, AnalysisError, TestSuiteError, AuthenticationError,
    RateLimitError, TimeoutError, LayoutFileNotFoundError, NetworkError
)
from .cache import AnalysisCache, create_cache

__all__ = [
    "LayoutLens", 
    "AnalysisResult", 
    "ComparisonResult", 
    "BatchResult",
    "TestCase",
    "TestSuite",
    "TestResult",
    "Config",
    # Exceptions
    "LayoutLensError",
    "APIError",
    "ScreenshotError", 
    "ConfigurationError",
    "ValidationError",
    "AnalysisError",
    "TestSuiteError",
    "AuthenticationError",
    "RateLimitError",
    "TimeoutError",
    "LayoutFileNotFoundError",
    "NetworkError",
    # Cache
    "AnalysisCache",
    "create_cache"
]

# Import version dynamically from pyproject.toml
try:
    import importlib.metadata
    __version__ = importlib.metadata.version("layoutlens")
except importlib.metadata.PackageNotFoundError:
    # Fallback for development/editable installs
    __version__ = "1.1.0-dev"

__author__ = "LayoutLens Team"