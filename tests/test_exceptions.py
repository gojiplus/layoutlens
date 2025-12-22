"""Test custom exception handling."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from layoutlens import LayoutLens
from layoutlens.exceptions import (
    AnalysisError,
    APIError,
    AuthenticationError,
    LayoutFileNotFoundError,
    LayoutLensError,
    RateLimitError,
    ScreenshotError,
    ValidationError,
    handle_api_error,
    wrap_exception,
)


class TestCustomExceptions:
    """Test custom exception classes."""

    def test_layoutlens_error_base(self):
        """Test base LayoutLensError."""
        error = LayoutLensError("Test message", {"key": "value"})

        assert str(error) == "Test message (key: value)"
        assert error.message == "Test message"
        assert error.details == {"key": "value"}

    def test_api_error(self):
        """Test APIError."""
        error = APIError("API failed", status_code=500, response="Server error")

        assert error.status_code == 500
        assert error.response == "Server error"
        assert "status_code: 500" in str(error)

    def test_screenshot_error(self):
        """Test ScreenshotError."""
        error = ScreenshotError("Capture failed", source="test.html", viewport="mobile")

        assert error.source == "test.html"
        assert error.viewport == "mobile"
        assert "source: test.html" in str(error)

    def test_validation_error(self):
        """Test ValidationError."""
        error = ValidationError("Invalid input", field="query", value="")

        assert error.field == "query"
        assert error.value == ""
        assert "field: query" in str(error)

    def test_analysis_error(self):
        """Test AnalysisError."""
        error = AnalysisError("Analysis failed", query="test query", source="test.html", confidence=0.2)

        assert error.query == "test query"
        assert error.source == "test.html"
        assert error.confidence == 0.2

    def test_authentication_error(self):
        """Test AuthenticationError."""
        error = AuthenticationError()

        assert "API key" in str(error)

    def test_rate_limit_error(self):
        """Test RateLimitError."""
        error = RateLimitError("Rate limited", retry_after=60)

        assert error.retry_after == 60
        assert "retry_after: 60" in str(error)


class TestExceptionHandlers:
    """Test exception handling utilities."""

    def test_handle_api_error(self):
        """Test API error handling factory."""
        # Test 401 unauthorized
        error = handle_api_error(401, "Unauthorized")
        assert isinstance(error, AuthenticationError)

        # Test 429 rate limit
        error = handle_api_error(429, "Rate limited")
        assert isinstance(error, RateLimitError)

        # Test generic error
        error = handle_api_error(500, "Server error")
        assert isinstance(error, APIError)
        assert error.status_code == 500

    def test_wrap_exception(self):
        """Test exception wrapping."""
        # Test ConnectionError
        original = ConnectionError("Network failed")
        wrapped = wrap_exception(original, "Network operation")
        assert isinstance(wrapped, LayoutLensError)
        assert "Network operation" in str(wrapped)

        # Test generic exception
        original = ValueError("Invalid value")
        wrapped = wrap_exception(original)
        assert isinstance(wrapped, LayoutLensError)
        assert "Invalid value" in str(wrapped)


class TestLayoutLensExceptions:
    """Test exception handling in LayoutLens class."""

    def test_missing_api_key(self):
        """Test AuthenticationError when API key is missing."""
        with (
            patch.dict("os.environ", {}, clear=True),
            pytest.raises(AuthenticationError, match="API key required"),
        ):
            LayoutLens()

    @pytest.mark.asyncio
    async def test_empty_query_validation(self):
        """Test ValidationError for empty query."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"}):
            lens = LayoutLens()

            with pytest.raises(ValidationError, match="Query cannot be empty"):
                await lens.analyze("test.html", "")

    @pytest.mark.asyncio
    async def test_file_not_found_error(self):
        """Test graceful handling of missing screenshot file."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"}):
            lens = LayoutLens()

            # Current implementation handles file not found gracefully
            result = await lens.analyze("nonexistent.png", "Is this good?")

            # Should return error result instead of raising exception
            assert result.confidence == 0.0
            assert "Error" in result.answer
            assert "nonexistent.png" in result.answer

    @patch("layoutlens.vision.capture.Capture.screenshots")
    @pytest.mark.asyncio
    async def test_screenshot_error(self, mock_capture):
        """Test graceful handling when screenshot capture fails."""
        mock_capture.side_effect = Exception("Browser failed")

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"}):
            lens = LayoutLens()

            # Current implementation handles capture errors gracefully
            result = await lens.analyze("https://example.com", "Is this accessible?")

            # Should return error result instead of raising exception
            assert result.confidence == 0.0
            assert "Error" in result.answer
            assert "Browser failed" in result.answer

    @patch("layoutlens.vision.capture.Capture.screenshots")
    @patch("layoutlens.api.core.acompletion")
    @pytest.mark.asyncio
    async def test_analysis_error(self, mock_acompletion, mock_capture):
        """Test graceful handling when vision analysis fails."""
        mock_capture.return_value = ["screenshot.png"]
        mock_acompletion.side_effect = Exception("OpenAI API failed")

        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"}),
            patch("os.path.exists", return_value=True),
            patch("layoutlens.api.core.LayoutLens._encode_image", return_value="fake-base64"),
        ):
            lens = LayoutLens()

            # Current implementation handles analysis errors gracefully
            result = await lens.analyze("https://example.com", "Is this accessible?")

            # Should return error result instead of raising exception
            assert result.confidence == 0.0
            assert "Error" in result.answer
            assert "OpenAI API failed" in result.answer


class TestExceptionMessages:
    """Test exception message formatting."""

    def test_error_with_details(self):
        """Test error message with details."""
        error = LayoutLensError(
            "Something failed",
            {"component": "VisionAnalyzer", "operation": "analyze", "retry_count": 3},
        )

        message = str(error)
        assert "Something failed" in message
        assert "component: VisionAnalyzer" in message
        assert "operation: analyze" in message
        assert "retry_count: 3" in message

    def test_error_without_details(self):
        """Test error message without details."""
        error = LayoutLensError("Simple error")

        assert str(error) == "Simple error"

    def test_nested_error_information(self):
        """Test that error details are preserved through wrapping."""
        original = ConnectionError("Network timeout")
        wrapped = wrap_exception(original, "URL capture")

        assert "URL capture" in str(wrapped)
        assert "Network timeout" in str(wrapped)


class TestGracefulDegradation:
    """Test graceful degradation when errors occur."""

    @patch("layoutlens.vision.capture.Capture.screenshots")
    @patch("layoutlens.api.core.acompletion")
    @pytest.mark.asyncio
    async def test_analysis_failure_handling(self, mock_acompletion, mock_capture):
        """Test that analysis failures are handled gracefully."""
        mock_capture.return_value = ["screenshot.png"]
        mock_acompletion.side_effect = Exception("API quota exceeded")

        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"}),
            patch("os.path.exists", return_value=True),
            patch("layoutlens.api.core.LayoutLens._encode_image", return_value="fake-base64"),
        ):
            lens = LayoutLens()

            # Current implementation handles failures gracefully by returning error results
            result = await lens.analyze("https://example.com", "Is this good?")

            # Should return error result with proper metadata
            assert result.query == "Is this good?"
            assert result.source == "https://example.com"
            assert result.confidence == 0.0
            assert "Error" in result.answer
            assert "API quota exceeded" in result.answer

    def test_exception_chaining(self):
        """Test that original exceptions are preserved in the chain."""
        original = ValueError("Original error")
        wrapped = wrap_exception(original, "Context")

        # The original exception should be accessible
        assert "Original error" in str(wrapped)
