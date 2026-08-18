"""Post-run validation for browser-use agent sessions.

Integrates at browser-use's most *stable* seam: the ``AgentHistoryList`` that
``Agent.run()`` returns (its ``urls()``/``screenshot_paths()`` accessors have
been stable across minor versions), rather than the per-step hook API, whose
signature has changed repeatedly. Nothing here imports ``browser_use`` — the
history object is duck-typed — so the integration works with any 0.13.x
release and is testable with a recorded fixture.

Usage::

    from browser_use import Agent
    from layoutlens import LayoutLens
    from layoutlens.integrations.browser_use import validate_agent_run

    history = await Agent(task=..., llm=...).run()
    session = await validate_agent_run(LayoutLens(), history)
    print(session.total_findings)

Each unique URL the agent visited is re-audited live with the keyless
deterministic stack (axe-core WCAG A/AA + geometry/contrast scorers). If
``queries`` are given and an API key is configured, each recorded screenshot is
additionally judged by the vision LLM.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from ...a11y import AxeAuditor
from ...layout import LayoutScorer
from ...logger import get_logger
from .types import (
    SessionState,
    ValidationFinding,
    ValidationSession,
    ValidationSeverity,
    ValidationStepResult,
    ValidationTrigger,
)

if TYPE_CHECKING:
    from ...api.core import LayoutLens

logger = get_logger("integrations.browser_use")

# axe impact -> ValidationSeverity
_AXE_SEVERITY = {
    "critical": ValidationSeverity.CRITICAL,
    "serious": ValidationSeverity.HIGH,
    "moderate": ValidationSeverity.MEDIUM,
    "minor": ValidationSeverity.LOW,
}


@runtime_checkable
class AgentHistoryLike(Protocol):
    """The slice of browser-use's ``AgentHistoryList`` this module reads."""

    def urls(self) -> list[str | None]:
        """Per-step URLs, in order."""
        ...

    def screenshot_paths(
        self, n_last: int | None = None, return_none_if_not_screenshot: bool = True
    ) -> list[str | None]:
        """Per-step screenshot paths, aligned with :meth:`urls`."""
        ...


def _steps_from_history(history: AgentHistoryLike) -> list[tuple[str, str | None]]:
    """Pair each step's URL with its screenshot, deduplicating URLs in order."""
    urls = history.urls()
    shots = history.screenshot_paths()
    if len(shots) < len(urls):
        shots = shots + [None] * (len(urls) - len(shots))

    seen: set[str] = set()
    steps: list[tuple[str, str | None]] = []
    for url, shot in zip(urls, shots, strict=False):
        if not url or url in seen or url.startswith("about:"):
            continue
        seen.add(url)
        steps.append((url, shot))
    return steps


def _steps_from_dir(screenshot_dir: str | Path) -> list[tuple[str, str | None]]:
    """One step per PNG in ``screenshot_dir`` (sorted); URLs unknown."""
    return [("", str(p)) for p in sorted(Path(screenshot_dir).glob("*.png"))]


def _findings_from_a11y(report: Any) -> list[ValidationFinding]:
    """Convert an ``A11yReport``'s violations to validation findings."""
    return [
        ValidationFinding(
            issue=f"axe: {v.rule_id} — {v.description}",
            severity=_AXE_SEVERITY.get(v.impact, ValidationSeverity.MEDIUM),
            expert="axe-core",
            confidence=1.0,
            location=", ".join(",".join(n.get("target", [])) for n in v.nodes[:3]),
            wcag_reference=", ".join(v.wcag_refs) or None,
            verified=True,
            metadata={"rule_id": v.rule_id, "impact": v.impact},
        )
        for v in report.violations
    ]


def _findings_from_layout(report: Any) -> list[ValidationFinding]:
    """Convert a ``LayoutReport``'s findings to validation findings."""
    return [
        ValidationFinding(
            issue=f"layout: {f.defect_class} at {f.selector}",
            severity=ValidationSeverity.MEDIUM,
            expert="layout-scorer",
            confidence=1.0,
            location=f.selector,
            wcag_reference=", ".join(getattr(f, "wcag_refs", []) or []) or None,
            verified=True,
            metadata={"measured": f.measured, "threshold": f.threshold},
        )
        for f in report.findings
    ]


async def validate_agent_run(
    lens: LayoutLens,
    history: AgentHistoryLike | None = None,
    *,
    screenshot_dir: str | Path | None = None,
    checks: tuple[str, ...] = ("a11y", "layout"),
    queries: list[str] | None = None,
    viewport: str = "desktop",
    session_id: str | None = None,
) -> ValidationSession:
    """Validate the pages a browser-use agent visited, after the run.

    Args:
        lens: The LayoutLens client (only needed for LLM ``queries``; the
            deterministic checks are keyless).
        history: The ``AgentHistoryList`` returned by ``Agent.run()``.
        screenshot_dir: Alternative to ``history`` — validate every ``*.png``
            in a directory (no URLs, so deterministic re-audits are skipped
            unless queries are given).
        checks: Deterministic checks to run per visited URL: ``"a11y"``
            (axe-core WCAG A/AA) and/or ``"layout"`` (geometry/contrast).
        queries: Optional natural-language questions run by the vision LLM
            against each recorded screenshot (requires an API key).
        viewport: Viewport for the deterministic re-audits.
        session_id: Session identifier; generated when omitted.

    Returns:
        A ``ValidationSession`` with one step per visited URL (deterministic
        findings) plus one step per screenshot × query (LLM verdicts).

    Raises:
        ValueError: If neither ``history`` nor ``screenshot_dir`` is given.
    """
    if history is None and screenshot_dir is None:
        raise ValueError("Provide either a browser-use history or a screenshot_dir")

    steps = (
        _steps_from_history(history)
        if history is not None
        else _steps_from_dir(screenshot_dir)  # type: ignore[arg-type]
    )

    session = ValidationSession(
        session_id=session_id or f"agent-run-{uuid.uuid4().hex[:8]}",
        state=SessionState.RUNNING,
        start_url=steps[0][0] if steps else "",
        total_actions=len(steps),
    )

    step_number = 0
    for url, shot in steps:
        if url:
            started = time.time()
            findings: list[ValidationFinding] = []
            notes = []
            if "a11y" in checks:
                try:
                    report = await AxeAuditor(run_only=["wcag2a", "wcag2aa"]).audit(
                        url, viewport
                    )
                    findings.extend(_findings_from_a11y(report))
                    notes.append(f"axe: {len(report.violations)} violation(s)")
                except Exception as e:
                    logger.warning("axe re-audit failed for %s: %s", url, e)
                    notes.append(f"axe failed: {e}")
            if "layout" in checks:
                try:
                    report = await LayoutScorer().scan(url, viewport=viewport)
                    findings.extend(_findings_from_layout(report))
                    notes.append(f"layout: {len(report.findings)} defect(s)")
                except Exception as e:
                    logger.warning("layout re-audit failed for %s: %s", url, e)
                    notes.append(f"layout failed: {e}")

            session.steps.append(
                ValidationStepResult(
                    step_number=step_number,
                    trigger=ValidationTrigger.ON_NAVIGATION,
                    url=url,
                    screenshot_path=shot,
                    findings=findings,
                    answer="no issues found" if not findings else "issues found",
                    confidence=1.0,
                    reasoning="; ".join(notes),
                    execution_time=time.time() - started,
                    metadata={"checks": list(checks)},
                )
            )
            step_number += 1

        for query in queries or []:
            if not shot or not Path(shot).exists():
                continue
            started = time.time()
            result = await lens.analyze(shot, query, viewport=viewport)
            session.steps.append(
                ValidationStepResult(
                    step_number=step_number,
                    trigger=ValidationTrigger.MANUAL,
                    url=url,
                    screenshot_path=shot,
                    answer=result.answer,
                    confidence=result.confidence,
                    reasoning=result.reasoning,
                    execution_time=time.time() - started,
                    metadata={"query": query},
                )
            )
            step_number += 1

    session.validated_actions = len(session.steps)
    session.state = SessionState.COMPLETED
    session.end_time = time.strftime("%Y-%m-%dT%H:%M:%S")
    return session
