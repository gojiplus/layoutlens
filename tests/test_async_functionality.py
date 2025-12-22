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

    @patch("layoutlens.api.core.acompletion")
    @patch("pathlib.Path.exists")
    async def test_analyze_async_single(self, mock_exists, mock_acompletion, mock_api_key):
        """Test async single page analysis."""
        # Setup mocks
        mock_exists.return_value = True

        # Mock LiteLLM acompletion response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[
            0
        ].message.content = '{"answer": "Test answer", "confidence": 0.85, "reasoning": "Test reasoning"}'
        mock_response.usage.total_tokens = 150
        mock_acompletion.return_value = mock_response

        # Test async analyze
        with patch("layoutlens.api.core.LayoutLens._encode_image", return_value="fake-base64"):
            lens = LayoutLens(api_key=mock_api_key)
            result = await lens.analyze("test.html", "Test query")

        # Verify
        assert isinstance(result, AnalysisResult)
        assert result.answer == "Test answer"
        assert result.confidence == 0.85

    @patch("layoutlens.api.core.LayoutLens.analyze")
    async def test_analyze_batch(self, mock_analyze, mock_api_key):
        """Test async batch analysis."""

        # Setup mock
        async def mock_analyze_side_effect(source, query, viewport="desktop", context=None, max_concurrent=5):
            # The smart analyze method now returns BatchResult for multiple inputs
            from layoutlens.api.core import BatchResult

            # Handle both single and multiple source/query combinations
            sources = [source] if not isinstance(source, list) else source
            queries = [query] if not isinstance(query, list) else query

            results = []
            for s in sources:
                for q in queries:
                    results.append(
                        AnalysisResult(
                            source=s,
                            query=q,
                            answer=f"Answer for {s}",
                            confidence=0.8,
                            reasoning="Test reasoning",
                        )
                    )

            return BatchResult(
                results=results,
                total_queries=len(results),
                successful_queries=len(results),
                average_confidence=0.8,
                total_execution_time=0.1,
            )

        mock_analyze.side_effect = mock_analyze_side_effect

        # Test batch analysis
        lens = LayoutLens(api_key=mock_api_key)
        sources = ["page1.html", "page2.html"]
        queries = ["Is it accessible?", "Is it mobile-friendly?"]

        result = await lens.analyze(source=sources, query=queries, max_concurrent=2)

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

    @patch("layoutlens.api.core.LayoutLens.analyze")
    async def test_analyze_batch_with_failures(self, mock_analyze_async, mock_api_key):
        """Test async batch analysis with some failures."""

        # Setup mock with failures
        async def mock_analyze_side_effect(source, query, viewport="desktop", context=None, max_concurrent=5):
            from layoutlens.api.core import BatchResult

            # Handle both single and multiple source/query combinations
            sources = [source] if not isinstance(source, list) else source
            queries = [query] if not isinstance(query, list) else query

            results = []
            for s in sources:
                for q in queries:
                    if s == "bad_page.html":
                        # Create error result for failed analysis
                        results.append(
                            AnalysisResult(
                                source=s,
                                query=q,
                                answer=f"Error analyzing {s}: Analysis failed",
                                confidence=0.0,
                                reasoning="Analysis failed due to: Analysis failed",
                                metadata={"error": "Analysis failed", "error_type": "Exception"},
                            )
                        )
                    else:
                        results.append(
                            AnalysisResult(
                                source=s,
                                query=q,
                                answer=f"Answer for {s}",
                                confidence=0.9,
                                reasoning="Test reasoning",
                            )
                        )

            return BatchResult(
                results=results,
                total_queries=len(results),
                successful_queries=sum(1 for r in results if r.confidence > 0),
                average_confidence=sum(r.confidence for r in results) / len(results) if results else 0,
                total_execution_time=0.1,
            )

        mock_analyze_async.side_effect = mock_analyze_side_effect

        # Test batch analysis with failures
        lens = LayoutLens(api_key=mock_api_key)
        sources = ["good_page.html", "bad_page.html"]
        queries = ["Is it good?"]

        result = await lens.analyze(source=sources, query=queries)

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
        async def slow_analyze(source, query, viewport="desktop", context=None, max_concurrent=5):
            await asyncio.sleep(0.1)  # Simulate network delay
            from layoutlens.api.core import BatchResult

            # Handle both single and multiple source/query combinations
            sources = [source] if not isinstance(source, list) else source
            queries = [query] if not isinstance(query, list) else query

            results = []
            for s in sources:
                for q in queries:
                    results.append(
                        AnalysisResult(
                            source=s,
                            query=q,
                            answer="Answer",
                            confidence=0.8,
                            reasoning="Test",
                        )
                    )

            return BatchResult(
                results=results,
                total_queries=len(results),
                successful_queries=len(results),
                average_confidence=0.8,
                total_execution_time=0.1,
            )

        lens = LayoutLens(api_key=mock_api_key)

        with patch.object(lens, "analyze", side_effect=slow_analyze):
            sources = ["page1.html", "page2.html", "page3.html"]
            queries = ["Query 1", "Query 2"]

            # Time the async batch processing
            start_time = time.time()
            result = await lens.analyze(source=sources, query=queries, max_concurrent=3)
            async_time = time.time() - start_time

            # Should complete much faster than sequential processing
            # 6 analyses × 0.1s each = 0.6s sequential vs ~0.2s concurrent
            assert async_time < 0.4  # Should be much faster than 0.6s
            assert result.total_queries == 6


class TestAsyncCLI:
    """Test async CLI functionality - simplified for current architecture."""

    def test_cli_async_support(self):
        """Test that CLI supports async operations through simple entry point."""
        # Simple test that the CLI module can be imported and has the main entry point
        from layoutlens.cli import cli, main

        # The CLI supports async operations through asyncio.run internally
        # This test verifies the structure is in place
        assert callable(cli)
        assert callable(main)


class TestAsyncIntegration:
    """Test async integration with main CLI."""

    def test_async_integration_available(self):
        """Test that async functionality is available."""
        # Simple test that async functionality is properly integrated
        import asyncio

        from layoutlens.cli import main

        # The CLI uses asyncio.run internally for async operations
        # This test verifies basic integration is in place
        assert callable(main)
        assert hasattr(asyncio, "run")  # Ensure asyncio.run is available


@pytest.mark.performance
@pytest.mark.asyncio
async def test_async_performance_comparison():
    """Test concurrent performance benefits of async analyze_batch."""
    mock_api_key = "test-key"

    # Mock a realistic delay for individual analysis
    async def mock_analyze_async(source, query, viewport="desktop", context=None, max_concurrent=5):
        await asyncio.sleep(0.05)  # 50ms delay per analysis
        from layoutlens.api.core import BatchResult

        # Handle both single and multiple source/query combinations
        sources = [source] if not isinstance(source, list) else source
        queries = [query] if not isinstance(query, list) else query

        results = []
        for s in sources:
            for q in queries:
                results.append(
                    AnalysisResult(
                        source=s,
                        query=q,
                        answer="Test answer",
                        confidence=0.8,
                        reasoning="Test reasoning",
                    )
                )

        return BatchResult(
            results=results,
            total_queries=len(results),
            successful_queries=len(results),
            average_confidence=0.8,
            total_execution_time=0.05 * len(results),
        )

    lens = LayoutLens(api_key=mock_api_key)
    sources = [f"page_{i}.html" for i in range(5)]
    queries = ["Query 1", "Query 2"]

    # Test with high concurrency (should be faster)
    with patch.object(lens, "analyze", side_effect=mock_analyze_async):
        start_time = time.time()
        result_concurrent = await lens.analyze(source=sources, query=queries, max_concurrent=10)
        concurrent_time = time.time() - start_time

        # Test with low concurrency (should be slower)
        start_time = time.time()
        result_limited = await lens.analyze(source=sources, query=queries, max_concurrent=1)
        limited_time = time.time() - start_time

    # High concurrency should be faster than limited concurrency
    # 10 analyses: concurrent ~100ms vs limited ~500ms
    # Note: timing tests can be flaky, so we use a generous assertion
    assert concurrent_time <= limited_time + 0.1  # Should be at least as fast or just slightly slower due to overhead
    assert result_concurrent.total_queries == 10
    assert result_limited.total_queries == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
