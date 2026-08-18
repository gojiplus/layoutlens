"""Simplified LayoutLens API for natural language UI testing.

This module provides the main entry point for the new simplified API
designed for developer workflows and CI/CD integration.
"""

from .batch import BatchRequest
from .core import AnalysisResult, BatchResult, ComparisonResult, LayoutLens
from .judge import JudgeResult

__all__ = [
    "AnalysisResult",
    "BatchRequest",
    "BatchResult",
    "ComparisonResult",
    "JudgeResult",
    "LayoutLens",
]
