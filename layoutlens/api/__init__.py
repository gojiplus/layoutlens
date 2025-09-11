"""
Simplified LayoutLens API for natural language UI testing.

This module provides the main entry point for the new simplified API
designed for developer workflows and CI/CD integration.
"""

from .core import LayoutLens, AnalysisResult, ComparisonResult, BatchResult

__all__ = [
    "LayoutLens",
    "AnalysisResult", 
    "ComparisonResult",
    "BatchResult"
]