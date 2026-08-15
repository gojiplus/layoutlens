"""Structural tests for the SARIF 2.1.0 emitter.

(The emitted logs were additionally validated against the official OASIS
sarif-schema-2.1.0.json; these tests lock in the structure offline.)
"""

from dataclasses import asdict

from layoutlens.a11y.types import A11yFinding, A11yReport
from layoutlens.api.core import AnalysisResult
from layoutlens.layout.types import LayoutFinding, LayoutReport
from layoutlens.sarif import SARIF_VERSION, to_sarif


def _result_with_reports() -> AnalysisResult:
    a11y = A11yReport(
        source="page.html",
        viewport="desktop",
        engine_version="4.10.3",
        violations=[
            A11yFinding(
                rule_id="color-contrast",
                impact="serious",
                wcag_refs=["wcag2aa", "wcag143"],
                description="Elements must meet contrast ratio thresholds",
                help_url="https://dequeuniversity.com/rules/axe/4.10/color-contrast",
                nodes=[{"target": ["#low"], "html": "<p id='low'>x</p>"}],
            )
        ],
        incomplete=[],
        passes_count=10,
    )
    layout = LayoutReport(
        source="page.html",
        viewport="desktop",
        findings=[
            LayoutFinding(
                defect_class="page-overflow",
                selector="html",
                bbox=[0, 0, 3000, 0],
                measured={"overflow_px": 1080},
                threshold={"viewport_width_px": 1920},
                description="page scrolls horizontally",
            )
        ],
    )
    return AnalysisResult(
        source="page.html",
        query="q",
        answer="No",
        confidence=1.0,
        reasoning="r",
        metadata={"a11y": asdict(a11y), "layout": asdict(layout)},
    )


class TestToSarif:
    def test_structure_and_rules(self):
        log = to_sarif([_result_with_reports()])

        assert log["version"] == SARIF_VERSION
        run = log["runs"][0]
        rule_ids = [r["id"] for r in run["tool"]["driver"]["rules"]]
        assert rule_ids == ["axe/color-contrast", "layout/page-overflow"]

        results = run["results"]
        assert len(results) == 2
        by_rule = {r["ruleId"]: r for r in results}
        axe = by_rule["axe/color-contrast"]
        assert axe["level"] == "error"  # serious -> error
        assert "#low" in axe["message"]["text"]
        assert (
            axe["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
            == "page.html"
        )
        assert axe["locations"][0]["logicalLocations"][0]["name"] == "#low"

        layout = by_rule["layout/page-overflow"]
        assert "1080" in layout["message"]["text"]
        assert layout["locations"][0]["logicalLocations"][0]["name"] == "html"

    def test_empty_results_still_valid_shape(self):
        clean = AnalysisResult(
            source="page.html", query="q", answer="Yes", confidence=1.0, reasoning="r"
        )
        log = to_sarif([clean])
        assert log["runs"][0]["results"] == []
        assert log["runs"][0]["tool"]["driver"]["rules"] == []
