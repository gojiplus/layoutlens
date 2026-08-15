"""SARIF 2.1.0 output for deterministic accessibility and layout findings.

One emitter shared by the axe-core and layout paths, so
``layoutlens page.html --a11y axe --output sarif`` and
``layoutlens page.html --layout deterministic --output sarif`` both plug
straight into GitHub Code Scanning (upload with
``github/codeql-action/upload-sarif``), where findings appear as annotations
with stable rule ids and over-time tracking.

Only deterministic findings are emitted: they carry a rule id, a selector, and
measured numbers. LLM verdicts have none of those and do not belong in a
static-analysis report.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .api.core import AnalysisResult

SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = (
    "https://docs.oasis-open.org/sarif/sarif/v2.1.0/os/schemas/sarif-schema-2.1.0.json"
)

# axe impact / layout defects -> SARIF level
_AXE_LEVEL = {
    "critical": "error",
    "serious": "error",
    "moderate": "warning",
    "minor": "note",
}


def _artifact_uri(source: str) -> str:
    """A SARIF artifactLocation URI for a page source (URL or file path)."""
    if source.startswith(("http://", "https://", "file://")):
        return source
    return source.replace("\\", "/")


def _a11y_results(result_meta: dict[str, Any], source: str) -> tuple[list, dict]:
    """SARIF results + rules from an ``metadata["a11y"]`` axe report dict."""
    rules: dict[str, dict] = {}
    out = []
    for v in result_meta.get("violations", []):
        rule_id = f"axe/{v['rule_id']}"
        rules.setdefault(
            rule_id,
            {
                "id": rule_id,
                "shortDescription": {"text": v.get("description", v["rule_id"])},
                "helpUri": v.get("help_url")
                or "https://dequeuniversity.com/rules/axe/",
                "properties": {"tags": v.get("wcag_refs", [])},
            },
        )
        for node in v.get("nodes", []) or [{}]:
            selector = ",".join(node.get("target", [])) or "document"
            out.append(
                {
                    "ruleId": rule_id,
                    "level": _AXE_LEVEL.get(v.get("impact", ""), "warning"),
                    "message": {
                        "text": f"{v.get('description', v['rule_id'])} (selector: {selector})"
                    },
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": _artifact_uri(source)}
                            },
                            "logicalLocations": [{"name": selector, "kind": "element"}],
                        }
                    ],
                }
            )
    return out, rules


def _layout_results(result_meta: dict[str, Any], source: str) -> tuple[list, dict]:
    """SARIF results + rules from a ``metadata["layout"]`` report dict."""
    rules: dict[str, dict] = {}
    out = []
    for f in result_meta.get("findings", []):
        rule_id = f"layout/{f['defect_class']}"
        rules.setdefault(
            rule_id,
            {
                "id": rule_id,
                "shortDescription": {
                    "text": f"Deterministic layout defect: {f['defect_class']}"
                },
                "properties": {"tags": f.get("wcag_refs", [])},
            },
        )
        out.append(
            {
                "ruleId": rule_id,
                "level": "warning",
                "message": {
                    "text": f"{f.get('description', f['defect_class'])} "
                    f"(measured: {f.get('measured')}, threshold: {f.get('threshold')})"
                },
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": _artifact_uri(source)}
                        },
                        "logicalLocations": [
                            {"name": f.get("selector", "document"), "kind": "element"}
                        ],
                    }
                ],
            }
        )
    return out, rules


def to_sarif(results: list[AnalysisResult]) -> dict[str, Any]:
    """Build a SARIF 2.1.0 log from deterministic analysis results.

    Args:
        results: Analysis results whose metadata may carry an ``"a11y"``
            (axe report) and/or ``"layout"`` (layout report) block.

    Returns:
        A SARIF log dict, ready for ``json.dumps``.
    """
    from . import __version__

    all_results: list[dict] = []
    all_rules: dict[str, dict] = {}
    for r in results:
        if "a11y" in r.metadata:
            res, rules = _a11y_results(r.metadata["a11y"], r.source)
            all_results.extend(res)
            all_rules.update(rules)
        if "layout" in r.metadata:
            res, rules = _layout_results(r.metadata["layout"], r.source)
            all_results.extend(res)
            all_rules.update(rules)

    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "LayoutLens",
                        "informationUri": "https://github.com/gojiplus/layoutlens",
                        "version": __version__,
                        "rules": sorted(all_rules.values(), key=lambda r: r["id"]),
                    }
                },
                "results": all_results,
            }
        ],
    }
