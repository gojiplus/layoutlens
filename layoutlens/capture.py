"""
Simplified URL capture system for live website screenshots.

Provides a single, clean interface that handles any number of URLs naturally.
"""

import asyncio
import hashlib
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from .config import ViewportConfig
from .logger import get_logger, log_performance_metric


class Capture:
    """
    Simple screenshot capture system using Playwright.

    One method handles everything - single URLs are just lists of 1 item.
    """

    VIEWPORTS = {
        "desktop": ViewportConfig("desktop", 1920, 1080, 1.0, False, False),
        "laptop": ViewportConfig("laptop", 1366, 768, 1.0, False, False),
        "tablet": ViewportConfig("tablet", 768, 1024, 2.0, True, True),
        "mobile": ViewportConfig("mobile", 375, 667, 2.0, True, True),
        "mobile_landscape": ViewportConfig("mobile_landscape", 667, 375, 2.0, True, True),
        "mobile_portrait": ViewportConfig("mobile_portrait", 375, 667, 2.0, True, True),
    }

    def __init__(self, output_dir: str | Path = "screenshots", timeout: int = 30000):
        """Initialize capture system."""

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.logger = get_logger("vision.capture")

        self.logger.info(f"Capture initialized - output_dir: {output_dir}, timeout: {timeout}ms")

    async def screenshots(
        self,
        urls: list[str],
        viewport: str = "desktop",
        max_concurrent: int = 3,
        wait_for_selector: str | None = None,
        wait_time: int | None = None,
    ) -> list[str]:
        """
        Capture screenshots from URLs.

        Simple interface: give it URLs, get back screenshot paths.
        Single URL? Pass a list with 1 item. Multiple URLs? Pass a list.

        Args:
            urls: List of URLs to capture (can be single URL in list)
            viewport: Viewport name (desktop, mobile, etc.)
            max_concurrent: Maximum concurrent captures
            wait_for_selector: CSS selector to wait for
            wait_time: Additional wait time in milliseconds

        Returns:
            List of screenshot paths in same order as input URLs

        Examples:
            # Single URL
            paths = await capture.screenshots(["https://example.com"])
            # Returns: ["/path/to/screenshot.png"]

            # Multiple URLs
            paths = await capture.screenshots(["url1", "url2"])
            # Returns: ["/path1.png", "/path2.png"]
        """
        if viewport not in self.VIEWPORTS:
            available = list(self.VIEWPORTS.keys())
            raise ValueError(f"Unknown viewport: {viewport}. Available: {available}")

        self.logger.info(f"Capturing {len(urls)} URLs with {viewport} viewport")
        start_time = time.time()

        semaphore = asyncio.Semaphore(max_concurrent)

        async def capture_single(url: str) -> str:
            async with semaphore:
                try:
                    return await self._capture_url(url, viewport, wait_for_selector, wait_time)
                except Exception as e:
                    self.logger.warning(f"Failed to capture {url}: {e}")
                    return f"Error: {str(e)}"

        # Execute all captures concurrently
        tasks = [capture_single(url) for url in urls]
        results = await asyncio.gather(*tasks)

        duration = time.time() - start_time

        log_performance_metric(
            operation="screenshots",
            duration=duration,
            url_count=len(urls),
            viewport=viewport,
            max_concurrent=max_concurrent,
            success=all(not result.startswith("Error:") for result in results),
        )

        self.logger.info(f"Captured {len(urls)} screenshots in {duration:.2f}s")
        return results

    async def _capture_url(
        self,
        url: str,
        viewport: str,
        wait_for_selector: str | None = None,
        wait_time: int | None = None,
    ) -> str:
        """Capture a single URL."""
        viewport_config = self.VIEWPORTS[viewport]
        start_time = time.time()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            # Set up proper mobile context with device emulation
            context_options = {
                "viewport": {"width": viewport_config.width, "height": viewport_config.height},
                "device_scale_factor": viewport_config.device_scale_factor,
                "is_mobile": viewport_config.is_mobile,
                "has_touch": viewport_config.has_touch,
                "user_agent": viewport_config.user_agent or "Mozilla/5.0 (compatible; LayoutLens/1.0)",
            }

            context = await browser.new_context(**context_options)

            page = await context.new_page()
            page.set_default_timeout(self.timeout)

            # Navigate to URL
            await page.goto(url, wait_until="networkidle")

            # Wait for specific selector if provided
            if wait_for_selector:
                await page.wait_for_selector(wait_for_selector, timeout=self.timeout)

            # Additional wait time if specified
            if wait_time:
                await page.wait_for_timeout(wait_time)

            # Generate filename and take screenshot
            filename = self._generate_filename(url, viewport)
            screenshot_path = self.output_dir / filename
            await page.screenshot(path=screenshot_path, full_page=True)

            await context.close()
            await browser.close()

            duration = time.time() - start_time
            self.logger.debug(f"Screenshot saved: {screenshot_path} ({duration:.2f}s)")
            return str(screenshot_path)

    def _generate_filename(self, url: str, viewport: str) -> str:
        """Generate a unique filename for the screenshot."""
        parsed = urlparse(url)
        domain = parsed.netloc or "local"
        path = parsed.path or "index"

        # Clean up path for filename
        path = path.strip("/").replace("/", "_")
        if not path:
            path = "index"

        # Create hash for uniqueness (not for security)
        url_hash = hashlib.md5(url.encode(), usedforsecurity=False).hexdigest()[:8]
        timestamp = int(time.time())

        filename = f"{domain}_{path}_{viewport}_{timestamp}_{url_hash}.png"

        # Clean filename
        filename = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
        return filename
