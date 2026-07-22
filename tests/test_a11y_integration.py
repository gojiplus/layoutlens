"""Tests for wiring the axe-core engine into the public API, validator, and CLI.

Unit tests mock the auditor and the LLM so mode semantics can be asserted
without a browser or API key. Browser-marked tests run real chromium with the
vendored axe-core bundle and require no API key at all.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from layoutlens import AXE_VERSION, LayoutLens
from layoutlens.a11y import A11yFinding, A11yReport
from layoutlens.api.core import AnalysisResult
from layoutlens.exceptions import ValidationError
from layoutlens.integrations.browser_use import AgentValidator, ValidationPolicy
from layoutlens.integrations.browser_use.validator import normalize_wcag_reference

FIXTURE_DIR = Path(__file__).parent.parent / "benchmarks" / "test_data" / "accessibility"
VIOLATIONS_HTML = FIXTURE_DIR / "wcag_violations.html"


def _finding(rule_id: str, refs: list[str]) -> A11yFinding:
    return A11yFinding(
        rule_id=rule_id,
        impact="serious",
        wcag_refs=refs,
        description=f"{rule_id} description",
        help_url=f"https://example.com/{rule_id}",
        nodes=[{"target": [f"#{rule_id}"], "html": f"<div id='{rule_id}'></div>"}],
    )


def _report(violations: list[A11yFinding]) -> A11yReport:
    return A11yReport(
        source="page.html",
        viewport="desktop",
        engine_version=AXE_VERSION,
        violations=violations,
        incomplete=[],
        passes_count=5,
    )


def _fake_open_page(page, sessions: list):
    """Build a patched ``open_page`` that records each session opened.

    Yields ``page`` and appends to ``sessions`` so a test can assert exactly one
    browser session was used for the hybrid screenshot + axe audit.
    """

    @asynccontextmanager
    async def _cm(*args, **kwargs):
        sessions.append((args, kwargs))
        yield page

    return _cm


def _fake_vision(answer: str, confidence: float, reasoning: str):
    """An AsyncMock standing in for ``_call_vision_api``."""
    return AsyncMock(
        return_value={
            "answer": answer,
            "confidence": confidence,
            "reasoning": reasoning,
            "metadata": {"model_used": "mock", "provider": "litellm"},
        }
    )


# ---------------------------------------------------------------------------
# check_accessibility / audit_accessibility mode semantics (mocked auditor+LLM)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestCheckAccessibilityModes:
    """Mode semantics for check_accessibility with a mocked auditor and LLM."""

    async def test_axe_mode_deterministic_never_calls_llm(self):
        lens = LayoutLens()
        report = _report(
            [_finding("image-alt", ["wcag2a", "wcag111"]), _finding("color-contrast", ["wcag2aa", "wcag143"])]
        )

        with (
            patch("layoutlens.api.core.AxeAuditor") as mock_auditor_cls,
            patch("layoutlens.api.core.acompletion", new=AsyncMock()) as mock_llm,
        ):
            mock_auditor_cls.return_value.audit = AsyncMock(return_value=report)
            result = await lens.check_accessibility("page.html", mode="axe")

        # No LLM was touched.
        mock_llm.assert_not_called()
        # WCAG A/AA tags requested.
        mock_auditor_cls.assert_called_once_with(run_only=["wcag2a", "wcag2aa"])

        assert result.answer.lower().startswith("no")
        assert "image-alt" in result.answer and "color-contrast" in result.answer
        assert result.confidence == 1.0
        assert result.reasoning == report.summary()
        assert result.metadata["mode"] == "axe"
        assert result.metadata["engine"] == f"axe-core {AXE_VERSION}"
        assert result.metadata["a11y"]["violations"][0]["rule_id"] == "image-alt"

    async def test_axe_mode_clean_answers_yes(self):
        lens = LayoutLens()
        report = _report([])

        with (
            patch("layoutlens.api.core.AxeAuditor") as mock_auditor_cls,
            patch("layoutlens.api.core.acompletion", new=AsyncMock()) as mock_llm,
        ):
            mock_auditor_cls.return_value.audit = AsyncMock(return_value=report)
            result = await lens.check_accessibility("page.html", mode="axe")

        mock_llm.assert_not_called()
        assert result.answer.lower().startswith("yes")
        assert result.confidence == 1.0
        assert result.metadata["mode"] == "axe"

    async def test_hybrid_uses_single_session_and_overrides_on_violations(self):
        # Plan-mandated: hybrid opens ONE browser session shared by the
        # screenshot and the axe audit, then forces "no" on violations.
        lens = LayoutLens()
        report = _report([_finding("color-contrast", ["wcag2aa", "wcag143"])])

        page = Mock()
        page.screenshot = AsyncMock()
        sessions: list = []
        lens._call_vision_api = _fake_vision(
            "Yes, this page looks accessible", 0.6, "The layout appears clean and usable."
        )

        with (
            patch("layoutlens.api.core.open_page", _fake_open_page(page, sessions)),
            patch("layoutlens.api.core.AxeAuditor") as mock_auditor_cls,
        ):
            mock_auditor_cls.return_value.audit_page = AsyncMock(return_value=report)
            # The single-session path must never fall back to the two-session audit().
            mock_auditor_cls.return_value.audit = AsyncMock(side_effect=AssertionError("audit() must not be used"))
            result = await lens.check_accessibility("page.html", mode="hybrid")

        # Exactly one browser session was opened.
        assert len(sessions) == 1
        # The screenshot was taken and axe audited the SAME page object.
        page.screenshot.assert_awaited_once()
        mock_auditor_cls.return_value.audit_page.assert_awaited_once()
        assert mock_auditor_cls.return_value.audit_page.call_args.args[0] is page
        # The LLM analyzed exactly the screenshot that was captured, with axe context injected.
        shot_path = page.screenshot.call_args.kwargs["path"]
        assert lens._call_vision_api.call_args.kwargs["image_path"] == shot_path
        assert "Deterministic axe-core scan results" in lens._call_vision_api.call_args.kwargs["query"]

        # Deterministic override wins.
        assert result.answer.lower().startswith("no")
        assert result.confidence == 1.0
        assert "LLM assessment" in result.reasoning
        assert "color-contrast" in result.reasoning
        assert result.metadata["mode"] == "hybrid"
        assert result.metadata["a11y"]["violations"][0]["rule_id"] == "color-contrast"
        assert result.metadata["engine"] == f"axe-core {AXE_VERSION}"

    async def test_hybrid_keeps_llm_answer_when_clean(self):
        lens = LayoutLens()
        report = _report([])

        page = Mock()
        page.screenshot = AsyncMock()
        sessions: list = []
        lens._call_vision_api = _fake_vision("Yes, fully accessible", 0.72, "Good contrast and structure.")

        with (
            patch("layoutlens.api.core.open_page", _fake_open_page(page, sessions)),
            patch("layoutlens.api.core.AxeAuditor") as mock_auditor_cls,
        ):
            mock_auditor_cls.return_value.audit_page = AsyncMock(return_value=report)
            result = await lens.check_accessibility("page.html", mode="hybrid")

        assert len(sessions) == 1
        assert result.answer == "Yes, fully accessible"
        assert result.confidence == 0.72
        assert result.metadata["mode"] == "hybrid"
        assert "a11y" in result.metadata

    async def test_hybrid_axe_failure_falls_back_to_llm_only(self):
        # Item 7a: an axe error in hybrid degrades to LLM-only with a note,
        # rather than failing loud (axe mode still fails loud, tested elsewhere).
        lens = LayoutLens()

        page = Mock()
        page.screenshot = AsyncMock()
        sessions: list = []
        lens._call_vision_api = _fake_vision("Mostly accessible", 0.8, "Some minor issues.")

        with (
            patch("layoutlens.api.core.open_page", _fake_open_page(page, sessions)),
            patch("layoutlens.api.core.AxeAuditor") as mock_auditor_cls,
        ):
            mock_auditor_cls.return_value.audit_page = AsyncMock(side_effect=RuntimeError("axe boom"))
            result = await lens.check_accessibility("page.html", mode="hybrid")

        # LLM result is returned, with the axe error recorded and no override applied.
        assert result.answer == "Mostly accessible"
        assert result.confidence == 0.8
        assert result.metadata["mode"] == "hybrid"
        assert result.metadata["a11y_error"] == "axe boom"
        assert "a11y" not in result.metadata
        # The LLM query carried NO injected axe context (there was no report).
        assert "Deterministic axe-core scan results" not in lens._call_vision_api.call_args.kwargs["query"]

    async def test_hybrid_cache_hit_returns_copy_without_re_wrapping(self):
        # CRITICAL regression: a memory-cache hit must return a defensive copy so
        # the hybrid override never re-wraps the cached reasoning across calls.
        lens = LayoutLens()  # real in-memory cache
        report = _report([_finding("color-contrast", ["wcag2aa", "wcag143"])])

        page = Mock()
        page.screenshot = AsyncMock()
        sessions: list = []
        lens._call_vision_api = _fake_vision("Yes, looks fine", 0.6, "Clean and usable layout.")

        with (
            patch("layoutlens.api.core.open_page", _fake_open_page(page, sessions)),
            patch("layoutlens.api.core.AxeAuditor") as mock_auditor_cls,
        ):
            mock_auditor_cls.return_value.audit_page = AsyncMock(return_value=report)
            first = await lens.check_accessibility("page.html", mode="hybrid")
            # Mutating the first result must not corrupt the cached entry.
            first.reasoning += " MUTATED"
            second = await lens.check_accessibility("page.html", mode="hybrid")

        # Second call is a pure cache hit: one session, one LLM call total.
        assert len(sessions) == 1
        lens._call_vision_api.assert_awaited_once()
        # Reasoning is wrapped exactly once, both times.
        assert second.reasoning.count("LLM assessment") == 1
        assert "MUTATED" not in second.reasoning
        assert second.metadata["cache_hit"] is True

    async def test_axe_mode_rejects_image_source(self):
        # Item 2: axe cannot audit a pre-rendered screenshot (no DOM).
        lens = LayoutLens()
        with (
            patch("layoutlens.api.core.AxeAuditor") as mock_auditor_cls,
            pytest.raises(ValidationError, match="image source"),
        ):
            await lens.check_accessibility("shot.png", mode="axe")
        mock_auditor_cls.assert_not_called()

    async def test_hybrid_mode_image_source_falls_back_to_llm(self):
        # Item 2: hybrid on an image falls back to vision-only, no auditor built.
        lens = LayoutLens()
        lens.analyze = AsyncMock(
            return_value=AnalysisResult(
                source="shot.png", query="q", answer="Looks ok", confidence=0.7, reasoning="fine"
            )
        )
        with patch("layoutlens.api.core.AxeAuditor", new=MagicMock()) as mock_auditor_cls:
            result = await lens.check_accessibility("shot.png", mode="hybrid")

        lens.analyze.assert_awaited_once()
        mock_auditor_cls.assert_not_called()
        assert result.metadata["mode"] == "llm"
        assert result.metadata["a11y_skipped"] == "image source"

    async def test_axe_answer_is_level_aware(self):
        # Item 7b: the deterministic answer names the level(s) actually audited.
        lens = LayoutLens()
        report = _report([_finding("image-alt", ["wcag2a", "wcag111"])])

        with patch("layoutlens.api.core.AxeAuditor") as mock_auditor_cls:
            mock_auditor_cls.return_value.audit = AsyncMock(return_value=report)
            a_only = await lens.audit_accessibility("page.html", compliance_level="A", mode="axe")
            aaa = await lens.audit_accessibility("page.html", compliance_level="AAA", mode="axe")

        assert "WCAG A violation" in a_only.answer
        assert "A/AA" not in a_only.answer
        assert "WCAG A/AA/AAA violation" in aaa.answer

    async def test_llm_mode_never_constructs_auditor(self):
        lens = LayoutLens()

        llm_result = AnalysisResult(
            source="page.html",
            query="q",
            answer="Mostly accessible",
            confidence=0.8,
            reasoning="Some minor issues.",
        )
        lens.analyze = AsyncMock(return_value=llm_result)

        with patch("layoutlens.api.core.AxeAuditor", new=MagicMock()) as mock_auditor_cls:
            result = await lens.check_accessibility("page.html", mode="llm")

        mock_auditor_cls.assert_not_called()
        assert result.metadata["mode"] == "llm"
        assert "a11y" not in result.metadata

    @pytest.mark.parametrize(
        "level,expected",
        [
            ("A", ["wcag2a"]),
            ("AA", ["wcag2a", "wcag2aa"]),
            ("AAA", ["wcag2a", "wcag2aa", "wcag2aaa"]),
        ],
    )
    async def test_audit_accessibility_honors_compliance_level(self, level, expected):
        lens = LayoutLens()
        report = _report([_finding("image-alt", ["wcag2a", "wcag111"])])

        with (
            patch("layoutlens.api.core.AxeAuditor") as mock_auditor_cls,
            patch("layoutlens.api.core.acompletion", new=AsyncMock()) as mock_llm,
        ):
            mock_auditor_cls.return_value.audit = AsyncMock(return_value=report)
            result = await lens.audit_accessibility("page.html", compliance_level=level, mode="axe")

        mock_llm.assert_not_called()
        mock_auditor_cls.assert_called_once_with(run_only=expected)
        assert result.confidence == 1.0
        assert result.metadata["mode"] == "axe"


# ---------------------------------------------------------------------------
# WCAG reference normalization
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestWcagNormalization:
    """normalize_wcag_reference maps free-text refs to axe tag form."""

    @pytest.mark.parametrize(
        "reference,expected",
        [
            ("WCAG 1.4.3", "wcag143"),
            ("wcag 1.4.3", "wcag143"),
            ("wcag 2.1 SC 1.4.3", "wcag143"),
            ("wcag 2.1 SC 4.1.2", "wcag412"),
            ("WCAG 1.4.11", "wcag1411"),
            ("WCAG 2.4.7", "wcag247"),
            ("WCAG AA", None),
            ("wcag aaa", None),
            ("no criterion here", None),
        ],
    )
    def test_normalization(self, reference, expected):
        assert normalize_wcag_reference(reference) == expected


# ---------------------------------------------------------------------------
# Validator machine-verification (mocked auditor + expert analysis)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestValidatorVerification:
    """validate_state cross-checks LLM findings against axe violations."""

    def _make_validator(self, tmp_path) -> AgentValidator:
        policy = ValidationPolicy(include_screenshots=False, experts=["accessibility_expert"])
        return AgentValidator(policy=policy, output_dir=str(tmp_path))

    def _mock_page(self):
        page = Mock()
        page.url = "http://localhost/page"
        page.screenshot = AsyncMock()
        return page

    async def test_verified_true_when_tag_matches(self, tmp_path):
        validator = self._make_validator(tmp_path)
        validator._analyze_with_expert = AsyncMock(
            return_value=AnalysisResult(
                source="s",
                query="q",
                answer="Low contrast text",
                confidence=0.7,
                reasoning="This is a serious wcag 1.4.3 color contrast failure.",
            )
        )
        report = _report([_finding("color-contrast", ["wcag2aa", "wcag143"])])

        with patch("layoutlens.integrations.browser_use.validator.AxeAuditor") as mock_auditor_cls:
            mock_auditor_cls.return_value.audit_page = AsyncMock(return_value=report)
            step = await validator.validate_state(self._mock_page())

        assert step.findings, "expected an extracted finding"
        assert step.findings[0].wcag_reference is not None
        assert step.findings[0].verified is True
        assert step.metadata["a11y"]["violations"][0]["rule_id"] == "color-contrast"

    async def test_verified_false_when_tag_absent(self, tmp_path):
        validator = self._make_validator(tmp_path)
        validator._analyze_with_expert = AsyncMock(
            return_value=AnalysisResult(
                source="s",
                query="q",
                answer="Low contrast text",
                confidence=0.7,
                reasoning="This is a serious wcag 1.4.3 color contrast failure.",
            )
        )
        # axe reports a different criterion (1.1.1), not 1.4.3.
        report = _report([_finding("image-alt", ["wcag2a", "wcag111"])])

        with patch("layoutlens.integrations.browser_use.validator.AxeAuditor") as mock_auditor_cls:
            mock_auditor_cls.return_value.audit_page = AsyncMock(return_value=report)
            step = await validator.validate_state(self._mock_page())

        assert step.findings[0].verified is False

    async def test_verified_none_without_wcag_reference(self, tmp_path):
        validator = self._make_validator(tmp_path)
        validator._analyze_with_expert = AsyncMock(
            return_value=AnalysisResult(
                source="s",
                query="q",
                answer="Serious usability problem",
                confidence=0.6,
                reasoning="This is a serious layout problem with no criterion cited.",
            )
        )
        report = _report([_finding("image-alt", ["wcag2a", "wcag111"])])

        with patch("layoutlens.integrations.browser_use.validator.AxeAuditor") as mock_auditor_cls:
            mock_auditor_cls.return_value.audit_page = AsyncMock(return_value=report)
            step = await validator.validate_state(self._mock_page())

        assert step.findings[0].wcag_reference is None
        assert step.findings[0].verified is None

    async def test_verified_none_when_axe_fails(self, tmp_path):
        validator = self._make_validator(tmp_path)
        validator._analyze_with_expert = AsyncMock(
            return_value=AnalysisResult(
                source="s",
                query="q",
                answer="Low contrast text",
                confidence=0.7,
                reasoning="This is a serious wcag 1.4.3 color contrast failure.",
            )
        )

        with patch("layoutlens.integrations.browser_use.validator.AxeAuditor") as mock_auditor_cls:
            mock_auditor_cls.return_value.audit_page = AsyncMock(side_effect=RuntimeError("axe boom"))
            step = await validator.validate_state(self._mock_page())

        # WCAG reference present but no axe data to check against -> stays None.
        assert step.findings[0].wcag_reference is not None
        assert step.findings[0].verified is None
        assert "a11y" not in step.metadata


# ---------------------------------------------------------------------------
# Browser-marked: real chromium + vendored axe-core, no API key required.
# ---------------------------------------------------------------------------


def _chromium_available() -> bool:
    """Return True if a headless chromium can be launched."""
    from playwright.async_api import async_playwright

    async def _check() -> bool:
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                await browser.close()
            return True
        except Exception:
            return False

    return asyncio.run(_check())


requires_chromium = pytest.mark.skipif(
    not _chromium_available(),
    reason="chromium is not available for Playwright",
)


@pytest.mark.browser
@requires_chromium
class TestCheckAccessibilityBrowser:
    """End-to-end axe mode with a real browser and no API key."""

    def test_axe_mode_keyless_end_to_end(self, monkeypatch):
        # Prove the headline promise: deterministic WCAG checks, no API key.
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        lens = LayoutLens()
        assert lens.api_key is None

        result = asyncio.run(lens.check_accessibility(str(VIOLATIONS_HTML), mode="axe"))

        assert result.answer.lower().startswith("no")
        assert result.confidence == 1.0
        assert result.metadata["mode"] == "axe"
        assert result.metadata["engine"] == f"axe-core {AXE_VERSION}"
        assert len(result.metadata["a11y"]["violations"]) > 0
