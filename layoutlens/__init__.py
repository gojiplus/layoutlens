"""LayoutLens: AI-Enabled UI Test System

A production-ready AI-powered UI testing framework that enables
natural language visual testing.
"""

# Import the main API
from .api.core import AnalysisResult, BatchResult, ComparisonResult, LayoutLens
from .api.test_suite import UITestCase, UITestResult, UITestSuite
from .cache import AnalysisCache, create_cache
from .capture import Capture
from .config import Config
from .exceptions import (
    AnalysisError,
    APIError,
    AuthenticationError,
    ConfigurationError,
    LayoutFileNotFoundError,
    LayoutLensError,
    NetworkError,
    RateLimitError,
    ScreenshotError,
    TestSuiteError,
    TimeoutError,
    ValidationError,
)
from .logger import (
    configure_for_development,
    configure_for_production,
    configure_for_testing,
    configure_from_env,
    get_logger,
    setup_logging,
)
from .types import (
    CacheType,
    CacheTypeType,
    ComplianceLevel,
    ComplianceLevelType,
    Expert,
    ExpertType,
    Viewport,
    ViewportType,
)

__all__ = [
    "LayoutLens",
    "AnalysisResult",
    "ComparisonResult",
    "BatchResult",
    "UITestCase",
    "UITestSuite",
    "UITestResult",
    "Capture",
    "Config",
    # Types and Enums
    "ComplianceLevel",
    "Expert",
    "Viewport",
    "CacheType",
    "ViewportType",
    "ExpertType",
    "ComplianceLevelType",
    "CacheTypeType",
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
    "create_cache",
    # Logging
    "setup_logging",
    "configure_for_development",
    "configure_for_production",
    "configure_for_testing",
    "configure_from_env",
    "get_logger",
]

# Import version dynamically from pyproject.toml
try:
    import importlib.metadata

    __version__ = importlib.metadata.version("layoutlens")
except (importlib.metadata.PackageNotFoundError, ImportError):
    # Fallback for development/editable installs - read from pyproject.toml
    try:
        import tomllib
        from pathlib import Path

        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        if pyproject_path.exists():
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
                __version__ = data["project"]["version"]
        else:
            __version__ = "1.2.0-dev"
    except Exception:
        __version__ = "1.2.0-dev"

__author__ = "LayoutLens Team"
