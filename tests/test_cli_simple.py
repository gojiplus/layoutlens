"""Tests for the simplified LayoutLens CLI."""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from layoutlens.api.core import AnalysisResult, BatchResult, ComparisonResult
from layoutlens.cli import main


@pytest.mark.asyncio
class TestSimpleCLI:
    """Test the simplified CLI."""

    @patch("layoutlens.cli.LayoutLens")
    async def test_basic_analysis(self, mock_lens_class):
        """Test basic URL analysis."""
        # Setup mock
        mock_lens = Mock()
        mock_lens_class.return_value = mock_lens

        mock_result = AnalysisResult(
            source="https://example.com",
            query="Is it accessible?",
            answer="Yes, the page is accessible",
            confidence=0.9,
            reasoning="Good contrast and ARIA labels",
        )
        mock_lens.analyze = AsyncMock(return_value=mock_result)

        # Test with args
        test_args = ["layoutlens", "https://example.com", "Is it accessible?"]
        with patch("sys.argv", test_args):
            result = await main()

        assert result == 0
        mock_lens.analyze.assert_called_once_with(
            source="https://example.com", query="Is it accessible?", viewport="desktop"
        )

    @patch("layoutlens.cli.LayoutLens")
    async def test_compare_mode(self, mock_lens_class):
        """Test compare mode."""
        # Setup mock
        mock_lens = Mock()
        mock_lens_class.return_value = mock_lens

        mock_result = ComparisonResult(
            sources=["page1.html", "page2.html"],
            query="Which is better?",
            answer="Page 2 has better design",
            confidence=0.85,
            reasoning="Improved layout and accessibility",
        )
        mock_lens.compare = AsyncMock(return_value=mock_result)

        # Test with args
        test_args = ["layoutlens", "page1.html", "page2.html", "--compare"]
        with patch("sys.argv", test_args), patch("pathlib.Path.exists", return_value=True):
            result = await main()

        assert result == 0
        mock_lens.compare.assert_called_once()

    @patch("layoutlens.cli.LayoutLens")
    async def test_json_output(self, mock_lens_class, capsys):
        """Test JSON output format."""
        # Setup mock
        mock_lens = Mock()
        mock_lens_class.return_value = mock_lens

        mock_result = Mock()
        mock_result.to_json = Mock(return_value='{"test": "json"}')
        mock_lens.analyze = AsyncMock(return_value=mock_result)

        # Test with args
        test_args = ["layoutlens", "test.html", "--output", "json"]
        with patch("sys.argv", test_args), patch("pathlib.Path.exists", return_value=True):
            result = await main()

        captured = capsys.readouterr()
        assert '{"test": "json"}' in captured.out
        assert result == 0

    @patch("layoutlens.cli.LayoutLens")
    async def test_text_output(self, mock_lens_class, capsys):
        """Test human-readable text output."""
        # Setup mock
        mock_lens = Mock()
        mock_lens_class.return_value = mock_lens

        mock_result = AnalysisResult(
            source="test.html", query="Is it good?", answer="Yes, it's good", confidence=0.8, reasoning="Clean design"
        )
        mock_lens.analyze = AsyncMock(return_value=mock_result)

        # Test with args
        test_args = ["layoutlens", "test.html", "Is it good?", "--output", "text"]
        with patch("sys.argv", test_args), patch("pathlib.Path.exists", return_value=True):
            result = await main()

        captured = capsys.readouterr()
        assert "📍 test.html" in captured.out
        assert "✅ Yes, it's good" in captured.out
        assert "📊 Confidence: 80%" in captured.out
        assert result == 0

    @patch("layoutlens.cli.LayoutLens")
    async def test_batch_analysis(self, mock_lens_class):
        """Test multiple sources."""
        # Setup mock
        mock_lens = Mock()
        mock_lens_class.return_value = mock_lens

        mock_result = BatchResult(
            results=[
                AnalysisResult(
                    source="page1.html", query="Is it good?", answer="Yes", confidence=0.9, reasoning="Good"
                ),
                AnalysisResult(
                    source="page2.html", query="Is it good?", answer="Yes", confidence=0.8, reasoning="Also good"
                ),
            ],
            total_queries=2,
            successful_queries=2,
            average_confidence=0.85,
            total_execution_time=1.0,
        )
        mock_lens.analyze = AsyncMock(return_value=mock_result)

        # Test with args
        test_args = ["layoutlens", "page1.html", "page2.html", "--query", "Is it good?"]
        with patch("sys.argv", test_args), patch("pathlib.Path.exists", return_value=True):
            result = await main()

        assert result == 0
        mock_lens.analyze.assert_called_once_with(
            source=["page1.html", "page2.html"], query="Is it good?", viewport="desktop"
        )

    async def test_no_args_shows_help(self, capsys):
        """Test that no arguments shows help."""
        test_args = ["layoutlens"]
        with patch("sys.argv", test_args):
            result = await main()

        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower()
        assert result == 0

    async def test_error_handling(self, capsys):
        """Test error handling with no valid sources."""
        # Test case where no sources are detected (shows help)
        test_args = ["layoutlens", "--query", "Test query with no sources"]
        with patch("sys.argv", test_args):
            result = await main()

        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower()
        assert result == 0  # Help returns 0, not 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
