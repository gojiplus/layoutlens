"""Dataclasses for deterministic layout/geometry findings and reports.

These mirror the shapes in :mod:`layoutlens.a11y.types` (``A11yFinding`` /
``A11yReport``) but model visual defects measured directly off a rendered page —
overlap, clipping, viewport protrusion, undersized targets, low text contrast,
focus obscuration, and text occlusion — rather than axe rule outcomes. Each finding carries the
*measured* numbers and the *threshold* it violated (its "receipt"), so a result
is inspectable and reproducible without an LLM or an API key.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

# Defect-class identifiers used across the layout scorers.
CONTRAST = "contrast"
OVERLAP = "overlap"
CLIPPING = "clipping"
PROTRUSION = "viewport-protrusion"
TARGET_SIZE = "target-size"
PAGE_OVERFLOW = "page-overflow"
TRUNCATION = "truncation"
FOCUS_OBSCURED = "focus-obscured"
TEXT_OCCLUSION = "text-occlusion"


@dataclass(slots=True)
class LayoutFinding:
    """A single measured layout defect affecting one or two DOM elements.

    Attributes:
        defect_class: Stable finding class such as ``"contrast"``, ``"overlap"``,
            ``"clipping"``, ``"viewport-protrusion"``, ``"target-size"``,
            ``"focus-obscured"``, or ``"text-occlusion"``.
        selector: A best-effort CSS selector locating the offending element
            (for overlap, the primary element; the partner is in ``measured``).
        bbox: The element's rounded ``[x, y, width, height]`` in CSS pixels.
        measured: The measured numbers behind the finding (e.g. the contrast
            ratio, the intersection area, the overflow in pixels).
        threshold: The threshold(s) the measurement violated.
        description: A human/LLM-readable one-line description.
        wcag_refs: Relevant WCAG success-criterion tags where the defect maps
            to one (contrast -> ``wcag143``, target-size -> ``wcag258``); empty
            for the ReDeCheck-style geometric defects that are not WCAG SCs.
    """

    defect_class: str
    selector: str
    bbox: list[int]
    measured: dict[str, Any]
    threshold: dict[str, Any]
    description: str
    wcag_refs: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LayoutReport:
    """Structured deterministic layout report for a single page and viewport.

    Attributes:
        source: The URL or file path that was scanned.
        viewport: The viewport name used for the scan.
        findings: All measured layout defects, in detector order.
        timestamp: ISO-8601 timestamp of when the report was created.
    """

    source: str
    viewport: str
    findings: list[LayoutFinding]
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def ok(self) -> bool:
        """Return True if there are no findings."""
        return len(self.findings) == 0

    def by_class(self) -> dict[str, list[LayoutFinding]]:
        """Group findings by their ``defect_class``."""
        grouped: dict[str, list[LayoutFinding]] = {}
        for finding in self.findings:
            grouped.setdefault(finding.defect_class, []).append(finding)
        return grouped

    def to_json(self) -> str:
        """Serialize the report to an indented JSON string."""
        return json.dumps(asdict(self), indent=2, default=str)

    def summary(self) -> str:
        """Return a compact, human/LLM-readable summary of the report."""
        grouped = self.by_class()
        header = (
            f"Layout report for {self.source} [{self.viewport}]: "
            f"{len(self.findings)} finding(s) across {len(grouped)} class(es)."
        )
        if not self.findings:
            return header + " No layout defects found."

        lines = [header, "Findings:"]
        for defect_class, findings in grouped.items():
            first = findings[0]
            lines.append(
                f"- {defect_class}: {len(findings)} - first: {first.selector} ({first.description})"
            )
        return "\n".join(lines)
