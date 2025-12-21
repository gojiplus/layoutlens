"""
URL capture system for live website screenshots.

This module handles capturing screenshots from live URLs using Playwright
with support for different viewports and browser configurations.
"""

import asyncio
import hashlib
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from ..logger import get_logger, log_performance_metric

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
        "mobile_landscape": {"width": 667, "height": 375},
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
        self.logger = get_logger("vision.capture")

        if not PLAYWRIGHT_AVAILABLE:
            self.logger.error("Playwright not available")
            raise ImportError("Playwright not available. Run: pip install playwright && playwright install")

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout

        self.logger.info(f"URLCapture initialized - output_dir: {output_dir}, timeout: {timeout}ms")
        self.logger.debug(f"Available viewports: {list(self.VIEWPORTS.keys())}")

    def capture_url(
        self,
        url: str,
        viewport: str = "desktop",
        wait_for_selector: str | None = None,
        wait_time: int | None = None,
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
        self.logger.info(f"Starting capture: {url} ({viewport})")
        start_time = time.time()

        try:
            # Check if we're already in an event loop
            try:
                asyncio.get_running_loop()
                # We're in an event loop, use run_in_executor to avoid nested loops
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    result = executor.submit(
                        asyncio.run, self._capture_url_async(url, viewport, wait_for_selector, wait_time)
                    ).result()
            except RuntimeError:
                # No event loop running, safe to use asyncio.run
                result = asyncio.run(self._capture_url_async(url, viewport, wait_for_selector, wait_time))

            duration = time.time() - start_time

            log_performance_metric(
                operation="url_capture",
                duration=duration,
                url=url[:50] + "..." if len(url) > 50 else url,
                viewport=viewport,
                success=True,
            )

            self.logger.info(f"Capture successful: {url} -> {result} ({duration:.2f}s)")
            return result

        except Exception as e:
            duration = time.time() - start_time
            log_performance_metric(
                operation="url_capture",
                duration=duration,
                url=url[:50] + "..." if len(url) > 50 else url,
                viewport=viewport,
                success=False,
                error=str(e),
            )
            self.logger.error(f"Capture failed: {url} ({viewport}) - {e}")
            raise

    async def capture_url_async(
        self,
        url: str,
        viewport: str = "desktop",
        wait_for_selector: str | None = None,
        wait_time: int | None = None,
    ) -> str:
        """
        Async version of capture_url for use in async contexts like CLI.

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
        self.logger.info(f"Starting async capture: {url} ({viewport})")
        start_time = time.time()

        try:
            result = await self._capture_url_async(url, viewport, wait_for_selector, wait_time)
            duration = time.time() - start_time

            log_performance_metric(
                operation="url_capture_async",
                duration=duration,
                url=url[:50] + "..." if len(url) > 50 else url,
                viewport=viewport,
                success=True,
            )

            self.logger.info(f"Async capture successful: {url} -> {result} ({duration:.2f}s)")
            return result

        except Exception as e:
            duration = time.time() - start_time
            log_performance_metric(
                operation="url_capture_async",
                duration=duration,
                url=url[:50] + "..." if len(url) > 50 else url,
                viewport=viewport,
                success=False,
                error=str(e),
            )
            self.logger.error(f"Async capture failed: {url} ({viewport}) - {e}")
            raise

    async def _capture_url_async(
        self,
        url: str,
        viewport: str,
        wait_for_selector: str | None,
        wait_time: int | None,
    ) -> str:
        """Async implementation of URL capture."""

        if viewport not in self.VIEWPORTS:
            error_msg = f"Unknown viewport: {viewport}. Available: {list(self.VIEWPORTS.keys())}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)

        viewport_config = self.VIEWPORTS[viewport]

        # Generate unique filename
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:8]
        timestamp = int(time.time())
        filename = f"{self._sanitize_url_for_filename(url)}_{viewport}_{url_hash}_{timestamp}.png"
        screenshot_path = self.output_dir / filename

        self.logger.debug(f"Generated screenshot path: {screenshot_path}")
        self.logger.debug(f"Using viewport config: {viewport_config}")

        async with async_playwright() as p:
            # Launch browser
            self.logger.debug("Launching browser")
            browser = await p.chromium.launch(headless=True)

            # Configure context for mobile if needed
            context_options: dict[str, Any] = {
                "viewport": viewport_config,
                "user_agent": self._get_user_agent(viewport),
            }

            if viewport in ["mobile", "mobile_landscape"]:
                context_options.update({"is_mobile": True, "has_touch": True})
                self.logger.debug("Configured mobile context options")

            context = await browser.new_context(**context_options)
            page = await context.new_page()

            try:
                # Navigate to URL
                self.logger.debug(f"Navigating to URL: {url}")
                await page.goto(url, timeout=self.timeout, wait_until="networkidle")
                self.logger.debug("Page loaded successfully")

                # Wait for specific selector if provided
                if wait_for_selector:
                    self.logger.debug(f"Waiting for selector: {wait_for_selector}")
                    await page.wait_for_selector(wait_for_selector, timeout=10000)

                # Additional wait time if specified
                if wait_time:
                    self.logger.debug(f"Additional wait time: {wait_time}ms")
                    await page.wait_for_timeout(wait_time)

                # Capture full page screenshot
                self.logger.debug(f"Capturing screenshot to: {screenshot_path}")
                await page.screenshot(path=str(screenshot_path), full_page=True, type="png")

                return str(screenshot_path)

            except Exception as e:
                self.logger.error(f"Browser operation failed for {url}: {e}")
                raise RuntimeError(f"Failed to capture screenshot from {url}: {str(e)}") from e

            finally:
                self.logger.debug("Cleaning up browser resources")
                await context.close()
                await browser.close()

    def capture_multiple_viewports(self, url: str, viewports: list | None = None) -> dict[str, str]:
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
        self, urls: list, viewports: list | None = None, max_concurrent: int = 3
    ) -> dict[str, dict[str, str]]:
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
        self, urls: list, viewports: list | None, max_concurrent: int
    ) -> dict[str, dict[str, str]]:
        """Async batch capture implementation."""

        if viewports is None:
            viewports = ["desktop", "mobile"]

        results: dict[str, dict[str, str]] = {}
        semaphore = asyncio.Semaphore(max_concurrent)

        async def capture_single(url: str, viewport: str):
            async with semaphore:
                try:
                    screenshot_path = await self.capture._capture_url_async(url, viewport, None, None)
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
