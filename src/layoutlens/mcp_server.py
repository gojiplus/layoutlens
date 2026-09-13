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
- ``compare_ui`` returns structured regression evidence without a model.
- ``check_ui`` uses the optional vision LLM.

Requires the extra: ``pip install "layoutlens[mcp]"``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

try:
    from fastmcp import FastMCP
except ImportError as e:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        'The MCP server needs the mcp extra: pip install "layoutlens[mcp]"'
    ) from e

from .api.core import LayoutLens

if TYPE_CHECKING:
    from .regression.policy import GatePolicy

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
    lines.extend(
        f"- {finding['defect_class']} at {finding['selector']}: {finding['description']}"
        for finding in report["findings"]
    )
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
async def compare_ui(
    before: str,
    after: str,
    viewport: str = "desktop",
    policy: str = "qualified",
    browser: str = "chromium",
    color_scheme: str = "light",
    reduced_motion: str = "reduce",
    locale: str = "en-US",
    timezone_id: str = "UTC",
    device_scale_factor: float | None = None,
) -> dict:
    """Compare saved render states or live pages using browser measurements.

    Args:
        before: Baseline artifact path, URL, or HTML file.
        after: Candidate artifact path, URL, or HTML file.
        viewport: Named viewport for live captures.
        policy: qualified, findings, or nothing.
        browser: Local Chromium, Firefox, or WebKit engine.
        color_scheme: Light, dark, or no-preference media emulation.
        reduced_motion: Reduce or no-preference media emulation.
        locale: Browser locale.
        timezone_id: IANA timezone name.
        device_scale_factor: Optional DPR override.

    Returns:
        Structured deltas, source evidence, and an explicit gate status.
    """
    import json
    from typing import cast

    if policy not in {"qualified", "findings", "nothing"}:
        raise ValueError("unknown gate policy")
    result = await LayoutLens(
        browser=browser,
        color_scheme=color_scheme,
        reduced_motion=reduced_motion,
        locale=locale,
        timezone_id=timezone_id,
        device_scale_factor=device_scale_factor,
    ).compare(before, after, viewport=viewport, policy=cast("GatePolicy", policy))
    return json.loads(result.to_json())


@mcp.tool
async def capture_render_state(
    source: str,
    directory: str,
    viewport: str = "desktop",
    browser: str = "chromium",
    color_scheme: str = "light",
    reduced_motion: str = "reduce",
    locale: str = "en-US",
    timezone_id: str = "UTC",
    device_scale_factor: float | None = None,
) -> dict:
    """Save browser evidence in a new artifact directory.

    Args:
        source: Page URL or local HTML file.
        directory: New directory; existing baselines are not overwritten.
        viewport: Named viewport.
        browser: Local Chromium, Firefox, or WebKit engine.
        color_scheme: Light, dark, or no-preference media emulation.
        reduced_motion: Reduce or no-preference media emulation.
        locale: Browser locale.
        timezone_id: IANA timezone name.
        device_scale_factor: Optional DPR override.

    Returns:
        Artifact location and capture completeness information.
    """
    from .regression.capture import capture_state

    state = await capture_state(
        source,
        viewport=viewport,
        browser=browser,
        color_scheme=color_scheme,
        reduced_motion=reduced_motion,
        locale=locale,
        timezone_id=timezone_id,
        device_scale_factor=device_scale_factor,
    )
    return {
        "artifact": str(state.save(directory)),
        "stable": state.stable,
        "coverage_gaps": state.coverage_gaps,
    }


@mcp.tool
async def run_ui_scenario(
    definition: dict,
    directory: str,
    browser: str = "chromium",
    viewport: str = "desktop",
    color_scheme: str = "light",
    reduced_motion: str = "reduce",
    locale: str = "en-US",
    timezone_id: str = "UTC",
    device_scale_factor: float | None = None,
    timeout: int = 30000,
    policy: str = "qualified",
) -> dict:
    """Run declared interactions and save checkpoint artifacts and ordered evidence."""
    import json

    from .scenarios import Scenario

    report = await Scenario.from_dict(definition).run(
        browser=browser,
        viewport=viewport,
        color_scheme=color_scheme,
        reduced_motion=reduced_motion,
        locale=locale,
        timezone_id=timezone_id,
        device_scale_factor=device_scale_factor,
        timeout=timeout,
        policy=cast("GatePolicy", policy),
    )
    artifact = report.save(directory)
    return {"artifact": str(artifact), **json.loads(report.to_json())}


def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
