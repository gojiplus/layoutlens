"""Separate repeatable measurements, verification, and CI qualification."""

from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import Field

from .models import Record

type GatePolicy = Literal["qualified", "findings", "nothing"]


class Qualification(Record):
    """Independent, sealed precision evidence for one versioned rule."""

    rule: str
    rule_version: str
    configuration: dict[str, Any]
    conditions: dict[str, Any]
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    independent: bool
    sealed: bool
    true_positives: int = Field(ge=0)
    false_positives: int = Field(ge=0)
    provenance: str = Field(min_length=1)

    @property
    def precision_interval(self) -> tuple[float, float]:
        """Return the two-sided 95% Wilson interval, including empty samples."""
        n = self.true_positives + self.false_positives
        if not n:
            return (0, 1)
        p = self.true_positives / n
        z = 1.959963984540054
        denominator = 1 + z * z / n
        center = (p + z * z / (2 * n)) / denominator
        radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
        return (max(0, center - radius), min(1, center + radius))

    def qualifies(
        self, rule: str, version: str, configuration: dict, conditions: dict
    ) -> bool:
        """Require exact rule/configuration and applicable capture conditions."""
        return bool(
            self.independent
            and self.sealed
            and self.rule == rule
            and self.rule_version == version
            and self.configuration == configuration
            and self.conditions == conditions
            and self.precision_interval[0] >= 0.99
        )


def gate_decision(
    policy: GatePolicy,
    *,
    regression: bool,
    qualified: bool = False,
    complete: bool = True,
) -> dict[str, Any]:
    """Evaluate blocking without upgrading a finding's evidentiary status."""
    if policy not in {"qualified", "findings", "nothing"}:
        raise ValueError(f"unknown gate policy: {policy}")
    blocks = (
        complete
        and regression
        and (policy == "findings" or (policy == "qualified" and qualified))
    )
    return {
        "qualified": qualified,
        "blocks": blocks,
        "policy": policy,
        "reason": "incomplete evidence"
        if not complete
        else "explicit strict policy"
        if policy == "findings"
        else "independent qualification required"
        if not qualified
        else "independently qualified",
    }


class Verification(Record):
    """Auditable exception resolution or independent support for one finding."""

    state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rule: str
    selector: str
    evidence: str = Field(min_length=1)
    reviewer: str = Field(min_length=1)
    resolved_exceptions: list[str] = Field(default_factory=list)
    independent_support: bool = False

    def supports(self, finding: dict, state_sha256: str) -> bool:
        """Require complete exception resolution and recorded supporting evidence."""
        exceptions = set(finding["measured"].get("manual_review_exceptions", []))
        return bool(
            self.state_sha256 == state_sha256
            and self.rule == finding["defect_class"]
            and self.selector == finding["selector"]
            and exceptions.issubset(self.resolved_exceptions)
            and (exceptions or self.independent_support)
        )
