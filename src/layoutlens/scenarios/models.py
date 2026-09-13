"""Portable interaction receipts and checkpoint artifacts."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from ..regression.models import DiffReport, Record, RenderState
from ..regression.policy import (
    GatePolicy,  # noqa: TC001 -- Pydantic resolves the alias at runtime
)


class Step(Record):
    """One declarative browser action or explicit expectation."""

    action: Literal[
        "tab",
        "press",
        "type",
        "fill",
        "click",
        "hover",
        "drag",
        "navigate",
        "resize",
        "pointer_move",
        "pointer_down",
        "pointer_up",
        "checkpoint",
        "expect_focus",
        "expect_visible",
        "expect_hidden",
        "expect_url",
        "expect_text",
        "expect_count",
        "expect_style",
        "expect_clickable",
        "expect_tab_reaches",
    ]
    target: str | None = None
    value: Any = None

    @model_validator(mode="after")
    def validate_arguments(self) -> Step:
        """Reject malformed declarative steps before any browser action runs."""
        no_target = {
            "tab",
            "press",
            "type",
            "navigate",
            "resize",
            "pointer_move",
            "pointer_down",
            "pointer_up",
            "expect_url",
        }
        if self.action not in no_target and (
            not isinstance(self.target, str) or not self.target
        ):
            raise ValueError(f"{self.action} requires a target")
        if self.action in no_target and self.target is not None:
            raise ValueError(f"{self.action} does not accept a target")
        strings = {
            "press",
            "type",
            "fill",
            "drag",
            "navigate",
            "expect_url",
            "expect_text",
            "pointer_down",
            "pointer_up",
        }
        if self.action in strings and not isinstance(self.value, str):
            raise ValueError(f"{self.action} requires a string value")
        if (
            self.action in {"press", "drag", "navigate", "expect_url"}
            and not self.value
        ):
            raise ValueError(f"{self.action} requires a nonempty value")
        if self.action == "tab" and type(self.value) is not bool:
            raise ValueError("tab requires a boolean backwards value")
        if self.action in {"expect_count", "expect_tab_reaches"}:
            minimum = 1 if self.action == "expect_tab_reaches" else 0
            if (
                type(self.value) is not int
                or self.value < minimum
                or (self.action == "expect_tab_reaches" and self.value > 1000)
            ):
                raise ValueError("invalid expectation count or Tab bound")
        if self.action in {"resize", "pointer_move"}:
            if (
                not isinstance(self.value, list)
                or len(self.value) != 2
                or any(
                    type(v) not in {int, float} or not math.isfinite(v)
                    for v in self.value
                )
            ):
                raise ValueError("coordinates must contain two finite numbers")
            if self.action == "resize" and any(
                type(v) is not int or v <= 0 for v in self.value
            ):
                raise ValueError("viewport dimensions must be positive integers")
        if self.action in {"pointer_down", "pointer_up"} and self.value not in {
            "left",
            "middle",
            "right",
        }:
            raise ValueError("invalid pointer button")
        if self.action == "expect_style" and (
            not isinstance(self.value, dict)
            or set(self.value) != {"property", "value"}
            or any(not isinstance(v, str) for v in self.value.values())
            or not self.value["property"]
        ):
            raise ValueError("expect_style requires a CSS property and string value")
        if (
            self.action
            in {
                "click",
                "hover",
                "checkpoint",
                "expect_focus",
                "expect_visible",
                "expect_hidden",
                "expect_clickable",
            }
            and self.value is not None
        ):
            raise ValueError(f"{self.action} does not accept a value")
        return self


class Event(Record):
    """An observed event, with run-relative time and the active step index."""

    sequence: int
    step: int
    time_ms: float
    kind: str
    url: str
    detail: dict[str, Any] = Field(default_factory=dict)


class StepResult(Record):
    """Action outcome, focus transition, and measured expectation evidence."""

    index: int
    action: str
    target: str | None = None
    status: Literal["pass", "fail", "error"] = "pass"
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class InteractionFinding(Record):
    """A reproducible observation matching a reviewable interaction predicate."""

    step: int
    defect_class: str
    element: str
    evidence: dict[str, Any]
    exceptions: list[str] = Field(default_factory=list)
    level: Literal["candidate"] = "candidate"


class ScenarioReport(Record):
    """A complete or interrupted run, retaining its ordered evidence."""

    schema_version: Literal[1] = 1
    source: str
    policy: GatePolicy = "qualified"
    definition_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    planned_steps: int = Field(ge=1)
    steps: list[StepResult] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    findings: list[InteractionFinding] = Field(default_factory=list)
    checkpoints: dict[str, RenderState] = Field(default_factory=dict)
    incomplete_reasons: list[str] = Field(default_factory=list)

    @property
    def gate_status(self) -> Literal["pass", "fail", "incomplete"]:
        """Keep execution gaps distinct from failed, explicitly requested contracts."""
        if (
            self.incomplete_reasons
            or len(self.steps) != self.planned_steps
            or any(s.status == "error" for s in self.steps)
            or [s.index for s in self.steps] != list(range(self.planned_steps))
            or [e.sequence for e in self.events] != list(range(len(self.events)))
            or any(e.step < -1 or e.step >= self.planned_steps for e in self.events)
            or any(
                not state.stable or state.coverage_gaps
                for state in self.checkpoints.values()
            )
            or any(
                s.action == "checkpoint" and s.target not in self.checkpoints
                for s in self.steps
            )
        ):
            return "incomplete"
        if self.policy != "nothing" and (
            any(step.status == "fail" for step in self.steps)
            or (self.policy == "findings" and self.findings)
        ):
            return "fail"
        return "pass"

    def to_json(self) -> str:
        """Serialize receipts and checkpoint metadata, excluding screenshot bytes."""
        return json.dumps(
            self.model_dump(mode="json") | {"gate_status": self.gate_status}, indent=2
        )

    def save(self, directory: str | Path) -> Path:
        """Write a new run directory with individually verified checkpoint artifacts."""
        target = Path(directory)
        target.mkdir(parents=True, exist_ok=False)
        payload = self.model_dump(mode="json", exclude={"checkpoints"})
        payload["checkpoints"] = {}
        for index, (name, state) in enumerate(self.checkpoints.items()):
            folder = f"checkpoint-{index:04d}"
            state.save(target / folder)
            payload["checkpoints"][name] = {
                "directory": folder,
                "fingerprint": state.fingerprint,
            }
        path = target / "scenario.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: str | Path) -> ScenarioReport:
        """Load saved receipts and reject corrupt or escaping checkpoint references."""
        manifest = Path(path)
        if manifest.is_dir():
            manifest /= "scenario.json"
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        checkpoints = {}
        for name, reference in payload.pop("checkpoints").items():
            folder = (manifest.parent / reference["directory"]).resolve()
            if folder.parent != manifest.parent.resolve():
                raise ValueError("checkpoint escapes scenario directory")
            state = RenderState.load(folder)
            if state.fingerprint != reference["fingerprint"]:
                raise ValueError(f"checkpoint fingerprint mismatch: {name}")
            checkpoints[name] = state
        return cls.model_validate(payload | {"checkpoints": checkpoints})

    def diff(self, after: ScenarioReport, **options: Any) -> ScenarioDiff:
        """Compare corresponding named checkpoints across two scenario runs."""
        from ..regression.diff import diff

        common = self.checkpoints.keys() & after.checkpoints.keys()
        gaps = [f"before: {reason}" for reason in self.incomplete_reasons]
        gaps.extend(f"after: {reason}" for reason in after.incomplete_reasons)
        if self.gate_status == "incomplete" or after.gate_status == "incomplete":
            gaps.append("scenario execution incomplete")
        if self.checkpoints.keys() != after.checkpoints.keys():
            gaps.append("checkpoint names differ")
        if not common:
            gaps.append("no corresponding checkpoints")
        if self.definition_fingerprint != after.definition_fingerprint:
            gaps.append("scenario definitions differ")
        if [(s.action, s.target) for s in self.steps] != [
            (s.action, s.target) for s in after.steps
        ]:
            gaps.append("scenario action sequences differ")
        return ScenarioDiff(
            checkpoints={
                name: diff(self.checkpoints[name], after.checkpoints[name], **options)
                for name in sorted(common)
            },
            incomplete_reasons=gaps,
            failed_expectations=[
                step.index for step in after.steps if step.status == "fail"
            ],
            transitions=[
                {
                    "step": old.index,
                    "before": old.after.get("focus"),
                    "after": new.after.get("focus"),
                }
                for old, new in zip(self.steps, after.steps, strict=False)
                if old.after.get("focus") != new.after.get("focus")
            ],
        )


class ScenarioDiff(Record):
    """Checkpoint regressions and changed observed focus transitions."""

    checkpoints: dict[str, DiffReport]
    transitions: list[dict[str, Any]] = Field(default_factory=list)
    failed_expectations: list[int] = Field(default_factory=list)
    incomplete_reasons: list[str] = Field(default_factory=list)

    @property
    def gate_status(self) -> Literal["pass", "fail", "incomplete"]:
        """Require comparable complete checkpoints before reporting a passing gate."""
        if self.incomplete_reasons or any(
            r.gate_status == "incomplete" for r in self.checkpoints.values()
        ):
            return "incomplete"
        if self.failed_expectations or any(
            r.gate_status == "fail" for r in self.checkpoints.values()
        ):
            return "fail"
        return "pass"
