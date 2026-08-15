"""Test custom exception handling."""

from unittest.mock import patch

import pytest

from layoutlens import LayoutLens
from layoutlens.exceptions import (
    AnalysisError,
    AuthenticationError,
    LayoutFileNotFoundError,
    LayoutLensError,
    ValidationError,
)


class TestCustomExceptions:
    """Test custom exception classes."""

    def test_layoutlens_error_base(self):
        error = LayoutLensError("Test message", {"key": "value"})

        assert str(error) == "Test message (key: value)"
        assert error.message == "Test message"
        assert error.details == {"key": "value"}

    def test_validation_error(self):
        error = ValidationError("Invalid input", field="query", value="")

        assert error.field == "query"
        assert error.value == ""
        assert "field: query" in str(error)

    def test_analysis_error(self):
        error = AnalysisError(
            "Analysis failed", query="test query", source="test.html", confidence=0.2
        )

        assert error.query == "test query"
        assert error.source == "test.html"
        assert error.confidence == 0.2

    def test_authentication_error(self):
        error = AuthenticationError()

        assert "API key" in str(error)
        assert isinstance(error, LayoutLensError)


class TestLayoutLensExceptions:
    """Test exception handling in LayoutLens class."""

    def test_missing_api_key_constructor_tolerant(self):
        """The constructor tolerates a missing key (deferred to first LLM use)."""
        with patch.dict("os.environ", {}, clear=True):
            lens = LayoutLens()
            assert lens.api_key is None

    @pytest.mark.asyncio
    async def test_missing_api_key_raises_on_first_llm_use(self, tmp_path):
        """AuthenticationError surfaces at the vision-API choke point, not construction."""
        image = tmp_path / "shot.png"
        image.write_bytes(b"not-a-real-png")
        with patch.dict("os.environ", {}, clear=True):
            lens = LayoutLens()
            with pytest.raises(AuthenticationError, match="API key required"):
                await lens._call_vision_api(str(image), "Is it accessible?")

    @pytest.mark.asyncio
    async def test_empty_query_validation(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"}):
            lens = LayoutLens()

            with pytest.raises(ValidationError, match="Query cannot be empty"):
                await lens.analyze("test.html", "")

    @pytest.mark.asyncio
    async def test_file_not_found_raises_for_single_call(self):
        """A single source+query call propagates typed errors to the caller."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"}):
            lens = LayoutLens()

            with pytest.raises(LayoutFileNotFoundError):
                await lens.analyze("nonexistent.png", "Is this good?")

    @pytest.mark.asyncio
    async def test_file_not_found_isolated_in_batch(self):
        """Batch runs isolate per-item errors instead of raising."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"}):
            lens = LayoutLens()

            batch = await lens.analyze(
                ["nonexistent1.png", "nonexistent2.png"], "Is this good?"
            )
            assert batch.total_queries == 2
            assert all(r.confidence == 0.0 for r in batch.results)
            assert all("Error" in r.answer for r in batch.results)

    @patch("layoutlens.capture.Capture.screenshots")
    @pytest.mark.asyncio
    async def test_screenshot_error(self, mock_capture):
        """Untyped capture failures degrade to an error result."""
        mock_capture.side_effect = Exception("Browser failed")

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"}):
            lens = LayoutLens()

            result = await lens.analyze("https://example.com", "Is this accessible?")

            assert result.confidence == 0.0
            assert "Error" in result.answer
            assert "Browser failed" in result.answer

    @patch("layoutlens.capture.Capture.screenshots")
    @patch("layoutlens.api.core.acompletion")
    @pytest.mark.asyncio
    async def test_analysis_error(self, mock_acompletion, mock_capture):
        """Untyped vision-API failures degrade to an error result."""
        mock_capture.return_value = ["screenshot.png"]
        mock_acompletion.side_effect = Exception("OpenAI API failed")

        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"}),
            patch("os.path.exists", return_value=True),
            patch(
                "layoutlens.api.core.LayoutLens._encode_image",
                return_value="fake-base64",
            ),
        ):
            lens = LayoutLens(cache_enabled=False)

            result = await lens.analyze("https://example.com", "Is this accessible?")

            assert result.confidence == 0.0
            assert "Error" in result.answer
            assert "OpenAI API failed" in result.answer


class TestExceptionMessages:
    """Test exception message formatting."""

    def test_error_with_details(self):
        error = LayoutLensError(
            "Something failed",
            {"component": "LayoutLens", "operation": "analyze", "retry_count": 3},
        )

        message = str(error)
        assert "Something failed" in message
        assert "component: LayoutLens" in message
        assert "operation: analyze" in message
        assert "retry_count: 3" in message

    def test_error_without_details(self):
        error = LayoutLensError("Simple error")

        assert str(error) == "Simple error"
