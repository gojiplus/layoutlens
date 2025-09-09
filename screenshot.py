"""Utilities for rendering HTML files to screenshots."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - playwright may not be installed
    sync_playwright = None  # type: ignore


def html_to_image(html_path: str, output_path: str, width: int = 800, height: int = 600) -> None:
    """Render an HTML file to ``output_path``.

    This uses Playwright's headless Chromium. The function expects that
    the Playwright browsers have been installed (``playwright install chromium``).
    """

    if sync_playwright is None:
        raise ImportError("playwright is required for html_to_image")

    html_abs = Path(html_path).resolve()
    out_abs = Path(output_path).resolve()
    out_abs.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_viewport_size({"width": width, "height": height})
        page.goto(f"file://{html_abs}")
        page.screenshot(path=str(out_abs))
        browser.close()
