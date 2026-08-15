"""Tests for the pytest plugin via pytester (in-process pytest runs)."""

import asyncio
import os
import sys
from pathlib import Path

import pytest

pytest_plugins = ["pytester"]

# Captured before pytester rewrites HOME, so subprocess runs can still find
# the Playwright browser cache.
_REAL_HOME = Path.home()
_BROWSERS_PATH = os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or str(
    _REAL_HOME / "Library" / "Caches" / "ms-playwright"
    if sys.platform == "darwin"
    else _REAL_HOME / ".cache" / "ms-playwright"
)


def _chromium_available() -> bool:
    from playwright.async_api import async_playwright

    async def _check() -> bool:
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                await browser.close()
            return True
        except Exception:
            return False

    return asyncio.run(_check())


requires_chromium = pytest.mark.skipif(
    not _chromium_available(),
    reason="chromium is not available for Playwright",
)


def test_plugin_registers_fixture_and_options(pytester: pytest.Pytester):
    """The entry point loads: fixture resolves, options exist, no key needed."""
    pytester.makepyfile(
        """
        def test_fixture_present(layoutlens):
            assert hasattr(layoutlens, "assert_a11y")
            assert hasattr(layoutlens, "assert_layout")
            assert hasattr(layoutlens, "assert_ui")
        """
    )
    result = pytester.runpytest_subprocess()
    result.assert_outcomes(passed=1)


def test_assert_ui_skips_without_api_key(pytester: pytest.Pytester, monkeypatch):
    """No API key => assert_ui skips instead of failing the suite."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    pytester.makepyfile(
        """
        def test_llm_check(layoutlens):
            layoutlens.assert_ui("page.html", "Is it good?")
        """
    )
    result = pytester.runpytest_subprocess()
    result.assert_outcomes(skipped=1)


def test_assert_ui_skips_with_no_llm_flag(pytester: pytest.Pytester, monkeypatch):
    """--layoutlens-no-llm makes assert_ui skip even with a key set."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    pytester.makepyfile(
        """
        def test_llm_check(layoutlens):
            layoutlens.assert_ui("page.html", "Is it good?")
        """
    )
    result = pytester.runpytest_subprocess("--layoutlens-no-llm")
    result.assert_outcomes(skipped=1)


@pytest.mark.browser
@requires_chromium
class TestKeylessAssertionsEndToEnd:
    """Real chromium, no API key: deterministic assertions pass and fail."""

    def test_assert_layout_fails_on_planted_defect(
        self, pytester: pytest.Pytester, monkeypatch
    ):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", _BROWSERS_PATH)
        pytester.makefile(
            ".html",
            defect=(
                "<html><head><title>d</title></head><body>"
                '<div style="width:3000px;height:20px;background:green"></div>'
                "</body></html>"
            ),
        )
        pytester.makepyfile(
            """
            def test_layout(layoutlens):
                layoutlens.assert_layout("defect.html")
            """
        )
        result = pytester.runpytest_subprocess()
        result.assert_outcomes(failed=1)
        result.stdout.fnmatch_lines(["*page-overflow*measured*"])

    def test_keyless_assertions_pass_on_clean_page(
        self, pytester: pytest.Pytester, monkeypatch
    ):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", _BROWSERS_PATH)
        pytester.makefile(
            ".html",
            clean=(
                "<html lang='en'><head><title>clean page</title></head>"
                "<body style='background:#ffffff'>"
                "<main><h1 style='color:#111111'>Readable</h1>"
                "<p style='color:#222222'>Body text that is readable.</p></main>"
                "</body></html>"
            ),
        )
        pytester.makepyfile(
            """
            def test_clean(layoutlens):
                layoutlens.assert_a11y("clean.html")
                layoutlens.assert_layout("clean.html")
            """
        )
        result = pytester.runpytest_subprocess()
        result.assert_outcomes(passed=1)
