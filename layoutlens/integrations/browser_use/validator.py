"""
AgentValidator for Browser Use integration.

Provides hooks to validate agent actions in real-time using LayoutLens analysis.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ...api.core import AnalysisResult, LayoutLens
from ...logger import get_logger
from ...prompts import Instructions
from ...types import Expert
from .types import (
    SessionState,
    ValidationFinding,
    ValidationPolicy,
    ValidationSession,
    ValidationSeverity,
    ValidationStepResult,
    ValidationTrigger,
)

if TYPE_CHECKING:
    from playwright.async_api import Page


class AgentValidator:
    """Validates browser agent actions using LayoutLens visual analysis.

    Hooks into Browser Use's action loop to provide real-time validation
    of UI states during agent execution.

    Attributes:
        lens: LayoutLens instance for analysis.
        policy: Validation policy configuration.
        session: Current validation session.

    Examples:
        >>> validator = AgentValidator(
        ...     experts=["accessibility_expert", "mobile_expert"],
        ...     policy=ValidationPolicy(capture_on_click=True)
        ... )
        >>> # Get hooks for Browser Use agent
        >>> hooks = validator.get_hooks()
        >>> await agent.run(**hooks)
        >>> # Get validation results
        >>> session = validator.get_session()
        >>> print(f"Found {session.total_findings} issues")
    """

    def __init__(
        self,
        lens: LayoutLens | None = None,
        experts: list[str] | None = None,
        policy: ValidationPolicy | None = None,
        output_dir: str | Path = "validation_output",
    ):
        """Initialize the AgentValidator.

        Args:
            lens: LayoutLens instance. Created with defaults if not provided.
            experts: List of expert personas to use for validation.
            policy: Validation policy configuration.
            output_dir: Directory for storing screenshots and results.
        """
        self.logger = get_logger("integrations.browser_use.validator")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.lens = lens or LayoutLens(output_dir=str(self.output_dir / "screenshots"))

        if experts:
            default_policy = policy or ValidationPolicy()
            self.policy = ValidationPolicy(
                capture_on_click=default_policy.capture_on_click,
                capture_on_navigation=default_policy.capture_on_navigation,
                capture_on_form_submit=default_policy.capture_on_form_submit,
                capture_on_error=default_policy.capture_on_error,
                capture_interval_steps=default_policy.capture_interval_steps,
                experts=experts,
                viewport=default_policy.viewport,
                confidence_threshold=default_policy.confidence_threshold,
                max_concurrent_validations=default_policy.max_concurrent_validations,
                include_screenshots=default_policy.include_screenshots,
                custom_queries=default_policy.custom_queries,
            )
        else:
            self.policy = policy or ValidationPolicy()

        self._session: ValidationSession | None = None
        self._step_counter = 0
        self._validation_semaphore = asyncio.Semaphore(self.policy.max_concurrent_validations)
        self._pending_validations: list[asyncio.Task] = []

        self.logger.info(f"AgentValidator initialized with experts: {self.policy.experts}")

    def _create_session(self, start_url: str = "", agent_task: str = "") -> ValidationSession:
        """Create a new validation session."""
        session_id = f"session_{uuid.uuid4().hex[:12]}"
        return ValidationSession(
            session_id=session_id,
            state=SessionState.RUNNING,
            policy=self.policy,
            start_url=start_url,
            agent_task=agent_task,
        )

    @property
    def session(self) -> ValidationSession | None:
        """Get the current validation session."""
        return self._session

    def get_session(self) -> ValidationSession:
        """Get the current session, raising if none exists."""
        if self._session is None:
            raise ValueError("No active validation session. Call start_session() first.")
        return self._session

    def start_session(self, start_url: str = "", agent_task: str = "") -> ValidationSession:
        """Start a new validation session.

        Args:
            start_url: Initial URL for the session.
            agent_task: Description of the agent's task.

        Returns:
            The newly created ValidationSession.
        """
        self._session = self._create_session(start_url, agent_task)
        self._step_counter = 0
        self._pending_validations = []
        self.logger.info(f"Started validation session: {self._session.session_id}")
        return self._session

    async def end_session(self) -> ValidationSession:
        """End the current validation session.

        Waits for pending validations to complete and finalizes the session.

        Returns:
            The completed ValidationSession.
        """
        if self._session is None:
            raise ValueError("No active validation session to end.")

        if self._pending_validations:
            self.logger.debug(f"Waiting for {len(self._pending_validations)} pending validations")
            await asyncio.gather(*self._pending_validations, return_exceptions=True)

        self._session.end_time = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._session.state = SessionState.COMPLETED
        self.logger.info(
            f"Ended session {self._session.session_id} - "
            f"{len(self._session.steps)} steps, {self._session.total_findings} findings"
        )
        return self._session

    async def validate_state(
        self,
        page: Page,
        trigger: ValidationTrigger = ValidationTrigger.MANUAL,
        action_context: dict[str, Any] | None = None,
    ) -> ValidationStepResult:
        """Validate the current page state.

        Args:
            page: Playwright Page object to capture and analyze.
            trigger: What triggered this validation.
            action_context: Context about the triggering action.

        Returns:
            ValidationStepResult with findings.
        """
        if self._session is None:
            self._session = self._create_session(page.url)

        start_time = time.time()
        self._step_counter += 1
        step_number = self._step_counter

        self.logger.debug(f"Validating step {step_number} ({trigger.value}): {page.url[:50]}...")

        screenshot_path: str | None = None
        if self.policy.include_screenshots:
            screenshot_path = str(self.output_dir / "screenshots" / f"step_{step_number:04d}.png")
            Path(screenshot_path).parent.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=screenshot_path, full_page=True)

        findings: list[ValidationFinding] = []
        all_answers: list[str] = []
        all_reasoning: list[str] = []
        total_confidence = 0.0

        for expert in self.policy.experts:
            try:
                expert_result = await self._analyze_with_expert(
                    screenshot_path or page.url,
                    expert,
                )
                if expert_result:
                    all_answers.append(f"[{expert}] {expert_result.answer}")
                    all_reasoning.append(f"[{expert}] {expert_result.reasoning}")
                    total_confidence += expert_result.confidence

                    expert_findings = self._extract_findings(expert_result, expert)
                    findings.extend(expert_findings)
            except Exception as e:
                self.logger.warning(f"Expert {expert} analysis failed: {e}")

        for custom_query in self.policy.custom_queries:
            try:
                result = await self.lens.analyze(
                    screenshot_path or page.url,
                    custom_query,
                    viewport=self.policy.viewport,
                )
                if isinstance(result, AnalysisResult):
                    all_answers.append(f"[custom] {result.answer}")
                    all_reasoning.append(f"[custom] {result.reasoning}")
                    total_confidence += result.confidence
            except Exception as e:
                self.logger.warning(f"Custom query failed: {e}")

        num_analyses = len(self.policy.experts) + len(self.policy.custom_queries)
        avg_confidence = total_confidence / num_analyses if num_analyses > 0 else 0.0

        filtered_findings = [f for f in findings if f.confidence >= self.policy.confidence_threshold]

        execution_time = time.time() - start_time

        step_result = ValidationStepResult(
            step_number=step_number,
            trigger=trigger,
            url=page.url,
            screenshot_path=screenshot_path,
            findings=filtered_findings,
            answer="\n".join(all_answers),
            confidence=avg_confidence,
            reasoning="\n".join(all_reasoning),
            action_context=action_context or {},
            execution_time=execution_time,
        )

        self._session.steps.append(step_result)
        self._session.validated_actions += 1

        self.logger.info(
            f"Step {step_number} validated: {len(filtered_findings)} findings, "
            f"confidence {avg_confidence:.2f}, time {execution_time:.2f}s"
        )

        return step_result

    async def _analyze_with_expert(
        self,
        source: str,
        expert: str,
    ) -> AnalysisResult | None:
        """Analyze source using a specific expert persona."""
        async with self._validation_semaphore:
            try:
                expert_enum = Expert(expert) if expert in [e.value for e in Expert] else None
                if expert_enum:
                    return await self.lens.analyze_with_expert(
                        source,
                        f"Analyze this page for issues related to {expert.replace('_', ' ')}",
                        expert_persona=expert_enum,
                        viewport=self.policy.viewport,
                    )
                else:
                    instructions = Instructions(expert_persona=expert)
                    result = await self.lens.analyze(
                        source,
                        f"Analyze this page for issues related to {expert.replace('_', ' ')}",
                        viewport=self.policy.viewport,
                        instructions=instructions,
                    )
                    if isinstance(result, AnalysisResult):
                        return result
                    return None
            except Exception as e:
                self.logger.error(f"Analysis with expert {expert} failed: {e}")
                return None

    def _extract_findings(
        self,
        result: AnalysisResult,
        expert: str,
    ) -> list[ValidationFinding]:
        """Extract structured findings from analysis result."""
        findings: list[ValidationFinding] = []

        reasoning = result.reasoning.lower()

        severity_keywords = {
            ValidationSeverity.CRITICAL: [
                "critical",
                "severe",
                "major violation",
                "completely fails",
                "unusable",
                "blocks users",
            ],
            ValidationSeverity.HIGH: [
                "significant",
                "serious",
                "major issue",
                "poor",
                "fails to meet",
                "wcag a ",
            ],
            ValidationSeverity.MEDIUM: [
                "moderate",
                "should improve",
                "could be better",
                "wcag aa",
                "some issues",
            ],
            ValidationSeverity.LOW: [
                "minor",
                "slight",
                "small improvement",
                "wcag aaa",
                "nice to have",
            ],
            ValidationSeverity.INFO: [
                "note",
                "consider",
                "suggestion",
                "best practice",
                "recommendation",
            ],
        }

        detected_severity = ValidationSeverity.INFO
        for severity, keywords in severity_keywords.items():
            if any(kw in reasoning for kw in keywords):
                detected_severity = severity
                break

        import re

        wcag_match = re.search(r"wcag\s*[\d.]+\s*(?:sc\s*)?[\d.]+|wcag\s+[a-z]+", reasoning, re.IGNORECASE)
        wcag_ref = wcag_match.group(0) if wcag_match else None

        if result.confidence < 0.9 or detected_severity != ValidationSeverity.INFO:
            findings.append(
                ValidationFinding(
                    issue=result.answer[:500],
                    severity=detected_severity,
                    expert=expert,
                    confidence=result.confidence,
                    recommendation=self._extract_recommendation(result.reasoning),
                    wcag_reference=wcag_ref,
                    metadata={"full_reasoning": result.reasoning},
                )
            )

        return findings

    def _extract_recommendation(self, reasoning: str) -> str | None:
        """Extract recommendation from reasoning text."""
        recommendation_patterns = [
            r"recommend[ation]*[s]?[:\s]+([^.]+\.)",
            r"should\s+([^.]+\.)",
            r"suggest[ion]*[s]?[:\s]+([^.]+\.)",
            r"fix[:\s]+([^.]+\.)",
            r"improve[ment]*[s]?[:\s]+([^.]+\.)",
        ]

        import re

        for pattern in recommendation_patterns:
            match = re.search(pattern, reasoning, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def get_hooks(self) -> dict[str, Callable[..., Coroutine[Any, Any, None]]]:
        """Get hooks compatible with Browser Use agent.run().

        Returns:
            Dictionary of hook functions to pass to agent.run().

        Example:
            >>> hooks = validator.get_hooks()
            >>> await agent.run(**hooks)
        """

        async def on_step_start(step: Any) -> None:
            """Hook called at the start of each agent step."""
            if self._session is None:
                self.start_session()

            session = self._session
            assert session is not None

            session.total_actions += 1

            if hasattr(step, "page") and step.page:
                page = step.page
                action_type = getattr(step, "action", {}).get("type", "unknown")

                should_validate = False

                if (
                    action_type == "click"
                    and self.policy.capture_on_click
                    or action_type in ("goto", "navigate")
                    and self.policy.capture_on_navigation
                    or action_type == "submit"
                    and self.policy.capture_on_form_submit
                    or (
                        self.policy.capture_interval_steps > 0
                        and session.total_actions % self.policy.capture_interval_steps == 0
                    )
                ):
                    should_validate = True

                if should_validate:
                    task = asyncio.create_task(
                        self.validate_state(
                            page,
                            trigger=ValidationTrigger.ON_STEP_START,
                            action_context={"action": action_type, "step": session.total_actions},
                        )
                    )
                    self._pending_validations.append(task)

        async def on_step_end(step: Any, result: Any) -> None:
            """Hook called at the end of each agent step."""
            if hasattr(step, "page") and step.page:
                page = step.page
                error = getattr(result, "error", None)

                if error and self.policy.capture_on_error:
                    task = asyncio.create_task(
                        self.validate_state(
                            page,
                            trigger=ValidationTrigger.ON_ERROR,
                            action_context={"error": str(error)},
                        )
                    )
                    self._pending_validations.append(task)

        return {
            "on_step_start": on_step_start,
            "on_step_end": on_step_end,
        }

    async def validate_after_action(
        self,
        page: Page,
        action_description: str = "",
    ) -> ValidationStepResult:
        """Manually validate after a specific action.

        Args:
            page: Playwright Page to validate.
            action_description: Description of the action just performed.

        Returns:
            ValidationStepResult with findings.
        """
        return await self.validate_state(
            page,
            trigger=ValidationTrigger.MANUAL,
            action_context={"description": action_description},
        )

    async def audit_flow(
        self,
        page: Page,
        steps: list[Callable[[Page], Coroutine[Any, Any, None]]],
    ) -> list[ValidationStepResult]:
        """Execute and validate a sequence of steps.

        Args:
            page: Playwright Page to use.
            steps: List of async functions that perform actions on the page.

        Returns:
            List of ValidationStepResult for each step.

        Example:
            >>> async def click_login(page):
            ...     await page.click("#login-button")
            >>> async def fill_form(page):
            ...     await page.fill("#email", "test@example.com")
            >>> results = await validator.audit_flow(page, [click_login, fill_form])
        """
        if self._session is None:
            self.start_session(page.url, "Flow audit")

        results: list[ValidationStepResult] = []

        for i, step_fn in enumerate(steps):
            self.logger.debug(f"Executing audit step {i + 1}/{len(steps)}")

            await step_fn(page)

            await page.wait_for_load_state("networkidle")

            result = await self.validate_state(
                page,
                trigger=ValidationTrigger.MANUAL,
                action_context={"step_index": i, "total_steps": len(steps)},
            )
            results.append(result)

        return results

    async def run_with_validation(
        self,
        agent: Any,
        task: str | None = None,
    ) -> ValidationSession:
        """Run a Browser Use agent with validation hooks.

        Args:
            agent: Browser Use agent instance.
            task: Optional task to run (uses agent's default if not provided).

        Returns:
            Completed ValidationSession with all findings.

        Example:
            >>> from browser_use import Agent
            >>> agent = Agent(task="Navigate to example.com")
            >>> session = await validator.run_with_validation(agent)
        """
        start_url = getattr(agent, "start_url", "") or ""
        agent_task = task or getattr(agent, "task", "") or ""

        self.start_session(start_url, agent_task)

        hooks = self.get_hooks()

        try:
            if task:
                await agent.run(task, **hooks)
            else:
                await agent.run(**hooks)
        except Exception as e:
            self.logger.error(f"Agent execution failed: {e}")
            if self._session:
                self._session.state = SessionState.FAILED
                self._session.metadata["error"] = str(e)
            raise
        finally:
            await self.end_session()

        return self.get_session()


__all__ = ["AgentValidator"]
