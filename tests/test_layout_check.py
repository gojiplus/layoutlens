"""check_layout mode semantics (mocked scorer + LLM), mirroring the a11y tests."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock, patch

import pytest

from layoutlens import LayoutLens
from layoutlens.exceptions import ValidationError
from layoutlens.layout.types import LayoutFinding, LayoutReport


def _finding(defect_class: str, selector: str = "#el") -> LayoutFinding:
    return LayoutFinding(
        defect_class=defect_class,
        selector=selector,
        bbox=[0, 0, 100, 20],
        measured={"value": 1},
        threshold={"limit": 2},
        description=f"{defect_class} at {selector}",
    )


def _report(findings: list[LayoutFinding]) -> LayoutReport:
    return LayoutReport(source="page.html", viewport="desktop", findings=findings)


def _fake_open_page(page, sessions: list):
    @asynccontextmanager
    async def _cm(*args, **kwargs):
        sessions.append(args)
        yield page

    return _cm


def _fake_vision(answer: str, confidence: float, reasoning: str):
    return AsyncMock(
        return_value={
            "answer": answer,
            "confidence": confidence,
            "reasoning": reasoning,
            "metadata": {},
        }
    )


@pytest.mark.unit
@pytest.mark.asyncio
class TestCheckLayoutModes:
    """Deterministic / hybrid / llm semantics for check_layout."""

    async def test_deterministic_mode_never_calls_llm(self):
        lens = LayoutLens()
        report = _report([_finding("overlap"), _finding("contrast", "#faint")])

        with (
            patch.object(LayoutLens, "_call_vision_api", new=AsyncMock()) as mock_llm,
            patch(
                "layoutlens.api.core.LayoutScorer.scan",
                new=AsyncMock(return_value=report),
            ) as mock_scan,
        ):
            result = await lens.check_layout("page.html", mode="deterministic")

        mock_llm.assert_not_called()
        mock_scan.assert_awaited_once()
        assert result.answer.lower().startswith("no")
        assert "overlap" in result.answer
        assert "contrast" in result.answer
        assert result.confidence == 1.0
        assert result.reasoning == report.summary()
        assert result.metadata["mode"] == "deterministic"
        assert result.metadata["engine"] == "layoutlens-layout"
        assert result.metadata["layout"]["findings"][0]["defect_class"] == "overlap"

    async def test_deterministic_clean_answers_yes(self):
        lens = LayoutLens()

        with patch(
            "layoutlens.api.core.LayoutScorer.scan",
            new=AsyncMock(return_value=_report([])),
        ):
            result = await lens.check_layout("page.html", mode="deterministic")

        assert result.answer.lower().startswith("yes")
        assert result.confidence == 1.0

    async def test_hybrid_single_session_and_override(self):
        lens = LayoutLens(cache_enabled=False)
        report = _report([_finding("clipping")])

        page = Mock()
        page.screenshot = AsyncMock()
        sessions: list = []
        lens._call_vision_api = _fake_vision(
            "Yes, the layout looks clean", 0.6, "Nothing stands out."
        )

        with (
            patch("layoutlens.api.core.open_page", _fake_open_page(page, sessions)),
            patch(
                "layoutlens.api.core.LayoutScorer.scan_page",
                new=AsyncMock(return_value=report),
            ) as mock_scan_page,
        ):
            result = await lens.check_layout("page.html", mode="hybrid")

        # Exactly one browser session: screenshot + scan share the page.
        assert len(sessions) == 1
        page.screenshot.assert_awaited_once()
        assert mock_scan_page.call_args.args[0] is page
        # The LLM saw the captured screenshot with layout context injected.
        shot_path = page.screenshot.call_args.kwargs["path"]
        assert lens._call_vision_api.call_args.kwargs["image_path"] == shot_path
        assert (
            "Deterministic layout/geometry scan results"
            in lens._call_vision_api.call_args.kwargs["query"]
        )
        # Measured defects override the LLM's opinion.
        assert result.answer.lower().startswith("no")
        assert result.confidence == 1.0
        assert "LLM assessment" in result.reasoning
        assert result.metadata["mode"] == "hybrid"
        assert result.metadata["layout"]["findings"][0]["defect_class"] == "clipping"

    async def test_hybrid_clean_keeps_llm_answer(self):
        lens = LayoutLens(cache_enabled=False)

        page = Mock()
        page.screenshot = AsyncMock()
        lens._call_vision_api = _fake_vision(
            "Yes, well laid out", 0.77, "Good spacing."
        )

        with (
            patch("layoutlens.api.core.open_page", _fake_open_page(page, [])),
            patch(
                "layoutlens.api.core.LayoutScorer.scan_page",
                new=AsyncMock(return_value=_report([])),
            ),
        ):
            result = await lens.check_layout("page.html", mode="hybrid")

        assert result.answer == "Yes, well laid out"
        assert result.confidence == 0.77
        assert "layout" in result.metadata

    async def test_hybrid_scan_failure_degrades_to_llm(self):
        lens = LayoutLens(cache_enabled=False)

        page = Mock()
        page.screenshot = AsyncMock()
        lens._call_vision_api = _fake_vision("Mostly fine", 0.8, "Minor issues.")

        with (
            patch("layoutlens.api.core.open_page", _fake_open_page(page, [])),
            patch(
                "layoutlens.api.core.LayoutScorer.scan_page",
                new=AsyncMock(side_effect=RuntimeError("boom")),
            ),
        ):
            result = await lens.check_layout("page.html", mode="hybrid")

        assert result.answer == "Mostly fine"
        assert result.metadata["layout_error"] == "boom"
        assert "layout" not in result.metadata

    async def test_deterministic_rejects_image_sources(self, tmp_path):
        lens = LayoutLens()
        shot = tmp_path / "shot.png"
        shot.write_bytes(b"fake")

        with pytest.raises(ValidationError, match="no DOM"):
            await lens.check_layout(str(shot), mode="deterministic")

    async def test_hybrid_image_falls_back_to_llm(self, tmp_path):
        lens = LayoutLens()
        shot = tmp_path / "shot.png"
        shot.write_bytes(b"fake")

        lens.analyze = AsyncMock(
            return_value=Mock(metadata={}, answer="Yes", confidence=0.9)
        )
        result = await lens.check_layout(str(shot), mode="hybrid")

        lens.analyze.assert_awaited_once()
        assert result.metadata["mode"] == "llm"
        assert result.metadata["layout_skipped"] == "image source"
