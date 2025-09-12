"""LayoutLens: AI-Enabled UI Test System

A production-ready AI-powered UI testing framework that enables natural language visual testing.
"""

# Import the main API
from .api.core import LayoutLens, AnalysisResult, ComparisonResult, BatchResult
from .config import Config

__all__ = [
    "LayoutLens", 
    "AnalysisResult", 
    "ComparisonResult", 
    "BatchResult",
    "Config"
]

__version__ = "1.0.4"
__author__ = "LayoutLens Team"