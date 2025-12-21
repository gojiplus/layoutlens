"""Integration tests for the complete LayoutLens workflow."""

import base64
import contextlib
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from layoutlens import AuthenticationError, LayoutLens, UITestCase, UITestSuite


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
    with patch("playwright.async_api.async_playwright") as mock_pw:
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

    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
        f.write(html_content)
        temp_path = Path(f.name)

    yield str(temp_path)

    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


class TestFullWorkflow:
    """Test complete LayoutLens workflows."""

    def test_single_page_analysis(self, mock_playwright, sample_html_file):
        """Test analyzing a single HTML page."""
        # Initialize LayoutLens
        lens = LayoutLens(api_key="test_api_key")

        # Mock the vision provider response
        from layoutlens.providers.base import VisionAnalysisResponse

        mock_response = VisionAnalysisResponse(
            answer="The page has a clean, modern design with good accessibility features.",
            confidence=0.85,
            reasoning="The layout uses semantic HTML, has good color contrast, and follows responsive design principles.",
            metadata={"tokens_used": 100},
            provider="openai",
            model="gpt-4o-mini",
        )

        # Mock both capture and vision provider
        with patch.object(lens, "capture_only", return_value="/fake/screenshot/path.png") as mock_capture, patch.object(
            lens.vision_provider, "analyze_image", return_value=mock_response
        ):
            # Analyze the page
            result = lens.analyze(
                source=sample_html_file,
                query="Is this page accessible and well-designed?",
                viewport="desktop",
            )

            # Verify results
            assert result.answer == "The page has a clean, modern design with good accessibility features."
            assert result.confidence == 0.85
            assert result.reasoning is not None
            assert result.source == sample_html_file
            assert result.query == "Is this page accessible and well-designed?"

    def test_page_comparison(self, mock_playwright, sample_html_file):
        """Test comparing two pages."""
        # Initialize LayoutLens
        lens = LayoutLens(api_key="test_api_key")

        # Create second temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write("<html><body>Second page</body></html>")
            second_file = f.name

        try:
            # Mock vision provider responses for individual analyses
            from layoutlens.providers.base import VisionAnalysisResponse

            mock_response1 = VisionAnalysisResponse(
                answer="The first page has basic design elements.",
                confidence=0.60,
                reasoning="Simple layout but lacks modern design principles.",
                metadata={"tokens_used": 80},
                provider="openai",
                model="gpt-4o-mini",
            )
            mock_response2 = VisionAnalysisResponse(
                answer="The second design is more modern and user-friendly.",
                confidence=0.78,
                reasoning="The second page has better visual hierarchy and cleaner layout.",
                metadata={"tokens_used": 100},
                provider="openai",
                model="gpt-4o-mini",
            )

            # Mock both individual analyses and comparison
            with patch.object(lens.vision_provider, "analyze_image", side_effect=[mock_response1, mock_response2]):
                # Compare pages
                result = lens.compare(sources=[sample_html_file, second_file], query="Which design is better?")

                # Verify results
                assert "second" in result.answer.lower() or "modern" in result.answer.lower()
                assert result.confidence == 0.78
                assert len(result.sources) == 2

        finally:
            # Cleanup
            Path(second_file).unlink()

    def test_batch_analysis(self, mock_playwright, sample_html_file):
        """Test batch analysis of multiple queries."""
        # Initialize LayoutLens
        lens = LayoutLens(api_key="test_api_key")

        # Different responses for different queries
        from layoutlens.providers.base import VisionAnalysisResponse

        mock_responses = [
            VisionAnalysisResponse(
                answer="Yes, the navigation is visible",
                confidence=0.9,
                reasoning="Clear nav elements",
                metadata={"tokens_used": 100},
                provider="openai",
                model="gpt-4o-mini",
            ),
            VisionAnalysisResponse(
                answer="Yes, it is mobile-friendly",
                confidence=0.8,
                reasoning="Responsive design detected",
                metadata={"tokens_used": 100},
                provider="openai",
                model="gpt-4o-mini",
            ),
            VisionAnalysisResponse(
                answer="Good color contrast",
                confidence=0.85,
                reasoning="WCAG compliant",
                metadata={"tokens_used": 100},
                provider="openai",
                model="gpt-4o-mini",
            ),
        ]

        # Run batch analysis
        queries = [
            "Is the navigation visible?",
            "Is it mobile-friendly?",
            "Does it have good color contrast?",
        ]

        # Mock vision provider responses
        with patch.object(lens.vision_provider, "analyze_image", side_effect=mock_responses):
            results = lens.analyze_batch(sources=[sample_html_file], queries=queries, viewport="desktop")

            # Verify results
            assert len(results.results) == 3
            assert results.total_queries == 3
            assert results.successful_queries == 3

            # Verify each result
            expected_answers = ["Yes, the navigation is visible", "Yes, it is mobile-friendly", "Good color contrast"]
            expected_confidences = [0.9, 0.8, 0.85]
            for i, result in enumerate(results.results):
                assert result.answer == expected_answers[i]
                assert result.confidence == expected_confidences[i]

    @patch("openai.OpenAI")
    def test_test_suite_execution(self, mock_openai_class, mock_playwright, sample_html_file):
        """Test running a complete test suite."""
        # Setup OpenAI mock
        mock_client = create_mock_openai_client()
        mock_openai_class.return_value = mock_client

        # Create test suite
        test_case1 = UITestCase(
            name="Accessibility Test",
            html_path=sample_html_file,
            queries=["Is this page accessible?", "Does it follow WCAG guidelines?"],
            viewports=["desktop", "mobile_portrait"],
        )

        test_case2 = UITestCase(
            name="Design Test",
            html_path=sample_html_file,
            queries=["Is the design modern?"],
            viewports=["desktop"],
        )

        suite = UITestSuite(
            name="Integration Test Suite",
            description="Testing full workflow",
            test_cases=[test_case1, test_case2],
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

    def test_built_in_checks(self, mock_playwright):
        """Test built-in check methods."""
        # Initialize LayoutLens
        lens = LayoutLens(api_key="test_api_key")

        # Mock vision provider response for accessibility check
        from layoutlens.providers.base import VisionAnalysisResponse

        mock_response = VisionAnalysisResponse(
            answer="The page is accessible with good color contrast and semantic HTML.",
            confidence=0.88,
            reasoning="All accessibility checks passed.",
            metadata={"tokens_used": 100},
            provider="openai",
            model="gpt-4o-mini",
        )

        # Test accessibility check
        with patch.object(lens.vision_provider, "analyze_image", return_value=mock_response):
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

    @patch("openai.OpenAI")
    def test_api_error_handling(self, mock_openai_class, sample_html_file):
        """Test handling of OpenAI API errors."""
        # Setup OpenAI mock to raise error
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API rate limit exceeded")
        mock_openai_class.return_value = mock_client

        # Initialize LayoutLens
        lens = LayoutLens(api_key="test_api_key")

        # Attempt analysis - should handle error gracefully
        with patch("layoutlens.vision.capture.URLCapture.capture_url") as mock_capture:
            mock_capture.return_value = "screenshot.png"

            result = lens.analyze(source=sample_html_file, query="Is this accessible?")

            # Should return error result with low confidence
            assert result.confidence == 0.0
            assert "error" in result.answer.lower() or "failed" in result.answer.lower()

    @patch("openai.OpenAI")
    def test_invalid_html_handling(self, mock_openai_class, mock_playwright):
        """Test handling of invalid HTML files."""
        # Create invalid HTML file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write("This is not valid HTML")
            invalid_file = f.name

        try:
            # Setup OpenAI mock
            mock_client = create_mock_openai_client()
            mock_openai_class.return_value = mock_client

            # Initialize LayoutLens
            lens = LayoutLens(api_key="test_api_key")

            # Should still work with invalid HTML
            result = lens.analyze(source=invalid_file, query="Can you analyze this?")

            assert result is not None

        finally:
            Path(invalid_file).unlink()

    def test_missing_api_key(self):
        """Test initialization without API key."""
        with patch.dict("os.environ", {}, clear=True), pytest.raises(AuthenticationError, match="API key"):
            lens = LayoutLens()


class TestCLIIntegration:
    """Test CLI command integration."""

    @patch("openai.OpenAI")
    @patch("layoutlens.api.core.LayoutLens")
    def test_cli_test_command(self, mock_lens_class, mock_openai_class):
        """Test the CLI test command."""
        from argparse import Namespace

        from layoutlens.cli import cmd_test

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
            suite=None,
        )

        # Run command
        try:
            cmd_test(args)
        except SystemExit as e:
            # Should exit with 0 on success
            assert e.code == 0 or e.code is None

        # Verify analyze was called
        mock_lens.analyze.assert_called_once()

    @patch("layoutlens.cli.UITestSuite")
    @patch("layoutlens.api.core.LayoutLens")
    def test_cli_suite_command(self, mock_lens_class, mock_suite_class):
        """Test the CLI test suite command."""
        from argparse import Namespace

        from layoutlens.cli import cmd_test

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
            output="output",
            model="gpt-4o-mini",
            provider="litellm",
        )

        # Run command
        with contextlib.suppress(SystemExit):
            cmd_test(args)

        # Verify suite was loaded (note: sync CLI doesn't support suite execution)
        mock_suite_class.load.assert_called_once()
        # Note: run_test_suite is not called because sync CLI redirects to async CLI for suite execution
