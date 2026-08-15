"""Tests for the Browser Use integration (types, reports, post-run validation)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from layoutlens.integrations.browser_use import (
    SessionState,
    ValidationFinding,
    ValidationPolicy,
    ValidationReportGenerator,
    ValidationSession,
    ValidationSeverity,
    ValidationStepResult,
    ValidationTrigger,
)


class TestValidationPolicy:
    """Tests for ValidationPolicy dataclass."""

    def test_default_policy(self):
        """Test default policy values."""
        policy = ValidationPolicy()

        assert policy.capture_on_click is True
        assert policy.capture_on_navigation is True
        assert policy.capture_on_form_submit is True
        assert policy.capture_on_error is True
        assert policy.capture_interval_steps == 0
        assert policy.experts == ["accessibility_expert"]
        assert policy.viewport == "desktop"
        assert policy.confidence_threshold == 0.5
        assert policy.max_concurrent_validations == 3
        assert policy.include_screenshots is True
        assert policy.custom_queries == []

    def test_custom_policy(self):
        """Test custom policy configuration."""
        policy = ValidationPolicy(
            capture_on_click=False,
            experts=["mobile_expert", "accessibility_expert"],
            viewport="mobile_portrait",
            confidence_threshold=0.7,
        )

        assert policy.capture_on_click is False
        assert policy.experts == ["mobile_expert", "accessibility_expert"]
        assert policy.viewport == "mobile_portrait"
        assert policy.confidence_threshold == 0.7


class TestValidationFinding:
    """Tests for ValidationFinding dataclass."""

    def test_create_finding(self):
        """Test creating a validation finding."""
        finding = ValidationFinding(
            issue="Missing alt text on image",
            severity=ValidationSeverity.HIGH,
            expert="accessibility_expert",
            confidence=0.85,
            wcag_reference="WCAG 2.1 SC 1.1.1",
            recommendation="Add descriptive alt text",
        )

        assert finding.issue == "Missing alt text on image"
        assert finding.severity == ValidationSeverity.HIGH
        assert finding.expert == "accessibility_expert"
        assert finding.confidence == 0.85
        assert finding.wcag_reference == "WCAG 2.1 SC 1.1.1"
        assert finding.recommendation == "Add descriptive alt text"


class TestValidationStepResult:
    """Tests for ValidationStepResult dataclass."""

    def test_create_step_result(self):
        """Test creating a step result."""
        finding = ValidationFinding(
            issue="Test issue",
            severity=ValidationSeverity.CRITICAL,
            expert="accessibility_expert",
            confidence=0.9,
        )

        result = ValidationStepResult(
            step_number=1,
            trigger=ValidationTrigger.ON_NAVIGATION,
            url="https://example.com",
            findings=[finding],
            confidence=0.85,
        )

        assert result.step_number == 1
        assert result.trigger == ValidationTrigger.ON_NAVIGATION
        assert result.url == "https://example.com"
        assert len(result.findings) == 1
        assert result.has_critical_findings is True

    def test_finding_count_by_severity(self):
        """Test counting findings by severity."""
        findings = [
            ValidationFinding("Issue 1", ValidationSeverity.CRITICAL, "expert", 0.9),
            ValidationFinding("Issue 2", ValidationSeverity.HIGH, "expert", 0.8),
            ValidationFinding("Issue 3", ValidationSeverity.CRITICAL, "expert", 0.85),
        ]

        result = ValidationStepResult(
            step_number=1,
            trigger=ValidationTrigger.MANUAL,
            findings=findings,
        )

        counts = result.finding_count_by_severity
        assert counts.get("critical") == 2
        assert counts.get("high") == 1


class TestValidationSession:
    """Tests for ValidationSession dataclass."""

    def test_create_session(self):
        """Test creating a validation session."""
        session = ValidationSession(
            session_id="test_session_123",
            start_url="https://example.com",
            agent_task="Test navigation",
        )

        assert session.session_id == "test_session_123"
        assert session.start_url == "https://example.com"
        assert session.agent_task == "Test navigation"
        assert session.state == SessionState.PENDING
        assert len(session.steps) == 0

    def test_session_statistics(self):
        """Test session statistics calculations."""
        finding = ValidationFinding(
            issue="Test issue",
            severity=ValidationSeverity.HIGH,
            expert="accessibility_expert",
            confidence=0.8,
        )

        step1 = ValidationStepResult(
            step_number=1,
            trigger=ValidationTrigger.MANUAL,
            findings=[finding],
            confidence=0.8,
        )

        step2 = ValidationStepResult(
            step_number=2,
            trigger=ValidationTrigger.MANUAL,
            findings=[finding, finding],
            confidence=0.9,
        )

        session = ValidationSession(
            session_id="test",
            steps=[step1, step2],
        )

        assert session.total_findings == 3
        assert abs(session.average_confidence - 0.85) < 0.001
        assert session.findings_by_severity.get("high") == 3


class TestValidationReportGenerator:
    """Tests for ValidationReportGenerator class."""

    def test_init(self):
        """Test initializing report generator."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = ValidationReportGenerator(output_dir=tmpdir)
            assert generator.output_dir.exists()

    def test_generate_json_report(self):
        """Test generating JSON report."""
        session = ValidationSession(
            session_id="test_session",
            state=SessionState.COMPLETED,
            start_url="https://example.com",
            total_actions=5,
            validated_actions=3,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = ValidationReportGenerator(output_dir=tmpdir)
            report_path = generator.generate_json_report(session)

            assert report_path.exists()

            with open(report_path) as f:
                data = json.load(f)

            assert data["session_id"] == "test_session"
            assert data["total_actions"] == 5
            assert data["validated_actions"] == 3

    def test_generate_html_report(self):
        """Test generating HTML report."""
        finding = ValidationFinding(
            issue="Test accessibility issue",
            severity=ValidationSeverity.HIGH,
            expert="accessibility_expert",
            confidence=0.85,
        )

        step = ValidationStepResult(
            step_number=1,
            trigger=ValidationTrigger.MANUAL,
            url="https://example.com",
            findings=[finding],
            confidence=0.85,
        )

        session = ValidationSession(
            session_id="test_session",
            state=SessionState.COMPLETED,
            steps=[step],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = ValidationReportGenerator(output_dir=tmpdir)
            report_path = generator.generate_html_report(session)

            assert report_path.exists()

            content = report_path.read_text()
            assert "test_session" in content
            assert "Test accessibility issue" in content
            assert "HIGH" in content

    def test_generate_timeline_data(self):
        """Test generating timeline visualization data."""
        step = ValidationStepResult(
            step_number=1,
            trigger=ValidationTrigger.ON_NAVIGATION,
            url="https://example.com",
            confidence=0.85,
            execution_time=1.5,
        )

        session = ValidationSession(
            session_id="test_session",
            steps=[step],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = ValidationReportGenerator(output_dir=tmpdir)
            timeline = generator.generate_timeline_data(session)

            assert timeline["session_id"] == "test_session"
            assert len(timeline["events"]) == 1
            assert timeline["events"][0]["step"] == 1
            assert timeline["events"][0]["confidence"] == 0.85


class _StubHistory:
    """Duck-typed stand-in for browser-use's AgentHistoryList."""

    def __init__(self, urls, shots):
        self._urls = urls
        self._shots = shots

    def urls(self):
        return self._urls

    def screenshot_paths(self, n_last=None, return_none_if_not_screenshot=True):
        return self._shots


class TestValidateAgentRun:
    """Post-run validation against a recorded history."""

    @pytest.mark.asyncio
    async def test_deterministic_checks_per_unique_url(self, monkeypatch):
        from layoutlens import LayoutLens
        from layoutlens.a11y.types import A11yFinding, A11yReport
        from layoutlens.integrations.browser_use import validate_agent_run
        from layoutlens.layout.types import LayoutReport

        violation = A11yFinding(
            rule_id="color-contrast",
            impact="serious",
            wcag_refs=["wcag143"],
            description="low contrast",
            help_url="",
            nodes=[{"target": ["#low"]}],
        )

        async def fake_audit(self, source, viewport="desktop"):
            return A11yReport(
                source=str(source),
                viewport=viewport,
                engine_version="test",
                violations=[violation],
                incomplete=[],
                passes_count=10,
            )

        async def fake_scan(self, source, viewport="desktop"):
            return LayoutReport(source=str(source), viewport=viewport, findings=[])

        monkeypatch.setattr(
            "layoutlens.integrations.browser_use.validator.AxeAuditor.audit",
            fake_audit,
        )
        monkeypatch.setattr(
            "layoutlens.integrations.browser_use.validator.LayoutScorer.scan",
            fake_scan,
        )

        # Three steps, one repeated URL, one about:blank -> 2 unique URLs.
        history = _StubHistory(
            urls=[
                "about:blank",
                "https://example.com",
                "https://example.com",
                "https://example.com/checkout",
            ],
            shots=[None, "a.png", "b.png", "c.png"],
        )

        session = await validate_agent_run(LayoutLens(), history)

        assert session.state == SessionState.COMPLETED
        assert len(session.steps) == 2
        assert [s.url for s in session.steps] == [
            "https://example.com",
            "https://example.com/checkout",
        ]
        first = session.steps[0]
        assert first.confidence == 1.0
        assert len(first.findings) == 1
        assert first.findings[0].severity == ValidationSeverity.HIGH
        assert first.findings[0].verified is True
        assert "color-contrast" in first.findings[0].issue

    @pytest.mark.asyncio
    async def test_requires_history_or_dir(self):
        from layoutlens import LayoutLens
        from layoutlens.integrations.browser_use import validate_agent_run

        with pytest.raises(ValueError, match="history or a screenshot_dir"):
            await validate_agent_run(LayoutLens())

    @pytest.mark.asyncio
    async def test_screenshot_dir_with_queries(self, tmp_path, monkeypatch):
        from layoutlens import LayoutLens
        from layoutlens.integrations.browser_use import validate_agent_run

        (tmp_path / "step1.png").write_bytes(b"fake")

        async def fake_analyze(source, query, viewport="desktop"):
            from layoutlens.api.core import AnalysisResult

            return AnalysisResult(
                source=str(source),
                query=query,
                answer="Yes",
                confidence=0.9,
                reasoning="looks fine",
            )

        lens = LayoutLens()
        monkeypatch.setattr(lens, "analyze", fake_analyze)

        session = await validate_agent_run(
            lens, screenshot_dir=tmp_path, queries=["Is the page readable?"]
        )

        assert len(session.steps) == 1
        assert session.steps[0].answer == "Yes"
        assert session.steps[0].metadata["query"] == "Is the page readable?"
