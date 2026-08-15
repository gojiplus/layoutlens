"""End-to-end API flow tests with mocked LLM and capture layers."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from layoutlens.exceptions import LayoutFileNotFoundError, ValidationError

MOCK_API_KEY = "sk-test-key-12345"


def _mock_llm_response(payload: str, total_tokens: int = 150) -> Mock:
    response = Mock()
    response.choices = [Mock()]
    response.choices[0].message.content = payload
    response.usage.total_tokens = total_tokens
    return response


class TestImports:
    """The public namespace exposes the API surface we document."""

    def test_main_api_imports(self):
        from layoutlens import (
            AnalysisResult,
            BatchResult,
            Capture,
            ComparisonResult,
            Instructions,
            LayoutLens,
            LayoutScorer,
            UserContext,
            get_expert,
            list_available_experts,
        )

        assert callable(get_expert)
        assert "accessibility_expert" in list_available_experts()
        for cls in (
            AnalysisResult,
            BatchResult,
            Capture,
            ComparisonResult,
            Instructions,
            LayoutLens,
            LayoutScorer,
            UserContext,
        ):
            assert isinstance(cls, type)


class TestAPIFunctionality:
    """Analyze flows with mocked capture + LLM."""

    def test_layoutlens_initialization(self):
        from layoutlens.api.core import LayoutLens

        # Without an API key the constructor no longer raises: the requirement
        # is deferred to first LLM use so deterministic operations stay keyless.
        with patch.dict("os.environ", {}, clear=True):
            keyless = LayoutLens()
            assert keyless.api_key is None

        lens = LayoutLens(api_key=MOCK_API_KEY)
        assert lens.api_key == MOCK_API_KEY
        assert lens.model == "gpt-4o-mini"  # default

    def test_url_detection(self):
        from layoutlens.api.core import LayoutLens

        lens = LayoutLens(api_key=MOCK_API_KEY)

        assert lens._is_url("https://example.com")
        assert lens._is_url("http://example.org")
        assert not lens._is_url("/path/to/file.png")
        assert not lens._is_url("screenshot.jpg")
        assert not lens._is_url(Path("image.png"))

    @pytest.mark.asyncio
    @patch("layoutlens.api.core.acompletion")
    @patch("layoutlens.capture.Capture.screenshots")
    async def test_analyze_url_flow(self, mock_capture, mock_acompletion):
        """URL -> capture -> vision call -> parsed AnalysisResult."""
        from layoutlens.api.core import LayoutLens

        mock_capture.return_value = ["/mock/screenshot.png"]
        mock_acompletion.return_value = _mock_llm_response(
            '{"answer": "Yes, the navigation is user-friendly.",'
            ' "confidence": 0.85, "reasoning": "Clear top navigation."}'
        )

        lens = LayoutLens(
            api_key=MOCK_API_KEY, output_dir=tempfile.mkdtemp(), cache_enabled=False
        )

        with (
            patch("os.path.exists", return_value=True),
            patch(
                "layoutlens.api.core.LayoutLens._encode_image",
                return_value="fake-base64-data",
            ),
        ):
            result = await lens.analyze(
                "https://example.com", "Is the navigation user-friendly?"
            )

        mock_acompletion.assert_awaited_once()
        assert result.answer.startswith("Yes")
        assert result.confidence == pytest.approx(0.85)
        assert result.reasoning == "Clear top navigation."

    @pytest.mark.asyncio
    async def test_analyze_missing_file_raises(self):
        from layoutlens.api.core import LayoutLens

        lens = LayoutLens(api_key=MOCK_API_KEY)

        with pytest.raises(LayoutFileNotFoundError):
            await lens.analyze("/nonexistent/file.png", "Test query")

    @pytest.mark.asyncio
    async def test_compare_handles_missing_files(self):
        """compare() degrades to an error result instead of crashing."""
        from layoutlens.api.core import LayoutLens

        lens = LayoutLens(api_key=MOCK_API_KEY)

        result = await lens.compare(
            ["/nonexistent1.png", "/nonexistent2.png"], "Which design is better?"
        )
        assert result.confidence == 0.0
        assert "Error" in result.answer

    @pytest.mark.asyncio
    @patch("layoutlens.api.core.acompletion")
    async def test_analyze_batch_method(self, mock_acompletion):
        """List sources fan out into a BatchResult with per-item results."""
        from layoutlens.api.core import LayoutLens

        mock_acompletion.return_value = _mock_llm_response(
            '{"answer": "The design looks good.", "confidence": 0.85,'
            ' "reasoning": "Clean layout."}'
        )

        lens = LayoutLens(api_key=MOCK_API_KEY)

        result = await lens.analyze(
            ["/nonexistent1.png", "/nonexistent2.png"], ["Is the design good?"]
        )

        assert isinstance(result.results, list)
        assert len(result.results) == 2
        assert result.total_queries == 2


class TestCaptureViewports:
    """Capture exposes the canonical viewport table."""

    def test_url_capture_viewports(self):
        from layoutlens.browser import ViewportConfig
        from layoutlens.capture import Capture

        capture = Capture()

        for name in ("desktop", "mobile", "tablet"):
            assert name in capture.VIEWPORTS

        desktop = capture.VIEWPORTS["desktop"]
        assert isinstance(desktop, ViewportConfig)
        assert (desktop.width, desktop.height) == (1920, 1080)
        assert not desktop.is_mobile

        mobile = capture.VIEWPORTS["mobile"]
        assert (mobile.width, mobile.height) == (375, 667)
        assert mobile.is_mobile
        assert mobile.has_touch


class TestErrorHandling:
    """Invalid inputs raise typed exceptions."""

    @pytest.mark.asyncio
    async def test_invalid_inputs(self):
        from layoutlens.api.core import LayoutLens

        lens = LayoutLens(api_key="test-key")

        with pytest.raises(ValidationError):
            await lens.analyze("https://example.com", "")

        with pytest.raises(LayoutFileNotFoundError):
            await lens.analyze("not-a-url", "test query")
