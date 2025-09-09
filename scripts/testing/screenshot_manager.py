"""Enhanced screenshot capabilities for UI testing.

This module provides advanced screenshot functionality including
multi-viewport capture, element-specific screenshots, and
comparison utilities.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

try:
    from playwright.sync_api import sync_playwright, Browser, Page
except Exception:  # pragma: no cover
    sync_playwright = None
    Browser = None
    Page = None


@dataclass
class ViewportConfig:
    """Configuration for a specific viewport size."""
    
    name: str
    width: int
    height: int
    device_scale_factor: float = 1.0
    is_mobile: bool = False
    has_touch: bool = False
    user_agent: Optional[str] = None


@dataclass
class ScreenshotOptions:
    """Options for screenshot capture."""
    
    full_page: bool = True
    clip: Optional[Dict[str, int]] = None
    omit_background: bool = False
    quality: Optional[int] = None  # For JPEG format
    type: str = "png"  # png or jpeg
    animations: str = "disabled"  # disabled, allow
    caret: str = "hide"  # hide, initial
    mask: Optional[List[str]] = None  # CSS selectors to mask
    mask_color: str = "#FF0000"


@dataclass
class ScreenshotResult:
    """Result of a screenshot operation."""
    
    path: str
    viewport: ViewportConfig
    timestamp: str
    file_size: int
    metadata: Dict[str, Any] = field(default_factory=dict)


class ScreenshotManager:
    """Advanced screenshot manager for UI testing.
    
    This class provides comprehensive screenshot capabilities including:
    - Multi-viewport capture for responsive testing
    - Element-specific screenshots
    - Before/after comparison captures
    - Batch processing of multiple pages
    - Custom device emulation
    """
    
    # Common viewport configurations
    VIEWPORT_PRESETS = {
        "mobile_portrait": ViewportConfig("mobile_portrait", 375, 667, 2.0, True, True),
        "mobile_landscape": ViewportConfig("mobile_landscape", 667, 375, 2.0, True, True),
        "tablet_portrait": ViewportConfig("tablet_portrait", 768, 1024, 2.0, True, True),
        "tablet_landscape": ViewportConfig("tablet_landscape", 1024, 768, 2.0, True, True),
        "desktop": ViewportConfig("desktop", 1440, 900),
        "desktop_large": ViewportConfig("desktop_large", 1920, 1080),
        "desktop_xl": ViewportConfig("desktop_xl", 2560, 1440)
    }
    
    def __init__(self, output_dir: str = "screenshots", browser_type: str = "chromium"):
        """Initialize the screenshot manager.
        
        Parameters
        ----------
        output_dir : str
            Directory where screenshots will be saved
        browser_type : str
            Browser type to use (chromium, firefox, webkit)
        """
        if sync_playwright is None:
            raise ImportError("playwright is required for ScreenshotManager")
            
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.browser_type = browser_type
        self.browser = None
        self.context = None
    
    def __enter__(self):
        """Context manager entry."""
        self.playwright = sync_playwright().start()
        self.browser = getattr(self.playwright, self.browser_type).launch()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if hasattr(self, 'playwright'):
            self.playwright.stop()
    
    def capture_single(
        self, 
        html_path: str, 
        viewport: ViewportConfig,
        options: Optional[ScreenshotOptions] = None,
        output_name: Optional[str] = None
    ) -> ScreenshotResult:
        """Capture a screenshot of an HTML file with specified viewport.
        
        Parameters
        ----------
        html_path : str
            Path to HTML file to capture
        viewport : ViewportConfig
            Viewport configuration for the capture
        options : ScreenshotOptions, optional
            Screenshot capture options
        output_name : str, optional
            Custom output filename (without extension)
            
        Returns
        -------
        ScreenshotResult
            Result containing screenshot path and metadata
        """
        if not self.browser:
            raise RuntimeError("Browser not initialized. Use as context manager.")
        
        options = options or ScreenshotOptions()
        
        # Create browser context with viewport settings
        context_options = {
            "viewport": {"width": viewport.width, "height": viewport.height},
            "device_scale_factor": viewport.device_scale_factor,
            "is_mobile": viewport.is_mobile,
            "has_touch": viewport.has_touch,
        }
        
        if viewport.user_agent:
            context_options["user_agent"] = viewport.user_agent
            
        self.context = self.browser.new_context(**context_options)
        page = self.context.new_page()
        
        # Configure page settings
        if options.animations == "disabled":
            page.add_style_tag(content="""
                *, *::before, *::after {
                    animation-duration: 0s !important;
                    animation-delay: 0s !important;
                    transition-duration: 0s !important;
                    transition-delay: 0s !important;
                }
            """)
        
        # Navigate to HTML file
        html_abs_path = Path(html_path).resolve()
        page.goto(f"file://{html_abs_path}")
        
        # Wait for page to be ready
        page.wait_for_load_state("networkidle")
        
        # Generate output filename
        if output_name is None:
            base_name = Path(html_path).stem
            output_name = f"{base_name}_{viewport.name}"
            
        output_path = self.output_dir / f"{output_name}.{options.type}"
        
        # Prepare screenshot options
        screenshot_kwargs = {
            "path": str(output_path),
            "full_page": options.full_page,
            "type": options.type,
            "omit_background": options.omit_background,
            "animations": options.animations,
            "caret": options.caret
        }
        
        if options.clip:
            screenshot_kwargs["clip"] = options.clip
        if options.quality and options.type == "jpeg":
            screenshot_kwargs["quality"] = options.quality
        if options.mask:
            screenshot_kwargs["mask"] = [page.locator(selector) for selector in options.mask]
            screenshot_kwargs["mask_color"] = options.mask_color
        
        # Take screenshot
        page.screenshot(**screenshot_kwargs)
        
        # Get file info
        file_size = output_path.stat().st_size
        timestamp = output_path.stat().st_mtime
        
        # Clean up
        page.close()
        self.context.close()
        self.context = None
        
        return ScreenshotResult(
            path=str(output_path),
            viewport=viewport,
            timestamp=str(timestamp),
            file_size=file_size,
            metadata={
                "html_path": html_path,
                "options": options.__dict__
            }
        )
    
    def capture_multiple_viewports(
        self,
        html_path: str,
        viewports: Optional[List[ViewportConfig]] = None,
        options: Optional[ScreenshotOptions] = None
    ) -> List[ScreenshotResult]:
        """Capture screenshots across multiple viewports.
        
        Parameters
        ----------
        html_path : str
            Path to HTML file to capture
        viewports : List[ViewportConfig], optional
            List of viewports to capture. Defaults to common presets.
        options : ScreenshotOptions, optional
            Screenshot capture options
            
        Returns
        -------
        List[ScreenshotResult]
            Results for all captured screenshots
        """
        if viewports is None:
            viewports = [
                self.VIEWPORT_PRESETS["mobile_portrait"],
                self.VIEWPORT_PRESETS["tablet_portrait"],
                self.VIEWPORT_PRESETS["desktop"],
                self.VIEWPORT_PRESETS["desktop_large"]
            ]
        
        results = []
        for viewport in viewports:
            try:
                result = self.capture_single(html_path, viewport, options)
                results.append(result)
            except Exception as e:
                print(f"Failed to capture {viewport.name}: {e}")
                continue
        
        return results
    
    def capture_element(
        self,
        html_path: str,
        element_selector: str,
        viewport: ViewportConfig,
        options: Optional[ScreenshotOptions] = None,
        output_name: Optional[str] = None
    ) -> ScreenshotResult:
        """Capture a screenshot of a specific element.
        
        Parameters
        ----------
        html_path : str
            Path to HTML file
        element_selector : str
            CSS selector for the element to capture
        viewport : ViewportConfig
            Viewport configuration
        options : ScreenshotOptions, optional
            Screenshot capture options
        output_name : str, optional
            Custom output filename
            
        Returns
        -------
        ScreenshotResult
            Result containing screenshot path and metadata
        """
        if not self.browser:
            raise RuntimeError("Browser not initialized. Use as context manager.")
            
        options = options or ScreenshotOptions()
        
        # Create context and page
        context_options = {
            "viewport": {"width": viewport.width, "height": viewport.height},
            "device_scale_factor": viewport.device_scale_factor,
            "is_mobile": viewport.is_mobile,
            "has_touch": viewport.has_touch,
        }
        
        self.context = self.browser.new_context(**context_options)
        page = self.context.new_page()
        
        # Navigate and wait
        html_abs_path = Path(html_path).resolve()
        page.goto(f"file://{html_abs_path}")
        page.wait_for_load_state("networkidle")
        
        # Find element
        element = page.locator(element_selector)
        if element.count() == 0:
            raise ValueError(f"Element not found: {element_selector}")
        
        # Generate output filename
        if output_name is None:
            base_name = Path(html_path).stem
            element_name = element_selector.replace("#", "").replace(".", "").replace(" ", "_")
            output_name = f"{base_name}_{element_name}_{viewport.name}"
            
        output_path = self.output_dir / f"{output_name}.{options.type}"
        
        # Screenshot the element
        screenshot_kwargs = {
            "path": str(output_path),
            "type": options.type,
            "omit_background": options.omit_background,
            "animations": options.animations,
            "caret": options.caret
        }
        
        if options.quality and options.type == "jpeg":
            screenshot_kwargs["quality"] = options.quality
            
        element.screenshot(**screenshot_kwargs)
        
        # Get file info
        file_size = output_path.stat().st_size
        timestamp = output_path.stat().st_mtime
        
        # Clean up
        page.close()
        self.context.close()
        self.context = None
        
        return ScreenshotResult(
            path=str(output_path),
            viewport=viewport,
            timestamp=str(timestamp),
            file_size=file_size,
            metadata={
                "html_path": html_path,
                "element_selector": element_selector,
                "options": options.__dict__
            }
        )
    
    def capture_before_after(
        self,
        html_path_before: str,
        html_path_after: str,
        viewport: ViewportConfig,
        options: Optional[ScreenshotOptions] = None
    ) -> Tuple[ScreenshotResult, ScreenshotResult]:
        """Capture before and after screenshots for comparison.
        
        Parameters
        ----------
        html_path_before : str
            Path to "before" HTML file
        html_path_after : str
            Path to "after" HTML file
        viewport : ViewportConfig
            Viewport configuration
        options : ScreenshotOptions, optional
            Screenshot capture options
            
        Returns
        -------
        Tuple[ScreenshotResult, ScreenshotResult]
            Results for before and after screenshots
        """
        base_name = Path(html_path_before).stem
        
        before_result = self.capture_single(
            html_path_before, 
            viewport, 
            options,
            f"{base_name}_before_{viewport.name}"
        )
        
        after_result = self.capture_single(
            html_path_after,
            viewport,
            options, 
            f"{base_name}_after_{viewport.name}"
        )
        
        return before_result, after_result
    
    def batch_capture(
        self,
        html_files: List[str],
        viewports: Optional[List[ViewportConfig]] = None,
        options: Optional[ScreenshotOptions] = None
    ) -> Dict[str, List[ScreenshotResult]]:
        """Capture screenshots for multiple HTML files across viewports.
        
        Parameters
        ----------
        html_files : List[str]
            List of HTML file paths
        viewports : List[ViewportConfig], optional
            List of viewports to capture
        options : ScreenshotOptions, optional
            Screenshot capture options
            
        Returns
        -------
        Dict[str, List[ScreenshotResult]]
            Results organized by HTML file path
        """
        results = {}
        
        for html_file in html_files:
            try:
                file_results = self.capture_multiple_viewports(html_file, viewports, options)
                results[html_file] = file_results
                print(f"Captured {len(file_results)} screenshots for {html_file}")
            except Exception as e:
                print(f"Failed to capture {html_file}: {e}")
                results[html_file] = []
                
        return results
    
    def get_viewport_preset(self, name: str) -> ViewportConfig:
        """Get a viewport configuration preset by name.
        
        Parameters
        ----------
        name : str
            Preset name
            
        Returns
        -------
        ViewportConfig
            Viewport configuration
        """
        if name not in self.VIEWPORT_PRESETS:
            available = ", ".join(self.VIEWPORT_PRESETS.keys())
            raise ValueError(f"Unknown preset '{name}'. Available: {available}")
            
        return self.VIEWPORT_PRESETS[name]
    
    def create_custom_viewport(
        self,
        name: str,
        width: int,
        height: int,
        device_scale_factor: float = 1.0,
        is_mobile: bool = False,
        has_touch: bool = False,
        user_agent: Optional[str] = None
    ) -> ViewportConfig:
        """Create a custom viewport configuration.
        
        Parameters
        ----------
        name : str
            Viewport name
        width : int
            Viewport width in pixels
        height : int
            Viewport height in pixels
        device_scale_factor : float
            Device pixel ratio
        is_mobile : bool
            Whether this is a mobile device
        has_touch : bool
            Whether device supports touch
        user_agent : str, optional
            Custom user agent string
            
        Returns
        -------
        ViewportConfig
            Custom viewport configuration
        """
        return ViewportConfig(
            name=name,
            width=width,
            height=height,
            device_scale_factor=device_scale_factor,
            is_mobile=is_mobile,
            has_touch=has_touch,
            user_agent=user_agent
        )


def html_to_image(
    html_path: str, 
    output_path: str, 
    width: int = 800, 
    height: int = 600
) -> None:
    """Backward compatibility function for simple screenshot capture.
    
    Parameters
    ----------
    html_path : str
        Path to HTML file
    output_path : str
        Output screenshot path
    width : int
        Viewport width
    height : int
        Viewport height
    """
    viewport = ViewportConfig("default", width, height)
    
    with ScreenshotManager(str(Path(output_path).parent)) as manager:
        result = manager.capture_single(
            html_path, 
            viewport,
            output_name=Path(output_path).stem
        )