"""
Simplified URL capture system for live website screenshots.

Provides a single, clean interface that handles any number of URLs naturally.
"""

import asyncio
import hashlib
import time
from pathlib import Path
from urllib.parse import urlparse

from .browser import VIEWPORTS, open_page
from .logger import get_logger, log_performance_metric


class Capture:
    """
    Simple screenshot capture system using Playwright.

    One method handles everything - single URLs are just lists of 1 item.
    """

    # Reuse the canonical viewport definitions owned by the browser module.
    VIEWPORTS = VIEWPORTS

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
        start_time = time.time()

        async with open_page(url, viewport, timeout=self.timeout) as page:
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
