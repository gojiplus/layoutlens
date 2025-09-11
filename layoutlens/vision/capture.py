"""
URL capture system for live website screenshots.

This module handles capturing screenshots from live URLs using Playwright
with support for different viewports and browser configurations.
"""

import asyncio
import hashlib
import time
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class URLCapture:
    """
    Capture screenshots from live URLs using Playwright.
    
    Supports multiple viewport sizes, mobile emulation, and
    various browser configurations for comprehensive testing.
    """
    
    VIEWPORTS = {
        "desktop": {"width": 1920, "height": 1080},
        "laptop": {"width": 1366, "height": 768},
        "tablet": {"width": 768, "height": 1024},
        "mobile": {"width": 375, "height": 667},
        "mobile_landscape": {"width": 667, "height": 375}
    }
    
    def __init__(self, output_dir: str = "screenshots", timeout: int = 30000):
        """
        Initialize URL capture system.
        
        Parameters
        ----------
        output_dir : str, default "screenshots"
            Directory to save captured screenshots
        timeout : int, default 30000
            Page load timeout in milliseconds
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright not available. Run: pip install playwright && playwright install")
        
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
    
    def capture_url(
        self,
        url: str,
        viewport: str = "desktop",
        wait_for_selector: Optional[str] = None,
        wait_time: Optional[int] = None
    ) -> str:
        """
        Capture screenshot from a URL.
        
        Parameters
        ----------
        url : str
            URL to capture
        viewport : str, default "desktop"
            Viewport size (desktop, laptop, tablet, mobile, mobile_landscape)
        wait_for_selector : str, optional
            CSS selector to wait for before capturing
        wait_time : int, optional
            Additional wait time in milliseconds
            
        Returns
        -------
        str
            Path to captured screenshot
        """
        return asyncio.run(self._capture_url_async(url, viewport, wait_for_selector, wait_time))
    
    async def _capture_url_async(
        self,
        url: str,
        viewport: str,
        wait_for_selector: Optional[str],
        wait_time: Optional[int]
    ) -> str:
        """Async implementation of URL capture."""
        
        if viewport not in self.VIEWPORTS:
            raise ValueError(f"Unknown viewport: {viewport}. Available: {list(self.VIEWPORTS.keys())}")
        
        viewport_config = self.VIEWPORTS[viewport]
        
        # Generate unique filename
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        timestamp = int(time.time())
        filename = f"{self._sanitize_url_for_filename(url)}_{viewport}_{url_hash}_{timestamp}.png"
        screenshot_path = self.output_dir / filename
        
        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(headless=True)
            
            # Configure context for mobile if needed
            context_options = {
                "viewport": viewport_config,
                "user_agent": self._get_user_agent(viewport)
            }
            
            if viewport in ["mobile", "mobile_landscape"]:
                context_options.update({
                    "is_mobile": True,
                    "has_touch": True
                })
            
            context = await browser.new_context(**context_options)
            page = await context.new_page()
            
            try:
                # Navigate to URL
                await page.goto(url, timeout=self.timeout, wait_until="networkidle")
                
                # Wait for specific selector if provided
                if wait_for_selector:
                    await page.wait_for_selector(wait_for_selector, timeout=10000)
                
                # Additional wait time if specified
                if wait_time:
                    await page.wait_for_timeout(wait_time)
                
                # Capture full page screenshot
                await page.screenshot(
                    path=str(screenshot_path),
                    full_page=True,
                    type="png"
                )
                
                return str(screenshot_path)
                
            except Exception as e:
                raise RuntimeError(f"Failed to capture screenshot from {url}: {str(e)}")
                
            finally:
                await context.close()
                await browser.close()
    
    def capture_multiple_viewports(
        self,
        url: str,
        viewports: Optional[list] = None
    ) -> Dict[str, str]:
        """
        Capture screenshots from multiple viewports.
        
        Parameters
        ----------
        url : str
            URL to capture
        viewports : list, optional
            List of viewport names. Defaults to ["desktop", "mobile"]
            
        Returns
        -------
        dict
            Mapping of viewport name to screenshot path
        """
        if viewports is None:
            viewports = ["desktop", "mobile"]
        
        results = {}
        for viewport in viewports:
            try:
                screenshot_path = self.capture_url(url, viewport)
                results[viewport] = screenshot_path
            except Exception as e:
                results[viewport] = f"Error: {str(e)}"
        
        return results
    
    def _sanitize_url_for_filename(self, url: str) -> str:
        """Convert URL to safe filename component."""
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "").replace(".", "_")
        path = parsed.path.replace("/", "_").replace(".", "_")
        
        filename_part = f"{domain}{path}".replace(":", "")
        
        # Truncate if too long
        if len(filename_part) > 50:
            filename_part = filename_part[:50]
        
        return filename_part or "page"
    
    def _get_user_agent(self, viewport: str) -> str:
        """Get appropriate user agent string for viewport."""
        if viewport in ["mobile", "mobile_landscape"]:
            return "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
        elif viewport == "tablet":
            return "Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
        else:
            return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


class BatchCapture:
    """Batch URL capture for multiple URLs and viewports."""
    
    def __init__(self, output_dir: str = "screenshots"):
        self.capture = URLCapture(output_dir)
    
    def capture_url_list(
        self,
        urls: list,
        viewports: Optional[list] = None,
        max_concurrent: int = 3
    ) -> Dict[str, Dict[str, str]]:
        """
        Capture multiple URLs with multiple viewports.
        
        Parameters
        ----------
        urls : list
            List of URLs to capture
        viewports : list, optional
            List of viewport names
        max_concurrent : int, default 3
            Maximum concurrent captures
            
        Returns
        -------
        dict
            Nested dict: {url: {viewport: screenshot_path}}
        """
        return asyncio.run(self._batch_capture_async(urls, viewports, max_concurrent))
    
    async def _batch_capture_async(
        self,
        urls: list,
        viewports: Optional[list],
        max_concurrent: int
    ) -> Dict[str, Dict[str, str]]:
        """Async batch capture implementation."""
        
        if viewports is None:
            viewports = ["desktop", "mobile"]
        
        results = {}
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def capture_single(url: str, viewport: str):
            async with semaphore:
                try:
                    screenshot_path = await self.capture._capture_url_async(
                        url, viewport, None, None
                    )
                    return url, viewport, screenshot_path
                except Exception as e:
                    return url, viewport, f"Error: {str(e)}"
        
        # Create all capture tasks
        tasks = []
        for url in urls:
            for viewport in viewports:
                tasks.append(capture_single(url, viewport))
        
        # Execute all tasks
        task_results = await asyncio.gather(*tasks)
        
        # Organize results
        for url, viewport, result in task_results:
            if url not in results:
                results[url] = {}
            results[url][viewport] = result
        
        return results