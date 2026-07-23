"""Shared browser and page lifecycle for LayoutLens.

This module centralizes Playwright browser management so there is a single
place that owns launching chromium, serving local HTML files over a temporary
HTTP server, and yielding a fully loaded :class:`~playwright.async_api.Page`.

Both the screenshot capture path (:mod:`layoutlens.capture`) and the
deterministic accessibility engine (:mod:`layoutlens.a11y`) build on
:func:`open_page` rather than opening browsers themselves.
"""

from __future__ import annotations

import asyncio
import http.server
import socket
import socketserver
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import Page, async_playwright

from .config import ViewportConfig
from .logger import get_logger
from .types import Viewport, ViewportType

logger = get_logger("browser")

# Canonical viewport definitions. This is the single source of truth reused by
# both the capture engine and the accessibility auditor.
VIEWPORTS: dict[str, ViewportConfig] = {
    "desktop": ViewportConfig("desktop", 1920, 1080, 1.0, False, False),
    "laptop": ViewportConfig("laptop", 1366, 768, 1.0, False, False),
    "tablet": ViewportConfig("tablet", 768, 1024, 2.0, True, True),
    "mobile": ViewportConfig("mobile", 375, 667, 2.0, True, True),
    "mobile_landscape": ViewportConfig("mobile_landscape", 667, 375, 2.0, True, True),
    "mobile_portrait": ViewportConfig("mobile_portrait", 375, 667, 2.0, True, True),
}

DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; LayoutLens/1.0)"


def resolve_viewport(viewport: ViewportType) -> ViewportConfig:
    """Resolve a viewport name or enum to its :class:`ViewportConfig`.

    Args:
        viewport: A :class:`~layoutlens.types.Viewport` enum member or a
            viewport name string (e.g. ``"desktop"``, ``"mobile_portrait"``).

    Returns:
        The matching :class:`ViewportConfig`.

    Raises:
        ValueError: If the viewport name is not recognized.
    """
    name = viewport.value if isinstance(viewport, Viewport) else str(viewport)
    if name not in VIEWPORTS:
        raise ValueError(f"Unknown viewport: {name}. Available: {list(VIEWPORTS.keys())}")
    return VIEWPORTS[name]


def _is_url(source: str) -> bool:
    """Return True if ``source`` is an addressable URL (http/https/file)."""
    scheme = urlparse(source).scheme
    return scheme in ("http", "https", "file")


def _find_free_port() -> int:
    """Find and return an available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        return s.getsockname()[1]


def _make_server(html_file_path: Path) -> socketserver.TCPServer:
    """Create (but do not start) an HTTP server that serves ``html_file_path``.

    The server routes ``/`` to the target HTML file and serves any other path
    (CSS, JS, images) statically from the file's parent directory.
    """
    port = _find_free_port()

    class LocalFileHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(html_file_path.parent), **kwargs)

        def do_GET(self):
            match self.path:
                case "/" | "":
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    with open(html_file_path, "rb") as f:
                        self.wfile.write(f.read())
                case _:
                    super().do_GET()

        def log_message(self, format, *args):  # noqa: A002 - stdlib signature
            # Suppress default HTTP server logging.
            return

    return socketserver.TCPServer(("", port), LocalFileHandler)


@asynccontextmanager
async def open_page(
    source: str | Path,
    viewport: ViewportType = "desktop",
    timeout: int = 30000,
) -> AsyncIterator[Page]:
    """Open a loaded Playwright page for a URL or local HTML file.

    Serves the file over a temporary local HTTP server when ``source`` is a
    local path, launches a headless chromium browser with the requested
    viewport emulation, navigates to the page, and yields the loaded
    :class:`~playwright.async_api.Page`. All browser and server resources are
    torn down when the context exits.

    Args:
        source: A URL (``http``/``https``/``file``) or a path to a local HTML file.
        viewport: Viewport name or :class:`~layoutlens.types.Viewport` enum member.
        timeout: Default navigation/action timeout in milliseconds.

    Yields:
        The loaded page, ready for screenshots or script injection.

    Raises:
        ValueError: If the viewport is unknown.
        FileNotFoundError: If ``source`` is a local path that does not exist.
    """
    viewport_config = resolve_viewport(viewport)

    source_str = str(source)
    httpd: socketserver.TCPServer | None = None
    server_thread: threading.Thread | None = None

    if _is_url(source_str):
        target_url = source_str
    else:
        html_file_path = Path(source).resolve()
        if not html_file_path.exists():
            raise FileNotFoundError(f"HTML file not found: {html_file_path}")
        httpd = _make_server(html_file_path)
        port = httpd.server_address[1]
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()
        # Give the server a moment to start accepting connections.
        await asyncio.sleep(0.5)
        target_url = f"http://localhost:{port}/"
        logger.debug(f"Serving {html_file_path} at {target_url}")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context_options = {
                "viewport": {"width": viewport_config.width, "height": viewport_config.height},
                "device_scale_factor": viewport_config.device_scale_factor,
                "is_mobile": viewport_config.is_mobile,
                "has_touch": viewport_config.has_touch,
                "user_agent": viewport_config.user_agent or DEFAULT_USER_AGENT,
            }
            context = await browser.new_context(**context_options)
            page = await context.new_page()
            page.set_default_timeout(timeout)

            await page.goto(target_url, wait_until="networkidle")

            try:
                yield page
            finally:
                await context.close()
                await browser.close()
    finally:
        if httpd is not None:
            httpd.shutdown()
            httpd.server_close()
        if server_thread is not None:
            server_thread.join(timeout=1)
