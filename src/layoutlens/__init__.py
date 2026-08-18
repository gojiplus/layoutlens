"""LayoutLens: AI-Enabled UI Test System.

A production-ready AI-powered UI testing framework that enables
natural language visual testing.
"""

# Import deterministic accessibility engine
from .a11y import AXE_VERSION, A11yFinding, A11yReport, AxeAuditor

# Import the main API
from .api.batch import BatchRequest, batch_usage_summary
from .api.core import AnalysisResult, BatchResult, ComparisonResult, LayoutLens
from .api.judge import JudgeResult
from .api.test_suite import UITestCase, UITestResult, UITestSuite
from .cache import AnalysisCache, create_cache
from .capture import Capture
from .exceptions import (
    AnalysisError,
    AuthenticationError,
    ConfigurationError,
    LayoutFileNotFoundError,
    LayoutLensError,
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

# Expert persona system
from .prompts import Instructions, UserContext, get_expert, list_available_experts
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
    "ConfigurationError",
    "Expert",
    "ExpertType",
    # Expert persona system
    "Instructions",
    "JudgeResult",
    "LayoutFileNotFoundError",
    "LayoutFinding",
    "LayoutLens",
    # Exceptions
    "LayoutLensError",
    "LayoutReport",
    # Deterministic layout/geometry scorers
    "LayoutScorer",
    "UITestCase",
    "UITestResult",
    "UITestSuite",
    "UserContext",
    "ValidationError",
    "Viewport",
    "ViewportType",
    "batch_usage_summary",
    "check_contrast",
    "configure_for_development",
    "configure_for_production",
    "configure_for_testing",
    "configure_from_env",
    "contrast_ratio",
    "create_cache",
    "element_geometry",
    "get_expert",
    "get_logger",
    "list_available_experts",
    "read_computed_styles",
    # Logging
    "setup_logging",
]

# Installed package metadata, generated from the static pyproject version, is the
# runtime source of truth.
import importlib.metadata

try:
    __version__ = importlib.metadata.version("layoutlens")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0+unknown"

__author__ = "LayoutLens Team"
