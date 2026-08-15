"""LayoutLens: AI-Enabled UI Test System.

A production-ready AI-powered UI testing framework that enables
natural language visual testing.
"""

# Import deterministic accessibility engine
from .a11y import AXE_VERSION, A11yFinding, A11yReport, AxeAuditor

# Import the main API
from .api.batch import BatchRequest
from .api.core import AnalysisResult, BatchResult, ComparisonResult, LayoutLens
from .api.judge import JudgeResult
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

# Import deterministic layout/geometry scorers
from .layout import (
    LayoutFinding,
    LayoutReport,
    LayoutScorer,
    check_contrast,
    contrast_ratio,
    element_geometry,
    read_computed_styles,
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
    "AXE_VERSION",
    "A11yFinding",
    "A11yReport",
    "APIError",
    # Cache
    "AnalysisCache",
    "AnalysisError",
    "AnalysisResult",
    "AuthenticationError",
    # Deterministic accessibility engine
    "AxeAuditor",
    "BatchRequest",
    "BatchResult",
    "CacheType",
    "CacheTypeType",
    "Capture",
    "ComparisonResult",
    # Types and Enums
    "ComplianceLevel",
    "ComplianceLevelType",
    "Config",
    "ConfigurationError",
    "Expert",
    "ExpertType",
    "JudgeResult",
    "LayoutFileNotFoundError",
    "LayoutFinding",
    "LayoutLens",
    # Exceptions
    "LayoutLensError",
    "LayoutReport",
    # Deterministic layout/geometry scorers
    "LayoutScorer",
    "NetworkError",
    "RateLimitError",
    "ScreenshotError",
    "TestSuiteError",
    "TimeoutError",
    "UITestCase",
    "UITestResult",
    "UITestSuite",
    "ValidationError",
    "Viewport",
    "ViewportType",
    "check_contrast",
    "configure_for_development",
    "configure_for_production",
    "configure_for_testing",
    "configure_from_env",
    "contrast_ratio",
    "create_cache",
    "element_geometry",
    "get_logger",
    "read_computed_styles",
    # Logging
    "setup_logging",
]

# Import version dynamically from pyproject.toml
import importlib.metadata

try:
    __version__ = importlib.metadata.version("layoutlens")
except importlib.metadata.PackageNotFoundError:
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
