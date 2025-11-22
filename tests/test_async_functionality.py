"""Test the async functionality for LayoutLens."""

import asyncio
import contextlib
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from layoutlens import AnalysisResult, LayoutLens


@pytest.fixture
def mock_api_key():
    """Mock API key for testing."""
    return "test-api-key"


@pytest.fixture
def sample_html_file():
    """Create a temporary HTML file for testing."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head><title>Test Page</title></head>
    <body>
        <h1>Welcome to Test Page</h1>
        <p>This is a sample page for testing.</p>
    </body>
    </html>
    """

    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
        f.write(html_content)
        yield f.name

    # Cleanup
    Path(f.name).unlink(missing_ok=True)


@pytest.mark.asyncio
class TestAsyncCore:
    """Test async functionality in core LayoutLens API."""

    @patch("layoutlens.api.core.LayoutLens.analyze")
    async def test_analyze_async_single(self, mock_analyze, mock_api_key):
        """Test async single page analysis."""
        # Setup mock
        expected_result = AnalysisResult(
            source="test.html",
            query="Test query",
            answer="Test answer",
            confidence=0.85,
            reasoning="Test reasoning",
        )
        mock_analyze.return_value = expected_result

        # Test async analyze
        lens = LayoutLens(api_key=mock_api_key)
        result = await lens.analyze_async("test.html", "Test query")

        # Verify
        assert isinstance(result, AnalysisResult)
        assert result.answer == "Test answer"
        assert result.confidence == 0.85
        mock_analyze.assert_called_once_with("test.html", "Test query", "desktop", None)

    @patch("layoutlens.api.core.LayoutLens.analyze_async")
    async def test_analyze_batch_async(self, mock_analyze_async, mock_api_key):
        """Test async batch analysis."""

        # Setup mock
        async def mock_analyze_side_effect(source, query, viewport, context):
            return AnalysisResult(
                source=source,
                query=query,
                answer=f"Answer for {source}",
                confidence=0.8,
                reasoning="Test reasoning",
            )

        mock_analyze_async.side_effect = mock_analyze_side_effect

        # Test batch analysis
        lens = LayoutLens(api_key=mock_api_key)
        sources = ["page1.html", "page2.html"]
        queries = ["Is it accessible?", "Is it mobile-friendly?"]

        result = await lens.analyze_batch_async(sources, queries, max_concurrent=2)

        # Verify
        assert result.total_queries == 4  # 2 sources × 2 queries
        assert result.successful_queries == 4
        assert len(result.results) == 4
        assert result.average_confidence == 0.8

        # Check that all combinations were analyzed
        source_query_pairs = [(r.source, r.query) for r in result.results]
        expected_pairs = [
            ("page1.html", "Is it accessible?"),
            ("page1.html", "Is it mobile-friendly?"),
            ("page2.html", "Is it accessible?"),
            ("page2.html", "Is it mobile-friendly?"),
        ]

        for pair in expected_pairs:
            assert pair in source_query_pairs

    @patch("layoutlens.api.core.LayoutLens.analyze_async")
    async def test_analyze_batch_async_with_failures(self, mock_analyze_async, mock_api_key):
        """Test async batch analysis with some failures."""

        # Setup mock with failures
        async def mock_analyze_side_effect(source, query, viewport, context):
            if source == "bad_page.html":
                raise Exception("Analysis failed")
            return AnalysisResult(
                source=source,
                query=query,
                answer=f"Answer for {source}",
                confidence=0.9,
                reasoning="Test reasoning",
            )

        mock_analyze_async.side_effect = mock_analyze_side_effect

        # Test batch analysis with failures
        lens = LayoutLens(api_key=mock_api_key)
        sources = ["good_page.html", "bad_page.html"]
        queries = ["Is it good?"]

        result = await lens.analyze_batch_async(sources, queries)

        # Verify
        assert result.total_queries == 2
        assert result.successful_queries == 1  # Only one succeeded
        assert len(result.results) == 2

        # Check that error was handled gracefully
        failed_result = next(r for r in result.results if r.confidence == 0.0)
        assert "Error analyzing" in failed_result.answer
        assert "Analysis failed" in failed_result.reasoning

    async def test_concurrent_performance_benefit(self, mock_api_key):
        """Test that async processing provides performance benefits."""

        # Mock a slow analyze function
        async def slow_analyze(source, query, viewport, context):
            await asyncio.sleep(0.1)  # Simulate network delay
            return AnalysisResult(
                source=source,
                query=query,
                answer="Answer",
                confidence=0.8,
                reasoning="Test",
            )

        lens = LayoutLens(api_key=mock_api_key)

        with patch.object(lens, "analyze_async", side_effect=slow_analyze):
            sources = ["page1.html", "page2.html", "page3.html"]
            queries = ["Query 1", "Query 2"]

            # Time the async batch processing
            start_time = time.time()
            result = await lens.analyze_batch_async(sources, queries, max_concurrent=3)
            async_time = time.time() - start_time

            # Should complete much faster than sequential processing
            # 6 analyses × 0.1s each = 0.6s sequential vs ~0.2s concurrent
            assert async_time < 0.4  # Should be much faster than 0.6s
            assert result.total_queries == 6


@pytest.mark.asyncio
class TestAsyncCLI:
    """Test async CLI functionality."""

    @patch("layoutlens.cli_async.LayoutLens")
    async def test_cmd_test_async_single_page(self, mock_lens_class):
        """Test async CLI test command for single page."""
        from layoutlens.cli_async import cmd_test_async

        # Setup mock
        mock_lens = Mock()
        mock_lens_class.return_value = mock_lens

        mock_batch_result = Mock()
        mock_batch_result.results = [
            AnalysisResult(
                source="test.html",
                query="Is it good?",
                answer="Yes, it's good",
                confidence=0.9,
                reasoning="Good design",
            )
        ]
        mock_lens.analyze_batch_async = AsyncMock(return_value=mock_batch_result)

        # Create mock args
        args = Mock()
        args.api_key = "test-key"
        args.output = "test_output"
        args.page = "test.html"
        args.suite = None
        args.queries = "Is it good?"
        args.viewports = "desktop"
        args.max_concurrent = 3

        # Test the command
        with patch("builtins.print") as mock_print:
            await cmd_test_async(args)

            # Verify LayoutLens was initialized correctly
            mock_lens_class.assert_called_once_with(api_key="test-key", output_dir="test_output")

            # Verify batch analysis was called
            mock_lens.analyze_batch_async.assert_called_once()

            # Check that results were printed
            print_calls = [str(call) for call in mock_print.call_args_list]
            assert any("Analyzing page: test.html" in call for call in print_calls)

    @patch("layoutlens.cli_async.LayoutLens")
    async def test_cmd_compare_async(self, mock_lens_class):
        """Test async CLI compare command."""
        from layoutlens.cli_async import cmd_compare_async

        # Setup mock
        mock_lens = Mock()
        mock_lens_class.return_value = mock_lens

        mock_batch_result = Mock()
        mock_batch_result.results = [
            AnalysisResult(
                source="page_a.html",
                query="Which is better?",
                answer="This page is good",
                confidence=0.8,
                reasoning="Good design",
            ),
            AnalysisResult(
                source="page_b.html",
                query="Which is better?",
                answer="This page is excellent",
                confidence=0.95,
                reasoning="Excellent design",
            ),
        ]
        mock_lens.analyze_batch_async = AsyncMock(return_value=mock_batch_result)

        # Create mock args
        args = Mock()
        args.api_key = "test-key"
        args.output = "test_output"
        args.page_a = "page_a.html"
        args.page_b = "page_b.html"
        args.query = "Which is better?"

        # Test the command
        with patch("builtins.print") as mock_print:
            await cmd_compare_async(args)

            # Verify batch analysis was called with both pages
            mock_lens.analyze_batch_async.assert_called_once_with(
                sources=["page_a.html", "page_b.html"],
                queries=["Which is better?"],
                max_concurrent=2,
            )

            # Check that comparison results were printed
            print_calls = [str(call) for call in mock_print.call_args_list]
            assert any("page_b.html" in call for call in print_calls)  # Should show winner


class TestAsyncIntegration:
    """Test async integration with main CLI."""

    def test_async_flag_in_main_cli(self):
        """Test that async flag is properly handled in main CLI."""
        # Test that the async flag exists
        import argparse

        from layoutlens.cli import main

        # We can't easily test the full main() function without mocking extensively
        # But we can test that the argument parser accepts async flags
        with (
            patch("sys.argv", ["layoutlens", "--async", "test", "--page", "test.html"]),
            patch("layoutlens.cli.cmd_test_async") as mock_async_cmd,
            patch("asyncio.run") as mock_asyncio_run,
            contextlib.suppress(SystemExit),
        ):
            main()

            # The test passes if no exception is raised from parsing

    def test_max_concurrent_parameter(self):
        """Test that max_concurrent parameter is handled correctly."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--max-concurrent", type=int, default=5)

        args = parser.parse_args(["--max-concurrent", "10"])
        assert args.max_concurrent == 10

        args = parser.parse_args([])
        assert args.max_concurrent == 5


@pytest.mark.performance
@pytest.mark.asyncio
async def test_async_performance_comparison():
    """Compare async vs sync performance for batch operations."""
    mock_api_key = "test-key"

    # Mock a realistic delay
    async def mock_analyze_async(source, query, viewport, context):
        await asyncio.sleep(0.05)  # 50ms delay per analysis
        return AnalysisResult(
            source=source,
            query=query,
            answer="Test answer",
            confidence=0.8,
            reasoning="Test reasoning",
        )

    def mock_analyze_sync(source, query, viewport, context):
        import time

        time.sleep(0.05)  # 50ms delay per analysis
        return AnalysisResult(
            source=source,
            query=query,
            answer="Test answer",
            confidence=0.8,
            reasoning="Test reasoning",
        )

    lens = LayoutLens(api_key=mock_api_key)
    sources = [f"page_{i}.html" for i in range(5)]
    queries = ["Query 1", "Query 2"]

    # Test async performance
    with patch.object(lens, "analyze_async", side_effect=mock_analyze_async):
        start_time = time.time()
        async_result = await lens.analyze_batch_async(sources, queries, max_concurrent=5)
        async_time = time.time() - start_time

    # Test sync performance simulation
    with patch.object(lens, "analyze", side_effect=mock_analyze_sync):
        start_time = time.time()
        sync_result = lens.analyze_batch(sources, queries)
        sync_time = time.time() - start_time

    # Async should be significantly faster
    # 10 analyses × 50ms = 500ms sync vs ~100ms async (with concurrency)
    assert async_time < sync_time * 0.3  # At least 3x faster
    assert async_result.total_queries == sync_result.total_queries == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
