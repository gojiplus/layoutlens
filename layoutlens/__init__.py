"""LayoutLens: AI-Enabled UI Test System

A comprehensive framework for natural language UI testing using AI vision models.
"""

from .core import LayoutLens, TestSuite, TestCase
from .config import Config
from .reports import ReportGenerator

# Framework modules
try:
    from .vision import PageTester, PageTestResult
    from .capture import ScreenshotManager
    from .analysis import QueryGenerator
    __all__ = ["LayoutLens", "TestSuite", "TestCase", "Config", "ReportGenerator", 
               "PageTester", "PageTestResult", "ScreenshotManager", "QueryGenerator"]
except ImportError:
    __all__ = ["LayoutLens", "TestSuite", "TestCase", "Config", "ReportGenerator"]

__version__ = "1.0.0"
__author__ = "LayoutLens Team"