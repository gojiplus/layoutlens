"""Tests for the deterministic accessibility engine (layoutlens.a11y).

Unit tests exercise the axe-JSON -> dataclass mapping with a hand-written dict
mimicking ``axe.run`` output and require no browser. Browser-marked tests run
real chromium with the vendored axe-core bundle against local HTML fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from layoutlens.a11y import AXE_VERSION, A11yFinding, A11yReport, AxeAuditor

FIXTURE_DIR = Path(__file__).parent.parent / "benchmarks" / "test_data" / "accessibility"
VIOLATIONS_HTML = FIXTURE_DIR / "wcag_violations.html"
COMPLIANT_HTML = FIXTURE_DIR / "wcag_compliant.html"


def _fake_axe_results() -> dict:
    """A minimal dict mimicking the shape of ``axe.run`` output."""
    long_html = "<div>" + ("x" * 400) + "</div>"
    return {
        "testEngine": {"name": "axe-core", "version": "4.10.3"},
        "violations": [
            {
                "id": "image-alt",
                "impact": "critical",
                "description": "Ensures <img> elements have alternate text",
                "helpUrl": "https://dequeuniversity.com/rules/axe/4.10/image-alt",
                "tags": ["cat.text-alternatives", "wcag2a", "wcag111", "section508"],
                "nodes": [
                    {"target": ["img.logo"], "html": "<img class='logo' src='a.png'>"},
                    {"target": ["#hero > img"], "html": long_html},
                ],
            },
            {
                "id": "color-contrast",
                "impact": "serious",
                "description": "Ensures contrast between text and background",
                "helpUrl": "https://dequeuniversity.com/rules/axe/4.10/color-contrast",
                "tags": ["cat.color", "wcag2aa", "wcag143"],
                "nodes": [
                    {"target": ["p.muted"], "html": "<p class='muted'>hi</p>"},
                ],
            },
        ],
        "incomplete": [
            {
                "id": "aria-valid-attr-value",
                "impact": "moderate",
                "description": "Ensures all ARIA attributes have valid values",
                "helpUrl": "https://dequeuniversity.com/rules/axe/4.10/aria-valid-attr-value",
                "tags": ["cat.aria", "wcag2a", "wcag412"],
                "nodes": [
                    {"target": ["div[aria-labelledby]"], "html": "<div aria-labelledby='x'></div>"},
                ],
            },
        ],
        "passes": [
            {"id": "document-title", "nodes": [{"target": ["html"], "html": "<html>"}]},
            {"id": "html-has-lang", "nodes": [{"target": ["html"], "html": "<html>"}]},
        ],
    }


@pytest.mark.unit
class TestAxeMapping:
    """Unit tests for mapping axe.run JSON into dataclasses (no browser)."""

    def test_build_report_counts(self):
        report = AxeAuditor._build_report(_fake_axe_results(), "page.html", "desktop")
        assert isinstance(report, A11yReport)
        assert len(report.violations) == 2
        assert len(report.incomplete) == 1
        assert report.passes_count == 2
        assert report.source == "page.html"
        assert report.viewport == "desktop"
        assert report.engine_version == "4.10.3"

    def test_finding_fields(self):
        report = AxeAuditor._build_report(_fake_axe_results(), "page.html", "desktop")
        image_alt = next(f for f in report.violations if f.rule_id == "image-alt")
        assert isinstance(image_alt, A11yFinding)
        assert image_alt.impact == "critical"
        assert image_alt.engine == "axe-core"
        assert image_alt.help_url.endswith("image-alt")
        assert "alternate text" in image_alt.description

    def test_wcag_refs_filtering(self):
        report = AxeAuditor._build_report(_fake_axe_results(), "page.html", "desktop")
        image_alt = next(f for f in report.violations if f.rule_id == "image-alt")
        # wcag* and section508 kept; cat.* dropped.
        assert image_alt.wcag_refs == ["wcag2a", "wcag111", "section508"]
        contrast = next(f for f in report.violations if f.rule_id == "color-contrast")
        assert contrast.wcag_refs == ["wcag2aa", "wcag143"]
        assert "cat.color" not in contrast.wcag_refs

    def test_node_html_truncation(self):
        report = AxeAuditor._build_report(_fake_axe_results(), "page.html", "desktop")
        image_alt = next(f for f in report.violations if f.rule_id == "image-alt")
        # Second node had 400+ chars of html; it must be truncated.
        long_node = image_alt.nodes[1]
        assert long_node["target"] == ["#hero > img"]
        assert len(long_node["html"]) <= 205
        assert long_node["html"].endswith("...")
        # Short node is preserved verbatim.
        assert image_alt.nodes[0]["html"] == "<img class='logo' src='a.png'>"

    def test_ok_property(self):
        report = AxeAuditor._build_report(_fake_axe_results(), "page.html", "desktop")
        assert report.ok is False

        clean = AxeAuditor._build_report(
            {"testEngine": {"version": "4.10.3"}, "violations": [], "incomplete": [], "passes": []},
            "clean.html",
            "desktop",
        )
        assert clean.ok is True

    def test_summary_content(self):
        report = AxeAuditor._build_report(_fake_axe_results(), "page.html", "desktop")
        summary = report.summary()
        assert "image-alt" in summary
        assert "color-contrast" in summary
        assert "critical" in summary
        assert "wcag2aa" in summary
        # Node count and first-node target rendered.
        assert "img.logo" in summary

    def test_to_json_round_trip(self):
        report = AxeAuditor._build_report(_fake_axe_results(), "page.html", "desktop")
        raw = report.to_json()
        parsed = json.loads(raw)
        assert parsed["source"] == "page.html"
        assert parsed["engine_version"] == "4.10.3"
        assert len(parsed["violations"]) == 2
        assert parsed["violations"][0]["rule_id"] == "image-alt"
        assert parsed["violations"][0]["nodes"][0]["target"] == ["img.logo"]
        assert parsed["passes_count"] == 2


# ---------------------------------------------------------------------------
# Browser-marked tests: real chromium + vendored axe-core.
# ---------------------------------------------------------------------------


def _chromium_available() -> bool:
    """Return True if a headless chromium can be launched."""
    import asyncio

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


@pytest.mark.browser
@requires_chromium
class TestAxeBrowser:
    """Real chromium audits using the vendored axe-core bundle."""

    def test_audit_violations_fixture(self):
        import asyncio

        auditor = AxeAuditor(run_only=["wcag2a", "wcag2aa"])
        report = asyncio.run(auditor.audit(str(VIOLATIONS_HTML)))

        assert report.engine_version == AXE_VERSION
        assert report.ok is False
        rule_ids = {f.rule_id for f in report.violations}
        # image-alt and color-contrast are genuine axe violations on this fixture.
        for expected in ("image-alt", "color-contrast"):
            assert expected in rule_ids, f"expected {expected} in {sorted(rule_ids)}"
        # NOTE: the fixture's "unlabeled" inputs carry a placeholder, which axe
        # 4.10.3 counts as an accessible name, so the `label` rule PASSES rather
        # than failing. This fixture/axe mismatch is a finding for the later
        # benchmark task (see task report), not something to force here.
        assert "label" not in rule_ids

    def test_audit_compliant_fixture(self):
        import asyncio

        auditor = AxeAuditor(run_only=["wcag2a", "wcag2aa"])
        report = asyncio.run(auditor.audit(str(COMPLIANT_HTML)))

        # The compliant fixture is genuinely clean under axe wcag2a+wcag2aa
        # (the submit button's contrast was fixed to exceed 4.5:1 in Task 5).
        assert report.ok is True, f"unexpected violations: {[f.rule_id for f in report.violations]}"
        assert report.violations == []

    def test_open_page_serves_local_html(self):
        import asyncio

        from layoutlens.browser import open_page

        async def _run() -> str:
            async with open_page(str(COMPLIANT_HTML)) as page:
                return await page.title()

        title = asyncio.run(_run())
        assert title  # A non-empty <title> is readable from the served page.
