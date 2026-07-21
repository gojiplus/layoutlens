"""
Type definitions for Browser Use integration.

Provides data classes for validation policies, results, and session recordings.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ValidationTrigger(Enum):
    """When to trigger validation during agent execution."""

    ON_STEP_START = "on_step_start"
    ON_STEP_END = "on_step_end"
    ON_CLICK = "on_click"
    ON_NAVIGATION = "on_navigation"
    ON_FORM_SUBMIT = "on_form_submit"
    ON_ERROR = "on_error"
    MANUAL = "manual"


class ValidationSeverity(Enum):
    """Severity level for validation findings."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class SessionState(Enum):
    """State of a validation session."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class ValidationPolicy:
    """Configuration for when and how to validate during agent execution.

    Attributes:
        capture_on_click: Capture and validate after click actions.
        capture_on_navigation: Capture and validate after navigation.
        capture_on_form_submit: Capture and validate after form submissions.
        capture_on_error: Capture and validate when errors occur.
        capture_interval_steps: Capture every N steps (0 = disabled).
        experts: List of expert personas to use for validation.
        viewport: Viewport for screenshot capture.
        confidence_threshold: Minimum confidence for findings to be included.
        max_concurrent_validations: Maximum concurrent validation requests.
        include_screenshots: Whether to include screenshots in results.
        custom_queries: Additional queries to run on each validation.
    """

    capture_on_click: bool = True
    capture_on_navigation: bool = True
    capture_on_form_submit: bool = True
    capture_on_error: bool = True
    capture_interval_steps: int = 0
    experts: list[str] = field(default_factory=lambda: ["accessibility_expert"])
    viewport: str = "desktop"
    confidence_threshold: float = 0.5
    max_concurrent_validations: int = 3
    include_screenshots: bool = True
    custom_queries: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ValidationFinding:
    """A single finding from validation analysis.

    Attributes:
        issue: Description of the issue found.
        severity: Severity level of the finding.
        expert: Expert persona that identified the issue.
        confidence: Confidence score for this finding.
        location: Visual location or element reference if applicable.
        recommendation: Suggested fix for the issue.
        wcag_reference: WCAG guideline reference if applicable.
        verified: Deterministic cross-check status against axe-core. ``True`` if the
            finding's WCAG reference matches an axe violation, ``False`` if it does
            not, ``None`` if there was no WCAG reference or no axe data to check.
        metadata: Additional context.
    """

    issue: str
    severity: ValidationSeverity
    expert: str
    confidence: float
    location: str | None = None
    recommendation: str | None = None
    wcag_reference: str | None = None
    verified: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ValidationStepResult:
    """Result from validating a single step/state.

    Attributes:
        step_number: Step index in the session.
        trigger: What triggered this validation.
        timestamp: When validation occurred.
        url: URL at time of validation.
        screenshot_path: Path to captured screenshot.
        findings: List of validation findings.
        answer: Overall assessment answer.
        confidence: Overall confidence score.
        reasoning: Detailed reasoning for the assessment.
        action_context: Context about the action that triggered validation.
        execution_time: Time taken for this validation.
        metadata: Additional context.
    """

    step_number: int
    trigger: ValidationTrigger
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))
    url: str = ""
    screenshot_path: str | None = None
    findings: list[ValidationFinding] = field(default_factory=list)
    answer: str = ""
    confidence: float = 0.0
    reasoning: str = ""
    action_context: dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_critical_findings(self) -> bool:
        """Check if this step has any critical findings."""
        return any(f.severity == ValidationSeverity.CRITICAL for f in self.findings)

    @property
    def finding_count_by_severity(self) -> dict[str, int]:
        """Count findings by severity level."""
        counts: dict[str, int] = {}
        for finding in self.findings:
            severity = finding.severity.value
            counts[severity] = counts.get(severity, 0) + 1
        return counts


@dataclass(slots=True)
class ValidationSession:
    """Complete validation session containing multiple steps.

    Attributes:
        session_id: Unique identifier for this session.
        start_time: Session start timestamp.
        end_time: Session end timestamp.
        state: Current state of the session.
        policy: Validation policy used.
        steps: List of validation step results.
        start_url: Initial URL.
        agent_task: Task the agent was performing.
        total_actions: Total number of agent actions.
        validated_actions: Number of actions that were validated.
        metadata: Additional session context.
    """

    session_id: str
    start_time: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))
    end_time: str = ""
    state: SessionState = SessionState.PENDING
    policy: ValidationPolicy = field(default_factory=ValidationPolicy)
    steps: list[ValidationStepResult] = field(default_factory=list)
    start_url: str = ""
    agent_task: str = ""
    total_actions: int = 0
    validated_actions: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        """Calculate session duration in seconds."""
        if not self.end_time:
            return 0.0
        from datetime import datetime

        start = datetime.fromisoformat(self.start_time)
        end = datetime.fromisoformat(self.end_time)
        return (end - start).total_seconds()

    @property
    def total_findings(self) -> int:
        """Total number of findings across all steps."""
        return sum(len(step.findings) for step in self.steps)

    @property
    def findings_by_severity(self) -> dict[str, int]:
        """Aggregate finding counts by severity."""
        counts: dict[str, int] = {}
        for step in self.steps:
            for severity, count in step.finding_count_by_severity.items():
                counts[severity] = counts.get(severity, 0) + count
        return counts

    @property
    def average_confidence(self) -> float:
        """Average confidence across all steps."""
        if not self.steps:
            return 0.0
        return sum(step.confidence for step in self.steps) / len(self.steps)


@dataclass(slots=True)
class SessionRecording:
    """Recording of an agent session for replay.

    Attributes:
        recording_id: Unique identifier for this recording.
        session: The validation session data.
        screenshots: Mapping of step numbers to screenshot paths.
        action_log: Log of all agent actions.
        page_states: HTML/DOM states at each step.
        created_at: When recording was created.
        output_dir: Directory containing recording artifacts.
        metadata: Additional recording context.
    """

    recording_id: str
    session: ValidationSession
    screenshots: dict[int, str] = field(default_factory=dict)
    action_log: list[dict[str, Any]] = field(default_factory=list)
    page_states: dict[int, str] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))
    output_dir: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def save(self, path: str | Path) -> None:
        """Save recording to JSON file."""
        import json
        from dataclasses import asdict

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = asdict(self)
        data["session"]["state"] = self.session.state.value
        data["session"]["policy"]["experts"] = self.session.policy.experts
        for step in data["session"]["steps"]:
            step["trigger"] = (
                step["trigger"].value if isinstance(step["trigger"], ValidationTrigger) else step["trigger"]
            )
            for finding in step["findings"]:
                finding["severity"] = (
                    finding["severity"].value
                    if isinstance(finding["severity"], ValidationSeverity)
                    else finding["severity"]
                )

        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    @classmethod
    def load(cls, path: str | Path) -> SessionRecording:
        """Load recording from JSON file."""
        import json

        with open(path) as f:
            data = json.load(f)

        data["session"]["state"] = SessionState(data["session"]["state"])

        steps = []
        for step_data in data["session"]["steps"]:
            step_data["trigger"] = ValidationTrigger(step_data["trigger"])
            findings = []
            for finding_data in step_data["findings"]:
                finding_data["severity"] = ValidationSeverity(finding_data["severity"])
                findings.append(ValidationFinding(**finding_data))
            step_data["findings"] = findings
            steps.append(ValidationStepResult(**step_data))

        session = ValidationSession(
            session_id=data["session"]["session_id"],
            start_time=data["session"]["start_time"],
            end_time=data["session"]["end_time"],
            state=data["session"]["state"],
            policy=ValidationPolicy(**data["session"]["policy"]),
            steps=steps,
            start_url=data["session"]["start_url"],
            agent_task=data["session"]["agent_task"],
            total_actions=data["session"]["total_actions"],
            validated_actions=data["session"]["validated_actions"],
            metadata=data["session"]["metadata"],
        )

        return cls(
            recording_id=data["recording_id"],
            session=session,
            screenshots=data.get("screenshots", {}),
            action_log=data.get("action_log", []),
            page_states=data.get("page_states", {}),
            created_at=data.get("created_at", ""),
            output_dir=data.get("output_dir", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass(slots=True)
class SessionComparison:
    """Comparison between two validation sessions (e.g., baseline vs current).

    Attributes:
        baseline_id: ID of baseline session.
        current_id: ID of current session.
        new_findings: Findings in current but not baseline.
        resolved_findings: Findings in baseline but not current.
        persistent_findings: Findings in both sessions.
        regression_score: Score indicating regression (0=same, positive=worse).
        summary: Human-readable comparison summary.
        metadata: Additional comparison context.
    """

    baseline_id: str
    current_id: str
    new_findings: list[ValidationFinding] = field(default_factory=list)
    resolved_findings: list[ValidationFinding] = field(default_factory=list)
    persistent_findings: list[ValidationFinding] = field(default_factory=list)
    regression_score: float = 0.0
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "ValidationTrigger",
    "ValidationSeverity",
    "SessionState",
    "ValidationPolicy",
    "ValidationFinding",
    "ValidationStepResult",
    "ValidationSession",
    "SessionRecording",
    "SessionComparison",
]
