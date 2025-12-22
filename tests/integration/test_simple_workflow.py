"""Simple integration tests for the LayoutLens workflow."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from layoutlens import LayoutLens


class TestSimpleWorkflow:
    """Test simple LayoutLens workflows with current architecture."""

    @patch("layoutlens.capture.Capture.screenshots")
    @patch("layoutlens.api.core.acompletion")
    @pytest.mark.asyncio
    async def test_single_page_analysis(self, mock_acompletion, mock_capture):
        """Test analyzing a single HTML page with current architecture."""
        # Setup mocks
        mock_capture.return_value = ["/fake/screenshot.png"]

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[
            0
        ].message.content = '{"answer": "The page has good accessibility features.", "confidence": 0.85, "reasoning": "Clear navigation and semantic HTML."}'
        mock_response.usage.total_tokens = 150
        mock_acompletion.return_value = mock_response

        # Create temporary HTML file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write("<html><head><title>Test</title></head><body><h1>Test Page</h1></body></html>")
            temp_file = f.name

        try:
            with (
                patch("os.path.exists", return_value=True),
                patch("layoutlens.api.core.LayoutLens._encode_image", return_value="fake-base64"),
            ):
                # Initialize LayoutLens
                lens = LayoutLens(api_key="test-key")

                # Analyze the page
                result = await lens.analyze(
                    source="https://example.com", query="Is this page accessible?", viewport="desktop"
                )

                # Verify results
                assert result.answer == "The page has good accessibility features."
                assert result.confidence == 0.85
                assert result.source == "https://example.com"
                assert result.query == "Is this page accessible?"

        finally:
            # Cleanup
            Path(temp_file).unlink()

    @patch("layoutlens.capture.Capture.screenshots")
    @patch("layoutlens.api.core.acompletion")
    @pytest.mark.asyncio
    async def test_page_comparison(self, mock_acompletion, mock_capture):
        """Test comparing two pages with current architecture."""
        # Setup mocks
        mock_capture.return_value = ["/fake/screenshot1.png", "/fake/screenshot2.png"]

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[
            0
        ].message.content = (
            '{"answer": "The second design is better.", "confidence": 0.78, "reasoning": "Better visual hierarchy."}'
        )
        mock_response.usage.total_tokens = 120
        mock_acompletion.return_value = mock_response

        with (
            patch("os.path.exists", return_value=True),
            patch("layoutlens.api.core.LayoutLens._encode_image", return_value="fake-base64"),
        ):
            # Initialize LayoutLens
            lens = LayoutLens(api_key="test-key")

            # Compare pages
            result = await lens.compare(sources=["page1.html", "page2.html"], query="Which design is better?")

            # Verify results
            assert "second" in result.answer.lower()
            assert result.confidence == 0.78
            assert len(result.sources) == 2
