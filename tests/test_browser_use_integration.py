"""
Tests for Browser Use integration module.

These tests validate the AgentValidator, SessionRecorder, SessionReplayer,
and ValidationReportGenerator classes.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from layoutlens.integrations.browser_use import (
    AgentValidator,
    SessionComparison,
    SessionRecording,
    SessionReplayer,
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


class TestSessionRecording:
    """Tests for SessionRecording dataclass."""

    def test_save_and_load(self):
        """Test saving and loading a recording."""
        session = ValidationSession(
            session_id="test_session",
            state=SessionState.COMPLETED,
            start_url="https://example.com",
        )

        recording = SessionRecording(
            recording_id="test_recording",
            session=session,
            screenshots={1: "/path/to/screenshot.png"},
            action_log=[{"step": 1, "action": "click"}],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "recording.json"
            recording.save(save_path)

            assert save_path.exists()

            loaded = SessionRecording.load(save_path)
            assert loaded.recording_id == "test_recording"
            assert loaded.session.session_id == "test_session"
            assert loaded.screenshots.get("1") == "/path/to/screenshot.png"


class TestAgentValidator:
    """Tests for AgentValidator class."""

    def test_init_with_defaults(self):
        """Test initializing with default values."""
        with patch("layoutlens.integrations.browser_use.validator.LayoutLens"):
            validator = AgentValidator()

            assert validator.policy.experts == ["accessibility_expert"]
            assert validator._session is None

    def test_init_with_custom_experts(self):
        """Test initializing with custom experts."""
        with patch("layoutlens.integrations.browser_use.validator.LayoutLens"):
            validator = AgentValidator(
                experts=["mobile_expert", "conversion_expert"],
            )

            assert validator.policy.experts == ["mobile_expert", "conversion_expert"]

    def test_start_session(self):
        """Test starting a validation session."""
        with patch("layoutlens.integrations.browser_use.validator.LayoutLens"):
            validator = AgentValidator()
            session = validator.start_session(
                start_url="https://example.com",
                agent_task="Test task",
            )

            assert session.start_url == "https://example.com"
            assert session.agent_task == "Test task"
            assert session.state == SessionState.RUNNING
            assert validator._session is session

    @pytest.mark.asyncio
    async def test_end_session(self):
        """Test ending a validation session."""
        with patch("layoutlens.integrations.browser_use.validator.LayoutLens"):
            validator = AgentValidator()
            validator.start_session()

            session = await validator.end_session()

            assert session.state == SessionState.COMPLETED
            assert session.end_time != ""

    def test_get_hooks(self):
        """Test getting Browser Use hooks."""
        with patch("layoutlens.integrations.browser_use.validator.LayoutLens"):
            validator = AgentValidator()
            hooks = validator.get_hooks()

            assert "on_step_start" in hooks
            assert "on_step_end" in hooks
            assert callable(hooks["on_step_start"])
            assert callable(hooks["on_step_end"])


class TestSessionReplayer:
    """Tests for SessionReplayer class."""

    def test_init(self):
        """Test initializing replayer."""
        with patch("layoutlens.integrations.browser_use.session.LayoutLens"):
            replayer = SessionReplayer()

            assert replayer.policy.experts == ["accessibility_expert"]

    @pytest.mark.asyncio
    async def test_extract_findings(self):
        """Test finding extraction from reasoning."""
        with patch("layoutlens.integrations.browser_use.session.LayoutLens"):
            replayer = SessionReplayer()

            findings = replayer._extract_findings(
                "This has critical accessibility issues with color contrast",
                "accessibility_expert",
                0.8,
            )

            assert len(findings) == 1
            assert findings[0].severity == ValidationSeverity.CRITICAL


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

    def test_generate_comparison_report(self):
        """Test generating comparison report."""
        comparison = SessionComparison(
            baseline_id="baseline_123",
            current_id="current_456",
            new_findings=[
                ValidationFinding("New issue", ValidationSeverity.HIGH, "expert", 0.8),
            ],
            resolved_findings=[],
            persistent_findings=[],
            regression_score=5.0,
            summary="Regression detected: 1 new issues",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = ValidationReportGenerator(output_dir=tmpdir)
            report_path = generator.generate_comparison_report(comparison)

            assert report_path.exists()

            content = report_path.read_text()
            assert "baseline_123" in content
            assert "current_456" in content
            assert "New issue" in content

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


class TestIntegrationWorkflow:
    """Integration tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_validator_session_lifecycle(self):
        """Test complete validator session lifecycle."""
        with patch("layoutlens.integrations.browser_use.validator.LayoutLens"):
            validator = AgentValidator(
                experts=["accessibility_expert"],
                policy=ValidationPolicy(
                    capture_on_click=False,
                    capture_on_navigation=False,
                ),
            )

            session = validator.start_session(
                start_url="https://example.com",
                agent_task="Test task",
            )
            assert session.state == SessionState.RUNNING

            completed_session = await validator.end_session()
            assert completed_session.state == SessionState.COMPLETED
            assert completed_session.session_id == session.session_id

    def test_session_recording_roundtrip(self):
        """Test saving and loading session recording."""
        finding = ValidationFinding(
            issue="Test issue",
            severity=ValidationSeverity.MEDIUM,
            expert="accessibility_expert",
            confidence=0.75,
        )

        step = ValidationStepResult(
            step_number=1,
            trigger=ValidationTrigger.ON_CLICK,
            url="https://example.com/page",
            findings=[finding],
            confidence=0.75,
        )

        session = ValidationSession(
            session_id="roundtrip_test",
            state=SessionState.COMPLETED,
            steps=[step],
            start_url="https://example.com",
            agent_task="Test roundtrip",
        )

        recording = SessionRecording(
            recording_id="roundtrip_recording",
            session=session,
            screenshots={1: "/path/screenshot.png"},
            action_log=[{"step": 1, "action": "click", "target": "#button"}],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "roundtrip.json"
            recording.save(save_path)

            loaded = SessionRecording.load(save_path)

            assert loaded.recording_id == recording.recording_id
            assert loaded.session.session_id == session.session_id
            assert loaded.session.state == SessionState.COMPLETED
            assert len(loaded.session.steps) == 1
            assert loaded.session.steps[0].trigger == ValidationTrigger.ON_CLICK
            assert len(loaded.session.steps[0].findings) == 1
            assert loaded.session.steps[0].findings[0].severity == ValidationSeverity.MEDIUM
