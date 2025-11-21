"""Test custom exception handling."""

from unittest.mock import Mock, patch
import pytest

from layoutlens import LayoutLens
from layoutlens.exceptions import (
    LayoutLensError, APIError, ScreenshotError, ValidationError,
    AnalysisError, AuthenticationError, RateLimitError, 
    LayoutFileNotFoundError, handle_api_error, wrap_exception
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
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(AuthenticationError, match="API key required"):
                LayoutLens()
    
    def test_empty_query_validation(self):
        """Test ValidationError for empty query."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'}):
            lens = LayoutLens()
            
            with pytest.raises(ValidationError, match="Query cannot be empty"):
                lens.analyze("test.html", "")
    
    def test_file_not_found_error(self):
        """Test FileNotFoundError for missing screenshot."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'}):
            lens = LayoutLens()
            
            with pytest.raises(LayoutLensError):  # Should be FileNotFoundError but might be wrapped
                lens.analyze("nonexistent.png", "Is this good?")
    
    @patch('layoutlens.vision.capture.URLCapture.capture_url')
    def test_screenshot_error(self, mock_capture):
        """Test ScreenshotError when capture fails.""" 
        mock_capture.side_effect = Exception("Browser failed")
        
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'}):
            lens = LayoutLens()
            
            with pytest.raises(ScreenshotError, match="Failed to capture screenshot"):
                lens.analyze("https://example.com", "Is this accessible?")
    
    @patch('layoutlens.vision.capture.URLCapture.capture_url')
    @patch('layoutlens.vision.analyzer.VisionAnalyzer.analyze_screenshot')
    def test_analysis_error(self, mock_analyze, mock_capture):
        """Test AnalysisError when analysis fails."""
        mock_capture.return_value = "screenshot.png"
        mock_analyze.side_effect = Exception("OpenAI API failed")
        
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'}):
            lens = LayoutLens()
            
            with pytest.raises(AnalysisError, match="Failed to analyze screenshot"):
                lens.analyze("https://example.com", "Is this accessible?")


class TestExceptionMessages:
    """Test exception message formatting."""
    
    def test_error_with_details(self):
        """Test error message with details."""
        error = LayoutLensError("Something failed", {
            "component": "VisionAnalyzer",
            "operation": "analyze",
            "retry_count": 3
        })
        
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
    
    @patch('layoutlens.vision.capture.URLCapture.capture_url')
    @patch('layoutlens.vision.analyzer.VisionAnalyzer.analyze_screenshot')
    def test_analysis_failure_handling(self, mock_analyze, mock_capture):
        """Test that analysis failures are handled gracefully."""
        # Setup successful capture but failed analysis
        mock_capture.return_value = "screenshot.png"
        mock_analyze.side_effect = Exception("API quota exceeded")
        
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'}):
            lens = LayoutLens()
            
            with pytest.raises(AnalysisError) as exc_info:
                lens.analyze("https://example.com", "Is this good?")
            
            error = exc_info.value
            assert error.query == "Is this good?"
            assert error.source == "https://example.com"
            assert error.confidence == 0.0
    
    def test_exception_chaining(self):
        """Test that original exceptions are preserved in the chain."""
        original = ValueError("Original error")
        wrapped = wrap_exception(original, "Context")
        
        # The original exception should be accessible
        assert "Original error" in str(wrapped)