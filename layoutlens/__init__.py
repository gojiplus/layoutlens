"""LayoutLens: AI-Enabled UI Test System

A comprehensive framework for natural language UI testing using AI vision models.
"""

from .core import LayoutLens, TestSuite
from .config import Config
from .test_runner import TestRunner

__version__ = "1.0.0"
__author__ = "LayoutLens Team"

__all__ = ["LayoutLens", "TestSuite", "Config", "TestRunner"]