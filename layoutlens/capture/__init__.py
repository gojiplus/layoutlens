"""Screenshot and image capture capabilities for LayoutLens.

This module provides comprehensive screenshot functionality including
multi-viewport capture, element-specific screenshots, and comparison utilities.
"""

from .screenshot_manager import ScreenshotManager, ViewportConfig, ScreenshotResult, ScreenshotOptions

__all__ = ["ScreenshotManager", "ViewportConfig", "ScreenshotResult", "ScreenshotOptions"]