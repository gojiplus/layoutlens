"""Tests for the deterministic layout/geometry scorers (layoutlens.layout).

Unit tests exercise the pure WCAG contrast math against published example pairs
and require no browser. Browser-marked tests run real chromium against small
inline HTML fixtures with one planted defect per class (contrast, overlap,
clipping, viewport protrusion, undersized target) and assert the matching
finding fires with the right measured value — and that a clean page yields none.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from layoutlens.layout import (
    AA_NORMAL_TEXT,
    LayoutFinding,
    LayoutReport,
    LayoutScorer,
    contrast_ratio,
    is_large_text,
    parse_css_color,
    relative_luminance,
)

# ---------------------------------------------------------------------------
# Unit tests: pure WCAG contrast math (no browser).
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestContrastMath:
    """WCAG relative-luminance / contrast-ratio math against published values."""

    def test_extremes(self):
        assert round(contrast_ratio((0, 0, 0), (255, 255, 255)), 2) == 21.0
        assert round(contrast_ratio((255, 255, 255), (255, 255, 255)), 2) == 1.0

    def test_symmetric(self):
        assert contrast_ratio((0, 0, 0), (255, 255, 255)) == contrast_ratio(
            (255, 255, 255), (0, 0, 0)
        )

    def test_published_pair(self):
        # #767676 on white is the canonical 4.54:1 boundary pair.
        ratio = contrast_ratio(parse_css_color("#767676"), parse_css_color("#ffffff"))
        assert round(ratio, 2) == 4.54

    def test_relative_luminance_bounds(self):
        assert relative_luminance((0, 0, 0)) == 0.0
        assert relative_luminance((255, 255, 255)) == pytest.approx(1.0)

    def test_parse_css_color_forms(self):
        assert parse_css_color("#fff") == (255, 255, 255)
        assert parse_css_color("#767676") == (118, 118, 118)
        assert parse_css_color("rgb(118, 118, 118)") == (118, 118, 118)
        assert parse_css_color("rgba(118, 118, 118, 0.5)") == (118, 118, 118)
        with pytest.raises(ValueError, match="unrecognised CSS colour"):
            parse_css_color("not-a-color")

    def test_is_large_text(self):
        assert is_large_text(24, "400") is True
        assert is_large_text(19, "bold") is True
        assert is_large_text(19, "400") is False
        assert is_large_text(16, "700") is False


@pytest.mark.unit
class TestLayoutReport:
    """Report container behaviour (no browser)."""

    def test_ok_and_grouping(self):
        empty = LayoutReport(source="p.html", viewport="desktop", findings=[])
        assert empty.ok is True
        assert "No layout defects" in empty.summary()

        findings = [
            LayoutFinding(
                "contrast",
                "#a",
                [0, 0, 10, 10],
                {"contrast_ratio": 2.0},
                {"min_ratio": 4.5},
                "low",
            ),
            LayoutFinding(
                "contrast",
                "#b",
                [0, 0, 10, 10],
                {"contrast_ratio": 3.0},
                {"min_ratio": 4.5},
                "low",
            ),
            LayoutFinding(
                "overlap",
                "#c",
                [0, 0, 10, 10],
                {"intersection_px2": 500},
                {},
                "overlap",
            ),
        ]
        report = LayoutReport(source="p.html", viewport="desktop", findings=findings)
        assert report.ok is False
        grouped = report.by_class()
        assert len(grouped["contrast"]) == 2
        assert len(grouped["overlap"]) == 1
        assert "contrast: 2" in report.summary()


# ---------------------------------------------------------------------------
# Browser-marked tests: real chromium + planted-defect fixtures.
# ---------------------------------------------------------------------------


def _chromium_available() -> bool:
    """Return True if a headless chromium can be launched."""
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


def _write(tmp_path: Path, name: str, body: str) -> str:
    """Write an HTML doc with ``body`` and return its path as a string."""
    html = f"<!doctype html><html><head><title>{name}</title></head><body>{body}</body></html>"
    path = tmp_path / f"{name}.html"
    path.write_text(html, encoding="utf-8")
    return str(path)


def _scan(path: str) -> LayoutReport:
    scorer = LayoutScorer()
    return asyncio.run(scorer.scan(path))


@pytest.mark.browser
@requires_chromium
class TestLayoutBrowser:
    """Each detector fires on its planted defect; a clean page yields none."""

    def test_contrast_defect(self, tmp_path):
        path = _write(
            tmp_path,
            "contrast",
            '<p id="low" style="color:#aaaaaa;background:#ffffff">faint text</p>'
            '<p id="good" style="color:#111111;background:#ffffff">readable text</p>',
        )
        report = _scan(path)
        contrast = [f for f in report.findings if f.defect_class == "contrast"]
        assert any(f.selector == "#low" for f in contrast), report.summary()
        assert not any(f.selector == "#good" for f in contrast)
        low = next(f for f in contrast if f.selector == "#low")
        assert low.measured["contrast_ratio"] < AA_NORMAL_TEXT
        assert low.wcag_refs == ["wcag143"]

    def test_overlap_defect(self, tmp_path):
        path = _write(
            tmp_path,
            "overlap",
            '<div style="position:relative;height:200px">'
            '<div id="a" style="position:absolute;left:0;top:0;width:100px;height:100px;background:red"></div>'
            '<div id="b" style="position:absolute;left:50px;top:50px;width:100px;height:100px;background:blue"></div>'
            "</div>",
        )
        report = _scan(path)
        overlaps = [f for f in report.findings if f.defect_class == "overlap"]
        assert overlaps, report.summary()
        f = overlaps[0]
        assert {f.selector, f.measured["partner"]} == {"#a", "#b"}
        # 100x100 boxes offset by (50,50) intersect over a 50x50 = 2500px^2 region.
        assert f.measured["intersection_px2"] == 2500

    def test_clipping_defect(self, tmp_path):
        path = _write(
            tmp_path,
            "clip",
            '<div id="clip" style="height:40px;width:200px;overflow:hidden">'
            '<p style="height:300px;margin:0">tall clipped content</p>'
            "</div>",
        )
        report = _scan(path)
        clips = [f for f in report.findings if f.defect_class == "clipping"]
        assert any(f.selector == "#clip" for f in clips), report.summary()
        clip = next(f for f in clips if f.selector == "#clip")
        assert clip.measured["clipped_axis"] == "y"
        assert clip.measured["clipped_px"] > 200

    def test_protrusion_defect(self, tmp_path):
        path = _write(
            tmp_path,
            "protrude",
            '<div id="wide" style="width:3000px;height:20px;background:green"></div>',
        )
        report = _scan(path)
        protrusions = [
            f for f in report.findings if f.defect_class == "viewport-protrusion"
        ]
        assert any(f.selector == "#wide" for f in protrusions), report.summary()
        wide = next(f for f in protrusions if f.selector == "#wide")
        assert wide.measured["overflow_px"] > 0

    def test_left_edge_protrusion(self, tmp_path):
        path = _write(
            tmp_path,
            "protrude_left",
            '<div id="off" style="position:absolute;left:-120px;width:200px;height:20px;background:red"></div>',
        )
        report = _scan(path)
        protrusions = [
            f for f in report.findings if f.defect_class == "viewport-protrusion"
        ]
        assert any(f.selector == "#off" for f in protrusions), report.summary()
        off = next(f for f in protrusions if f.selector == "#off")
        assert off.measured["edge"] == "left"
        assert off.measured["overflow_px"] >= 119

    def test_page_overflow_defect(self, tmp_path):
        path = _write(
            tmp_path,
            "pageflow",
            '<div style="width:3000px;height:20px;background:green"></div>',
        )
        report = _scan(path)
        page_flows = [f for f in report.findings if f.defect_class == "page-overflow"]
        assert page_flows, report.summary()
        assert page_flows[0].selector == "html"
        assert page_flows[0].measured["overflow_px"] > 0

    def test_truncation_defect(self, tmp_path):
        path = _write(
            tmp_path,
            "truncate",
            '<p id="cut" style="width:80px;white-space:nowrap;overflow:hidden;'
            'text-overflow:ellipsis">This sentence is much too long to fit</p>'
            '<p id="fits" style="width:400px;white-space:nowrap;overflow:hidden;'
            'text-overflow:ellipsis">Short</p>',
        )
        report = _scan(path)
        truncated = [f for f in report.findings if f.defect_class == "truncation"]
        assert any(f.selector == "#cut" for f in truncated), report.summary()
        assert not any(f.selector == "#fits" for f in truncated)
        cut = next(f for f in truncated if f.selector == "#cut")
        assert cut.measured["hidden_px"] > 0
        assert "This sentence" in cut.measured["text_preview"]

    def test_target_size_defect(self, tmp_path):
        path = _write(
            tmp_path,
            "target",
            '<a id="tiny" href="#" style="display:inline-block;width:10px;height:10px">x</a>',
        )
        report = _scan(path)
        targets = [f for f in report.findings if f.defect_class == "target-size"]
        assert any(f.selector == "#tiny" for f in targets), report.summary()
        tiny = next(f for f in targets if f.selector == "#tiny")
        assert tiny.measured["width_px"] < 24
        assert tiny.wcag_refs == ["wcag258"]

    def test_clean_page_is_ok(self, tmp_path):
        path = _write(
            tmp_path,
            "clean",
            '<div style="background:#ffffff">'
            '<h1 style="color:#111111">Readable Title</h1>'
            '<p style="color:#222222">A readable paragraph of body text.</p>'
            '<a href="#" style="display:inline-block;padding:12px 20px;color:#123456">A big link</a>'
            "</div>",
        )
        report = _scan(path)
        assert report.ok is True, f"unexpected findings: {report.summary()}"

    def test_computed_style_reader(self, tmp_path):
        from layoutlens.browser import open_page
        from layoutlens.layout import element_geometry, read_computed_styles

        path = _write(
            tmp_path,
            "styles",
            '<h1 id="hd" style="text-align:center;font-weight:700;font-size:32px">Heading</h1>',
        )

        async def _run():
            async with open_page(path) as page:
                styles = await read_computed_styles(
                    page, "#hd", ["text-align", "font-weight"]
                )
                geom = await element_geometry(page, "#hd")
                missing = await read_computed_styles(page, "#nope", ["color"])
                return styles, geom, missing

        styles, geom, missing = asyncio.run(_run())
        assert styles["text-align"] == "center"
        assert styles["font-weight"] == "700"
        assert geom is not None
        assert len(geom) == 4
        assert missing is None
