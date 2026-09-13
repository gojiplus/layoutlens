"""Shared browser and page lifecycle for LayoutLens.

This module centralizes Playwright browser management so there is a single
place that owns launching Chromium, Firefox, and WebKit, serving local HTML files over a temporary
HTTP server, and yielding a fully loaded :class:`~playwright.async_api.Page`.

Both the screenshot capture path (:mod:`layoutlens.capture`) and the
deterministic accessibility engine (:mod:`layoutlens.a11y`) build on
:func:`open_page` rather than opening browsers themselves.
"""

from __future__ import annotations

import asyncio
import http.server
import math
import threading
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlparse

from playwright.async_api import Browser, Page, async_playwright

from .logger import get_logger
from .types import Viewport, ViewportType

if TYPE_CHECKING:
    import socketserver
    from collections.abc import AsyncIterator

logger = get_logger("browser")


@dataclass
class ViewportConfig:
    """Viewport configuration for a capture/audit session."""

    name: str
    width: int
    height: int
    device_scale_factor: float = 1.0
    is_mobile: bool = False
    has_touch: bool = False
    user_agent: str | None = None


BrowserName = Literal["chromium", "firefox", "webkit"]


@dataclass(frozen=True)
class BrowserConfig:
    """Browser and emulation settings shared by captures and scenarios."""

    browser: str = "chromium"
    color_scheme: str = "light"
    reduced_motion: str = "reduce"
    locale: str = "en-US"
    timezone_id: str = "UTC"
    device_scale_factor: float | None = None

    def __post_init__(self) -> None:
        """Reject invalid engines and emulation values before opening a page."""
        if self.browser not in {"chromium", "firefox", "webkit"}:
            raise ValueError(f"unknown browser: {self.browser}")
        if self.color_scheme not in {"light", "dark", "no-preference"}:
            raise ValueError(f"unknown color scheme: {self.color_scheme}")
        if self.reduced_motion not in {"reduce", "no-preference"}:
            raise ValueError(f"unknown reduced motion: {self.reduced_motion}")
        if not self.locale or not self.timezone_id:
            raise ValueError("locale and timezone must be nonempty")
        if self.device_scale_factor is not None and (
            not math.isfinite(self.device_scale_factor) or self.device_scale_factor <= 0
        ):
            raise ValueError("device_scale_factor must be finite and positive")


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


def resolve_viewport(viewport: ViewportType | tuple[int, int]) -> ViewportConfig:
    """Resolve a viewport name or enum to its :class:`ViewportConfig`.

    Args:
        viewport: A :class:`~layoutlens.types.Viewport` enum member or a
            viewport name string (e.g. ``"desktop"``, ``"mobile_portrait"``).

    Returns:
        The matching :class:`ViewportConfig`.

    Raises:
        ValueError: If the viewport name is not recognized.
    """
    if isinstance(viewport, tuple):
        if len(viewport) != 2 or any(type(n) is not int or n <= 0 for n in viewport):
            raise ValueError("viewport dimensions must be positive integers")
        return ViewportConfig("custom", *viewport)
    name = viewport.value if isinstance(viewport, Viewport) else str(viewport)
    if name not in VIEWPORTS:
        raise ValueError(
            f"Unknown viewport: {name}. Available: {list(VIEWPORTS.keys())}"
        )
    return VIEWPORTS[name]


def _is_url(source: str) -> bool:
    """Return True if ``source`` is an addressable URL (http/https/file)."""
    scheme = urlparse(source).scheme
    return scheme in ("http", "https", "file")


def _make_server(html_file_path: Path) -> socketserver.TCPServer:
    """Create (but do not start) an HTTP server that serves ``html_file_path``.

    The server routes ``/`` to the target HTML file and serves any other path
    (CSS, JS, images) statically from the file's parent directory.
    """

    class LocalFileHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(html_file_path.parent), **kwargs)

        def do_GET(self):
            match self.path:
                case "/" | "":
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    with html_file_path.open("rb") as f:
                        self.wfile.write(f.read())
                case _:
                    super().do_GET()

        def log_message(self, format, *args):  # noqa: A002, ARG002
            # Suppress default HTTP server logging.
            return

    return http.server.ThreadingHTTPServer(("127.0.0.1", 0), LocalFileHandler)


@asynccontextmanager
async def open_browser(
    browser_type: str = "chromium",
) -> AsyncIterator[Browser]:
    """Launch one local headless browser to share across several ``open_page`` calls.

    Capturing N sources otherwise launches N browsers; pass the yielded
    browser to ``open_page(..., browser=...)`` to reuse it (each page still
    gets its own isolated context).
    """
    BrowserConfig(browser=browser_type)
    async with async_playwright() as p:
        browser = await getattr(p, browser_type).launch(headless=True)
        try:
            yield browser
        finally:
            await browser.close()


@asynccontextmanager
async def open_page(
    source: str | Path,
    viewport: ViewportType | tuple[int, int] = "desktop",
    timeout: int = 30000,
    browser: Browser | None = None,
    *,
    config: BrowserConfig | None = None,
) -> AsyncIterator[Page]:
    """Open a loaded Playwright page for a URL or local HTML file.

    Serves the file over a temporary local HTTP server when ``source`` is a
    local path, launches the configured headless browser with the requested
    viewport emulation, navigates to the page, and yields the loaded
    :class:`~playwright.async_api.Page`. All browser and server resources are
    torn down when the context exits.

    Args:
        source: A URL (``http``/``https``/``file``) or a path to a local HTML file.
        viewport: Viewport name or :class:`~layoutlens.types.Viewport` enum member.
        timeout: Default navigation/action timeout in milliseconds.
        browser: Optional already-launched browser to reuse (see
            :func:`open_browser`); when omitted, one is launched and closed
            per call.
        config: Engine, media preferences, locale, timezone, and DPR.

    Yields:
        The loaded page, ready for screenshots or script injection.

    Raises:
        ValueError: If the viewport is unknown.
        FileNotFoundError: If ``source`` is a local path that does not exist.
    """  # noqa: DOC201, DOC403 -- asynccontextmanager wraps this async generator.
    viewport_config = resolve_viewport(viewport)
    config = config or BrowserConfig(
        browser=browser.browser_type.name if browser else "chromium"
    )
    if browser and browser.browser_type.name != config.browser:
        raise ValueError("shared browser does not match the configured engine")

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
        target_url = f"http://127.0.0.1:{port}/"
        logger.debug("Serving %s at %s", html_file_path, target_url)

    context_options = {
        "viewport": {
            "width": viewport_config.width,
            "height": viewport_config.height,
        },
        "device_scale_factor": config.device_scale_factor
        or viewport_config.device_scale_factor,
        "is_mobile": viewport_config.is_mobile and config.browser != "firefox",
        "has_touch": viewport_config.has_touch,
        "color_scheme": config.color_scheme,
        "reduced_motion": config.reduced_motion,
        "locale": config.locale,
        "timezone_id": config.timezone_id,
    }

    if viewport_config.user_agent:
        context_options["user_agent"] = viewport_config.user_agent

    @asynccontextmanager
    async def _run(b: Browser) -> AsyncIterator[Page]:
        context = await b.new_context(**context_options)
        try:
            page = await context.new_page()
            page.set_default_timeout(timeout)
            await page.goto(target_url, wait_until="load")
            yield page
        finally:
            await context.close()

    try:
        if browser is not None:
            # Caller owns the browser lifecycle (see open_browser); only the
            # per-page context is created and torn down here.
            async with _run(browser) as page:
                yield page
        else:
            async with (
                open_browser(config.browser) as own_browser,
                _run(own_browser) as page,
            ):
                yield page
    finally:
        if httpd is not None:
            await asyncio.to_thread(httpd.shutdown)
            httpd.server_close()
        if server_thread is not None:
            server_thread.join(timeout=1)
