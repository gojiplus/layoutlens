"""Integration tests for the complete LayoutLens workflow."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import base64

import pytest

from layoutlens import LayoutLens, TestCase, TestSuite, AuthenticationError


def create_mock_openai_client():
    """Create a mock OpenAI client with realistic responses."""
    mock_client = Mock()
    mock_response = Mock()
    mock_choice = Mock()
    mock_message = Mock()
    
    # Setup the response chain with format that VisionAnalyzer expects
    mock_message.content = """ANSWER: The page has a clean, modern design with good accessibility features.
CONFIDENCE: 0.85
REASONING: The layout uses semantic HTML, has good color contrast, and follows responsive design principles."""
    
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_response.usage.total_tokens = 100
    mock_client.chat.completions.create.return_value = mock_response
    
    return mock_client


@pytest.fixture
def mock_playwright():
    """Mock Playwright for screenshot capture."""
    with patch('playwright.async_api.async_playwright') as mock_pw:
        # Create mock chain
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        
        # Setup return values
        mock_pw.return_value.__aenter__.return_value.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        
        # Mock screenshot method
        mock_page.screenshot = AsyncMock(return_value=b"fake_screenshot_data")
        mock_page.goto = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.content = AsyncMock(return_value="<html><body>Test page</body></html>")
        
        mock_context.close = AsyncMock()
        mock_browser.close = AsyncMock()
        
        yield mock_pw


@pytest.fixture
def sample_html_file():
    """Create a temporary HTML file for testing."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Page</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
            .header { background: #333; color: white; padding: 20px; }
            .main { max-width: 1200px; margin: 0 auto; }
            .button { background: #007bff; color: white; padding: 10px 20px; border: none; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Welcome to Test Page</h1>
        </div>
        <div class="main">
            <p>This is a test page for LayoutLens integration testing.</p>
            <button class="button">Click Me</button>
        </div>
    </body>
    </html>
    """
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
        f.write(html_content)
        temp_path = Path(f.name)
    
    yield str(temp_path)
    
    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


class TestFullWorkflow:
    """Test complete LayoutLens workflows."""
    
    @patch('openai.OpenAI')
    def test_single_page_analysis(self, mock_openai_class, mock_playwright, sample_html_file):
        """Test analyzing a single HTML page."""
        # Setup OpenAI mock
        mock_client = create_mock_openai_client()
        mock_openai_class.return_value = mock_client
        
        # Initialize LayoutLens
        lens = LayoutLens(api_key="test_api_key")
        
        # Analyze the page
        result = lens.analyze(
            source=sample_html_file,
            query="Is this page accessible and well-designed?",
            viewport="desktop"
        )
        
        # Verify results
        assert result.answer == "The page has a clean, modern design with good accessibility features."
        assert result.confidence == 0.85
        assert result.reasoning is not None
        assert result.source == sample_html_file
        assert result.query == "Is this page accessible and well-designed?"
        
        # Verify OpenAI was called
        mock_client.chat.completions.create.assert_called_once()
    
    @patch('openai.OpenAI')
    def test_page_comparison(self, mock_openai_class, mock_playwright, sample_html_file):
        """Test comparing two pages."""
        # Setup OpenAI mock for comparison
        mock_client = Mock()
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        
        mock_message.content = """ANSWER: The second design is more modern and user-friendly.
CONFIDENCE: 0.78
REASONING: The second page has better visual hierarchy and cleaner layout."""
        
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_response.usage.total_tokens = 100
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        # Initialize LayoutLens
        lens = LayoutLens(api_key="test_api_key")
        
        # Create second temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write("<html><body>Second page</body></html>")
            second_file = f.name
        
        try:
            # Compare pages
            result = lens.compare(
                sources=[sample_html_file, second_file],
                query="Which design is better?"
            )
            
            # Verify results
            assert "second" in result.answer.lower() or "modern" in result.answer.lower()
            assert result.confidence == 0.78
            assert len(result.sources) == 2
            
        finally:
            # Cleanup
            Path(second_file).unlink()
    
    @patch('openai.OpenAI')
    def test_batch_analysis(self, mock_openai_class, mock_playwright, sample_html_file):
        """Test batch analysis of multiple queries."""
        # Setup OpenAI mock
        mock_client = Mock()
        
        # Different responses for different queries
        responses = [
            {"answer": "Yes, the navigation is visible", "confidence": 0.9, "reasoning": "Clear nav elements"},
            {"answer": "Yes, it is mobile-friendly", "confidence": 0.8, "reasoning": "Responsive design detected"},
            {"answer": "Good color contrast", "confidence": 0.85, "reasoning": "WCAG compliant"}
        ]
        
        def create_response(resp):
            mock_resp = Mock()
            mock_resp.choices = [Mock(message=Mock(content=f"""ANSWER: {resp['answer']}
CONFIDENCE: {resp['confidence']}
REASONING: {resp['reasoning']}"""))]
            mock_resp.usage.total_tokens = 100
            return mock_resp
        
        mock_client.chat.completions.create.side_effect = [
            create_response(resp) for resp in responses
        ]
        
        mock_openai_class.return_value = mock_client
        
        # Initialize LayoutLens
        lens = LayoutLens(api_key="test_api_key")
        
        # Run batch analysis
        queries = [
            "Is the navigation visible?",
            "Is it mobile-friendly?",
            "Does it have good color contrast?"
        ]
        
        results = lens.analyze_batch(
            sources=[sample_html_file],
            queries=queries,
            viewport="desktop"
        )
        
        # Verify results
        assert len(results.results) == 3
        assert results.total_queries == 3
        assert results.successful_queries == 3
        
        # Verify each result
        for i, result in enumerate(results.results):
            assert result.answer == responses[i]["answer"]
            assert result.confidence == responses[i]["confidence"]
    
    @patch('openai.OpenAI')
    def test_test_suite_execution(self, mock_openai_class, mock_playwright, sample_html_file):
        """Test running a complete test suite."""
        # Setup OpenAI mock
        mock_client = create_mock_openai_client()
        mock_openai_class.return_value = mock_client
        
        # Create test suite
        test_case1 = TestCase(
            name="Accessibility Test",
            html_path=sample_html_file,
            queries=["Is this page accessible?", "Does it follow WCAG guidelines?"],
            viewports=["desktop", "mobile_portrait"]
        )
        
        test_case2 = TestCase(
            name="Design Test",
            html_path=sample_html_file,
            queries=["Is the design modern?"],
            viewports=["desktop"]
        )
        
        suite = TestSuite(
            name="Integration Test Suite",
            description="Testing full workflow",
            test_cases=[test_case1, test_case2]
        )
        
        # Initialize LayoutLens and run suite
        lens = LayoutLens(api_key="test_api_key")
        results = lens.run_test_suite(suite)
        
        # Verify results
        assert len(results) == 2
        
        # Check first test case results
        assert results[0].suite_name == "Integration Test Suite"
        assert results[0].test_case_name == "Accessibility Test"
        assert results[0].total_tests == 4  # 2 queries × 2 viewports
        
        # Check second test case results  
        assert results[1].test_case_name == "Design Test"
        assert results[1].total_tests == 1  # 1 query × 1 viewport
    
    @patch('openai.OpenAI')
    def test_built_in_checks(self, mock_openai_class, mock_playwright):
        """Test built-in check methods."""
        # Setup OpenAI mock
        mock_client = Mock()
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        
        mock_message.content = """ANSWER: The page is accessible with good color contrast and semantic HTML.
CONFIDENCE: 0.88
REASONING: All accessibility checks passed."""
        
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_response.usage.total_tokens = 100
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        # Initialize LayoutLens
        lens = LayoutLens(api_key="test_api_key")
        
        # Test accessibility check
        result = lens.check_accessibility("https://example.com")
        assert result.confidence == 0.88
        assert "accessible" in result.answer.lower()
        
        # Test mobile-friendly check
        result = lens.check_mobile_friendly("https://example.com")
        assert result is not None
        
        # Test conversion optimization check
        result = lens.check_conversion_optimization("https://example.com")
        assert result is not None


class TestErrorHandling:
    """Test error handling in integration scenarios."""
    
    @patch('openai.OpenAI')
    def test_api_error_handling(self, mock_openai_class, sample_html_file):
        """Test handling of OpenAI API errors."""
        # Setup OpenAI mock to raise error
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API rate limit exceeded")
        mock_openai_class.return_value = mock_client
        
        # Initialize LayoutLens
        lens = LayoutLens(api_key="test_api_key")
        
        # Attempt analysis - should handle error gracefully
        with patch('layoutlens.vision.capture.URLCapture.capture_url') as mock_capture:
            mock_capture.return_value = "screenshot.png"
            
            result = lens.analyze(
                source=sample_html_file,
                query="Is this accessible?"
            )
            
            # Should return error result with low confidence
            assert result.confidence == 0.0
            assert "error" in result.answer.lower() or "failed" in result.answer.lower()
    
    @patch('openai.OpenAI')
    def test_invalid_html_handling(self, mock_openai_class, mock_playwright):
        """Test handling of invalid HTML files."""
        # Create invalid HTML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write("This is not valid HTML")
            invalid_file = f.name
        
        try:
            # Setup OpenAI mock
            mock_client = create_mock_openai_client()
            mock_openai_class.return_value = mock_client
            
            # Initialize LayoutLens
            lens = LayoutLens(api_key="test_api_key")
            
            # Should still work with invalid HTML
            result = lens.analyze(
                source=invalid_file,
                query="Can you analyze this?"
            )
            
            assert result is not None
            
        finally:
            Path(invalid_file).unlink()
    
    def test_missing_api_key(self):
        """Test initialization without API key."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(AuthenticationError, match="API key"):
                lens = LayoutLens()


class TestCLIIntegration:
    """Test CLI command integration."""
    
    @patch('openai.OpenAI')
    @patch('layoutlens.cli.LayoutLens')
    def test_cli_test_command(self, mock_lens_class, mock_openai_class):
        """Test the CLI test command."""
        from layoutlens.cli import cmd_test
        from argparse import Namespace
        
        # Setup mock
        mock_lens = Mock()
        mock_result = Mock()
        mock_result.answer = "Page is well-designed"
        mock_result.confidence = 0.9
        mock_lens.analyze.return_value = mock_result
        mock_lens_class.return_value = mock_lens
        
        # Create args
        args = Namespace(
            page="test.html",
            queries="Is it good?",
            viewports="desktop",
            api_key="test_key",
            output="output",
            suite=None
        )
        
        # Run command
        try:
            cmd_test(args)
        except SystemExit as e:
            # Should exit with 0 on success
            assert e.code == 0 or e.code is None
        
        # Verify analyze was called
        mock_lens.analyze.assert_called_once()
    
    @patch('layoutlens.cli.TestSuite')
    @patch('layoutlens.cli.LayoutLens')
    def test_cli_suite_command(self, mock_lens_class, mock_suite_class):
        """Test the CLI test suite command."""
        from layoutlens.cli import cmd_test
        from argparse import Namespace
        
        # Setup mocks
        mock_lens = Mock()
        mock_suite = Mock()
        mock_suite.name = "Test Suite"
        mock_suite.description = "Test description"
        mock_suite.test_cases = []
        
        mock_result = Mock()
        mock_result.suite_name = "Test Suite"
        mock_result.test_case_name = "Test"
        mock_result.total_tests = 1
        mock_result.passed_tests = 1
        mock_result.failed_tests = 0
        mock_result.success_rate = 1.0
        mock_result.duration_seconds = 1.5
        
        mock_lens.run_test_suite.return_value = [mock_result]
        mock_lens_class.return_value = mock_lens
        mock_suite_class.load.return_value = mock_suite
        
        # Create args
        args = Namespace(
            page=None,
            suite="test_suite.json",
            api_key="test_key",
            output="output"
        )
        
        # Run command
        try:
            cmd_test(args)
        except SystemExit:
            pass  # Expected to exit
        
        # Verify suite was loaded and run
        mock_suite_class.load.assert_called_once()
        mock_lens.run_test_suite.assert_called_once()