"""Keyless deterministic layout checks: LayoutScorer and check_layout.

Everything here runs with NO API key and NO LLM — the browser's own layout
engine does the measuring, so results are exact and reproducible.
"""

import asyncio

from layoutlens import LayoutLens, LayoutScorer, contrast_ratio
from layoutlens.layout import parse_css_color


async def raw_scan():
    """Scan a page with the scorer directly — no LayoutLens client needed."""
    report = await LayoutScorer().scan("page.html", viewport="mobile")

    print(report.summary())
    for finding in report.findings:
        # Every finding is a receipt: selector, bbox, measured value, threshold.
        print(
            f"{finding.defect_class:20s} {finding.selector:30s} "
            f"measured={finding.measured} threshold={finding.threshold}"
        )


async def check_with_verdict():
    """check_layout wraps the scan in a yes/no verdict (still keyless)."""
    lens = LayoutLens()  # no API key required for deterministic mode

    result = await lens.check_layout("page.html", mode="deterministic")
    print(result.answer)  # "Yes — ... no defects" / "No — ... N defect(s): ..."
    print(result.reasoning)

    # Hybrid mode (needs a key): the scan grounds the vision model, and any
    # MEASURED defect forces the verdict to "no" regardless of the model.
    # result = await lens.check_layout("page.html", mode="hybrid")


def pure_math():
    """The WCAG contrast math is importable on its own — no browser at all."""
    ratio = contrast_ratio(parse_css_color("#767676"), parse_css_color("#ffffff"))
    print(f"#767676 on white: {ratio:.2f}:1 (AA normal-text minimum is 4.5:1)")


if __name__ == "__main__":
    asyncio.run(raw_scan())
    pure_math()
