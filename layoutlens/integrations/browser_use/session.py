"""
Session recording and replay for Browser Use integration.

Provides SessionRecorder for capturing agent sessions and SessionReplayer
for replaying recordings with validation.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ...api.core import LayoutLens
from ...logger import get_logger
from .types import (
    SessionComparison,
    SessionRecording,
    ValidationFinding,
    ValidationPolicy,
    ValidationSeverity,
    ValidationStepResult,
    ValidationTrigger,
)

if TYPE_CHECKING:
    from playwright.async_api import Page

    from .validator import AgentValidator


class SessionRecorder:
    """Records browser agent sessions for later replay and analysis.

    Captures screenshots, page states, and validation results at each step
    for regression testing and debugging.

    Attributes:
        output_dir: Directory for storing recordings.
        validator: AgentValidator for real-time validation during recording.

    Examples:
        >>> recorder = SessionRecorder(output_dir="recordings")
        >>> async with recorder.record(page) as recording:
        ...     await page.goto("https://example.com")
        ...     await page.click("#button")
        >>> recording.save("session.json")
    """

    def __init__(
        self,
        output_dir: str | Path = "recordings",
        validator: AgentValidator | None = None,
        policy: ValidationPolicy | None = None,
        capture_html: bool = True,
    ):
        """Initialize the SessionRecorder.

        Args:
            output_dir: Directory for storing recording artifacts.
            validator: AgentValidator instance for validation during recording.
            policy: Validation policy if creating new validator.
            capture_html: Whether to capture HTML state at each step.
        """
        self.logger = get_logger("integrations.browser_use.session")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if validator is None:
            from .validator import AgentValidator

            self.validator = AgentValidator(
                policy=policy,
                output_dir=self.output_dir / "validation",
            )
        else:
            self.validator = validator
        self.capture_html = capture_html

        self._current_recording: SessionRecording | None = None
        self._step_counter = 0

        self.logger.info(f"SessionRecorder initialized - output_dir: {self.output_dir}")

    @asynccontextmanager
    async def record(
        self,
        page: Page,
        task_description: str = "",
    ) -> AsyncIterator[SessionRecording]:
        """Context manager for recording a session.

        Args:
            page: Playwright Page to record.
            task_description: Description of what the agent is doing.

        Yields:
            SessionRecording that accumulates data during the session.

        Example:
            >>> async with recorder.record(page, "Login flow test") as recording:
            ...     await page.goto("https://example.com/login")
            ...     await page.fill("#email", "test@example.com")
            ...     await page.click("#submit")
            >>> print(f"Recorded {len(recording.action_log)} actions")
        """
        recording_id = f"recording_{uuid.uuid4().hex[:12]}"
        recording_dir = self.output_dir / recording_id
        recording_dir.mkdir(parents=True, exist_ok=True)

        session = self.validator.start_session(
            start_url=page.url,
            agent_task=task_description,
        )

        recording = SessionRecording(
            recording_id=recording_id,
            session=session,
            output_dir=str(recording_dir),
        )
        self._current_recording = recording
        self._step_counter = 0

        self.logger.info(f"Started recording: {recording_id}")

        try:
            yield recording
        finally:
            await self.validator.end_session()
            recording.session = self.validator.get_session()
            self._current_recording = None
            self.logger.info(
                f"Recording completed: {recording_id} - "
                f"{len(recording.action_log)} actions, "
                f"{len(recording.screenshots)} screenshots"
            )

    async def capture_step(
        self,
        page: Page,
        action_description: str = "",
        action_data: dict[str, Any] | None = None,
    ) -> ValidationStepResult:
        """Capture and validate a single step during recording.

        Args:
            page: Playwright Page at current state.
            action_description: Human-readable description of the action.
            action_data: Structured action data for replay.

        Returns:
            ValidationStepResult from validating this step.
        """
        if self._current_recording is None:
            raise ValueError("No active recording. Use record() context manager.")

        self._step_counter += 1
        recording = self._current_recording

        result = await self.validator.validate_state(
            page,
            trigger=ValidationTrigger.MANUAL,
            action_context={
                "description": action_description,
                "action_data": action_data or {},
            },
        )

        if result.screenshot_path:
            recording.screenshots[self._step_counter] = result.screenshot_path

        if self.capture_html:
            try:
                html_content = await page.content()
                recording.page_states[self._step_counter] = html_content
            except Exception as e:
                self.logger.warning(f"Failed to capture HTML: {e}")

        recording.action_log.append(
            {
                "step": self._step_counter,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "url": page.url,
                "description": action_description,
                "action_data": action_data or {},
            }
        )

        return result


class SessionReplayer:
    """Replays recorded sessions with validation for regression testing.

    Compares validation results against baseline recordings to detect
    regressions or improvements.

    Attributes:
        lens: LayoutLens instance for analysis.
        policy: Validation policy for replay validation.

    Examples:
        >>> replayer = SessionReplayer()
        >>> recording = SessionRecording.load("session.json")
        >>> results = await replayer.replay_with_validation(recording)
        >>> print(f"Found {len(results)} validation results")
    """

    def __init__(
        self,
        lens: LayoutLens | None = None,
        policy: ValidationPolicy | None = None,
        output_dir: str | Path = "replay_output",
    ):
        """Initialize the SessionReplayer.

        Args:
            lens: LayoutLens instance for analysis.
            policy: Validation policy for replay validation.
            output_dir: Directory for storing replay results.
        """
        self.logger = get_logger("integrations.browser_use.session")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.lens = lens or LayoutLens(output_dir=str(self.output_dir / "screenshots"))
        self.policy = policy or ValidationPolicy()

        self.logger.info(f"SessionReplayer initialized - output_dir: {self.output_dir}")

    async def replay_with_validation(
        self,
        recording: SessionRecording,
        experts: list[str] | None = None,
    ) -> list[ValidationStepResult]:
        """Replay a recording and validate each captured state.

        Args:
            recording: SessionRecording to replay.
            experts: Expert personas to use (overrides recording policy).

        Returns:
            List of ValidationStepResult for each step in the recording.
        """
        self.logger.info(f"Replaying recording: {recording.recording_id}")

        results: list[ValidationStepResult] = []
        experts_to_use = experts or recording.session.policy.experts

        for step_num, screenshot_path in sorted(recording.screenshots.items()):
            if not Path(screenshot_path).exists():
                self.logger.warning(f"Screenshot not found: {screenshot_path}")
                continue

            step_start = time.time()
            findings: list[ValidationFinding] = []
            all_answers: list[str] = []
            all_reasoning: list[str] = []
            total_confidence = 0.0

            for expert in experts_to_use:
                try:
                    result = await self.lens.analyze_with_expert(
                        screenshot_path,
                        f"Analyze this page for issues related to {expert.replace('_', ' ')}",
                        expert_persona=expert,
                        viewport=self.policy.viewport,
                    )
                    all_answers.append(f"[{expert}] {result.answer}")
                    all_reasoning.append(f"[{expert}] {result.reasoning}")
                    total_confidence += result.confidence

                    expert_findings = self._extract_findings(result.reasoning, expert, result.confidence)
                    findings.extend(expert_findings)
                except Exception as e:
                    self.logger.warning(f"Expert {expert} analysis failed for step {step_num}: {e}")

            avg_confidence = total_confidence / len(experts_to_use) if experts_to_use else 0.0

            action_log_entry = next(
                (a for a in recording.action_log if a.get("step") == step_num),
                {},
            )

            step_result = ValidationStepResult(
                step_number=step_num,
                trigger=ValidationTrigger.MANUAL,
                url=action_log_entry.get("url", ""),
                screenshot_path=screenshot_path,
                findings=findings,
                answer="\n".join(all_answers),
                confidence=avg_confidence,
                reasoning="\n".join(all_reasoning),
                action_context=action_log_entry.get("action_data", {}),
                execution_time=time.time() - step_start,
            )
            results.append(step_result)

            self.logger.debug(f"Step {step_num} replayed: {len(findings)} findings, confidence {avg_confidence:.2f}")

        self.logger.info(
            f"Replay completed: {len(results)} steps, {sum(len(r.findings) for r in results)} total findings"
        )

        return results

    def _extract_findings(
        self,
        reasoning: str,
        expert: str,
        confidence: float,
    ) -> list[ValidationFinding]:
        """Extract findings from reasoning text."""
        findings: list[ValidationFinding] = []
        reasoning_lower = reasoning.lower()

        severity_keywords = {
            ValidationSeverity.CRITICAL: ["critical", "severe", "major violation", "unusable"],
            ValidationSeverity.HIGH: ["significant", "serious", "major issue", "poor"],
            ValidationSeverity.MEDIUM: ["moderate", "should improve", "could be better"],
            ValidationSeverity.LOW: ["minor", "slight", "small improvement"],
            ValidationSeverity.INFO: ["note", "consider", "suggestion"],
        }

        detected_severity = ValidationSeverity.INFO
        for severity, keywords in severity_keywords.items():
            if any(kw in reasoning_lower for kw in keywords):
                detected_severity = severity
                break

        if confidence < 0.9 or detected_severity != ValidationSeverity.INFO:
            findings.append(
                ValidationFinding(
                    issue=reasoning[:500],
                    severity=detected_severity,
                    expert=expert,
                    confidence=confidence,
                )
            )

        return findings

    async def compare_sessions(
        self,
        baseline: SessionRecording,
        current: SessionRecording,
    ) -> SessionComparison:
        """Compare two session recordings to detect regressions.

        Args:
            baseline: The baseline recording to compare against.
            current: The current recording to check for regressions.

        Returns:
            SessionComparison with new, resolved, and persistent findings.
        """
        self.logger.info(f"Comparing sessions: {baseline.recording_id} vs {current.recording_id}")

        baseline_results = await self.replay_with_validation(baseline)
        current_results = await self.replay_with_validation(current)

        baseline_findings = self._collect_findings(baseline_results)
        current_findings = self._collect_findings(current_results)

        baseline_issues = {f.issue for f in baseline_findings}
        current_issues = {f.issue for f in current_findings}

        new_issues = current_issues - baseline_issues
        resolved_issues = baseline_issues - current_issues
        persistent_issues = baseline_issues & current_issues

        new_findings = [f for f in current_findings if f.issue in new_issues]
        resolved_findings = [f for f in baseline_findings if f.issue in resolved_issues]
        persistent_findings = [f for f in current_findings if f.issue in persistent_issues]

        severity_weights = {
            ValidationSeverity.CRITICAL: 10,
            ValidationSeverity.HIGH: 5,
            ValidationSeverity.MEDIUM: 2,
            ValidationSeverity.LOW: 1,
            ValidationSeverity.INFO: 0,
        }

        new_score = sum(severity_weights.get(f.severity, 0) for f in new_findings)
        resolved_score = sum(severity_weights.get(f.severity, 0) for f in resolved_findings)
        regression_score = new_score - resolved_score

        if regression_score > 0:
            summary = f"Regression detected: {len(new_findings)} new issues (score: +{regression_score})"
        elif regression_score < 0:
            summary = f"Improvement: {len(resolved_findings)} issues resolved (score: {regression_score})"
        else:
            summary = f"No significant change: {len(persistent_findings)} persistent issues"

        comparison = SessionComparison(
            baseline_id=baseline.recording_id,
            current_id=current.recording_id,
            new_findings=new_findings,
            resolved_findings=resolved_findings,
            persistent_findings=persistent_findings,
            regression_score=float(regression_score),
            summary=summary,
            metadata={
                "baseline_steps": len(baseline.screenshots),
                "current_steps": len(current.screenshots),
                "baseline_total_findings": len(baseline_findings),
                "current_total_findings": len(current_findings),
            },
        )

        self.logger.info(f"Comparison complete: {summary}")

        return comparison

    def _collect_findings(
        self,
        results: list[ValidationStepResult],
    ) -> list[ValidationFinding]:
        """Collect all findings from a list of step results."""
        findings: list[ValidationFinding] = []
        for result in results:
            findings.extend(result.findings)
        return findings


__all__ = ["SessionRecorder", "SessionReplayer"]
