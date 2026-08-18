"""LayoutLens MCP server: deterministic UI checks as agent tools.

Run with ``layoutlens-mcp`` (or ``uvx --from "layoutlens[mcp]" layoutlens-mcp``)
and register it with any MCP client (Claude Code, Cursor, ...).

Design notes:

- ``audit_accessibility`` and ``scan_layout`` are **keyless and deterministic**
  — they return measured numbers, not model opinions, and need no API key.
  They cover exactly what accessibility-tree snapshots (playwright-mcp) can't
  see: pixel layout, contrast, clipping, overflow.
- Responses are compact, pre-grouped summaries — never raw axe JSON dumps —
  so they cost the calling agent hundreds of tokens, not tens of thousands.
- ``check_ui``/``compare_ui`` use the vision LLM and return a clear error
  string when no API key is configured.

Requires the extra: ``pip install "layoutlens[mcp]"``.
"""

from __future__ import annotations

from typing import Any

try:
    from fastmcp import FastMCP
except ImportError as e:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        'The MCP server needs the mcp extra: pip install "layoutlens[mcp]"'
    ) from e

from .api.core import LayoutLens

mcp: Any = FastMCP(
    "LayoutLens",
    instructions=(
        "Deterministic UI checks (axe-core accessibility, geometry/contrast "
        "layout) plus optional vision-LLM questions. The deterministic tools "
        "return measured facts and need no API key."
    ),
)

_lens: LayoutLens | None = None


def _get_lens() -> LayoutLens:
    global _lens
    if _lens is None:
        _lens = LayoutLens()
    return _lens


@mcp.tool
async def audit_accessibility(url: str, compliance_level: str = "AA") -> str:
    """Deterministic axe-core WCAG audit of a page. Keyless; measured facts.

    Args:
        url: Page URL or local HTML file path.
        compliance_level: WCAG level to audit: A, AA (default), or AAA.

    Returns:
        Compact summary: violation count, each violated rule with impact and
        first affected selectors, and the passes count.
    """
    result = await _get_lens().check_accessibility(
        url, compliance_level=compliance_level, mode="axe"
    )
    report = result.metadata["a11y"]
    lines = [result.answer]
    for v in report["violations"]:
        targets = "; ".join(",".join(n.get("target", [])) for n in v["nodes"][:3])
        more = len(v["nodes"]) - 3
        suffix = f" (+{more} more)" if more > 0 else ""
        lines.append(f"- {v['rule_id']} [{v['impact']}]: {targets}{suffix}")
    lines.append(
        f"passes: {report['passes_count']} rules; engine: {result.metadata['engine']}"
    )
    return "\n".join(lines)


@mcp.tool
async def scan_layout(url: str, viewport: str = "desktop") -> str:
    """Deterministic geometry, contrast, target-spacing, focus, and text-occlusion scan. Keyless.

    Args:
        url: Page URL or local HTML file path.
        viewport: desktop, laptop, tablet, or mobile.

    Returns:
        Compact summary with each measured defect: class, selector, and the
        numbers behind it (e.g. contrast ratio, overflow px).
    """
    result = await _get_lens().check_layout(
        url, viewport=viewport, mode="deterministic"
    )
    report = result.metadata["layout"]
    lines = [result.answer + f" [{viewport}]"]
    for f in report["findings"]:
        lines.append(f"- {f['defect_class']} at {f['selector']}: {f['description']}")
    return "\n".join(lines)


@mcp.tool
async def check_ui(url: str, question: str, viewport: str = "desktop") -> str:
    """Ask the vision LLM a natural-language question about a rendered page.

    Args:
        url: Page URL, local HTML file, or screenshot path.
        question: The yes/no question to answer about the page.
        viewport: desktop, laptop, tablet, or mobile.

    Returns:
        The model's answer with confidence and reasoning, or an error when no
        API key is configured (the deterministic tools work without one).
    """
    lens = _get_lens()
    try:
        result = await lens.analyze(url, question, viewport=viewport)
    except Exception as e:
        return f"error: {e}"
    return (
        f"answer: {result.answer}\n"
        f"confidence: {result.confidence:.2f}\n"
        f"reasoning: {result.reasoning}"
    )


@mcp.tool
async def compare_ui(url_a: str, url_b: str, question: str) -> str:
    """Compare two pages/screenshots with the vision LLM.

    Args:
        url_a: First page URL, HTML file, or screenshot.
        url_b: Second page URL, HTML file, or screenshot.
        question: What to compare (e.g. "Which is more accessible?").

    Returns:
        The model's comparative answer with confidence and reasoning.
    """
    lens = _get_lens()
    try:
        result = await lens.compare([url_a, url_b], question)
    except Exception as e:
        return f"error: {e}"
    return (
        f"answer: {result.answer}\n"
        f"confidence: {result.confidence:.2f}\n"
        f"reasoning: {result.reasoning}"
    )


def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
