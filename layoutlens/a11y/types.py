"""Dataclasses for deterministic accessibility findings and reports.

These types model the structured output of the axe-core engine after it has
been mapped from raw JSON into typed Python objects. They are intentionally
engine-agnostic so future deterministic engines can reuse the same shapes.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class A11yFinding:
    """A single accessibility rule outcome affecting one or more DOM nodes.

    Attributes:
        rule_id: The axe-core rule identifier (e.g. ``"color-contrast"``).
        impact: Severity as reported by axe: ``"critical"``, ``"serious"``,
            ``"moderate"``, or ``"minor"`` (may be an empty string for
            incomplete results without a determined impact).
        wcag_refs: WCAG / Section 508 tags for the rule (e.g.
            ``["wcag2aa", "wcag143"]``).
        description: Human-readable description of the rule.
        help_url: URL to Deque's documentation for the rule.
        nodes: Affected DOM nodes, each a dict with ``"target"`` (list of
            selectors) and ``"html"`` (truncated outer HTML snippet).
        engine: Name of the engine that produced the finding.
    """

    rule_id: str
    impact: str
    wcag_refs: list[str]
    description: str
    help_url: str
    nodes: list[dict[str, Any]]
    engine: str = "axe-core"


@dataclass(slots=True)
class A11yReport:
    """Structured accessibility report for a single page and viewport.

    Attributes:
        source: The URL or file path that was audited.
        viewport: The viewport name used for the audit.
        engine_version: Version of the underlying engine (e.g. axe-core).
        violations: Findings that definitively fail a rule.
        incomplete: Findings axe could not decide automatically (needs review).
        passes_count: Number of rules that passed.
        timestamp: ISO-8601 timestamp of when the report was created.
    """

    source: str
    viewport: str
    engine_version: str
    violations: list[A11yFinding]
    incomplete: list[A11yFinding]
    passes_count: int
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def ok(self) -> bool:
        """Return True if there are no violations."""
        return len(self.violations) == 0

    def to_json(self) -> str:
        """Serialize the report to an indented JSON string."""
        return json.dumps(asdict(self), indent=2, default=str)

    def summary(self) -> str:
        """Return a compact, human/LLM-readable summary of the report.

        Lists each violation's rule id, impact, WCAG references, the number of
        affected nodes, and a snippet (target selector + HTML) of the first
        affected node.
        """
        header = (
            f"Accessibility report for {self.source} [{self.viewport}] "
            f"(engine axe-core {self.engine_version}): "
            f"{len(self.violations)} violation(s), "
            f"{len(self.incomplete)} incomplete, {self.passes_count} passed."
        )
        if not self.violations:
            return header + " No violations found."

        lines = [header, "Violations:"]
        for finding in self.violations:
            refs = ", ".join(finding.wcag_refs) if finding.wcag_refs else "n/a"
            node_count = len(finding.nodes)
            line = f"- {finding.rule_id} [{finding.impact or 'unknown'}] (WCAG: {refs}) - {node_count} node(s)"
            if finding.nodes:
                first = finding.nodes[0]
                target = first.get("target", [])
                target_str = " ".join(str(t) for t in target) if target else "?"
                snippet = first.get("html", "")
                line += f"; first: {target_str} -> {snippet}"
            lines.append(line)
        return "\n".join(lines)
