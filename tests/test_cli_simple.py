"""Tests for the simplified LayoutLens CLI."""

import json
import sys
from dataclasses import asdict
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from layoutlens import DiffReport
from layoutlens.api.core import AnalysisResult, BatchResult
from layoutlens.cli import main
from layoutlens.exceptions import LayoutLensError
from layoutlens.layout.types import LayoutFinding, LayoutReport
from layoutlens.sarif import to_sarif


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

        mock_result = DiffReport(before="page1.html", after="page2.html")
        mock_lens.compare = AsyncMock(return_value=mock_result)

        # Test with args
        test_args = ["layoutlens", "page1.html", "page2.html", "--compare"]
        with (
            patch("sys.argv", test_args),
            patch("pathlib.Path.exists", return_value=True),
        ):
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
        with (
            patch("sys.argv", test_args),
            patch("pathlib.Path.exists", return_value=True),
        ):
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
            source="test.html",
            query="Is it good?",
            answer="Yes, it's good",
            confidence=0.8,
            reasoning="Clean design",
        )
        mock_lens.analyze = AsyncMock(return_value=mock_result)

        # Test with args
        test_args = ["layoutlens", "test.html", "Is it good?", "--output", "text"]
        with (
            patch("sys.argv", test_args),
            patch("pathlib.Path.exists", return_value=True),
        ):
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
                    source="page1.html",
                    query="Is it good?",
                    answer="Yes",
                    confidence=0.9,
                    reasoning="Good",
                ),
                AnalysisResult(
                    source="page2.html",
                    query="Is it good?",
                    answer="Yes",
                    confidence=0.8,
                    reasoning="Also good",
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
        with (
            patch("sys.argv", test_args),
            patch("pathlib.Path.exists", return_value=True),
        ):
            result = await main()

        assert result == 0
        mock_lens.analyze.assert_called_once_with(
            source=["page1.html", "page2.html"], query="Is it good?", viewport="desktop"
        )

    @patch("layoutlens.cli.LayoutLens")
    async def test_a11y_axe_mode(self, mock_lens_class):
        """--a11y axe runs check_accessibility with the axe mode."""
        mock_lens = Mock()
        mock_lens_class.return_value = mock_lens

        mock_result = AnalysisResult(
            source="test.html",
            query="",
            answer="No — axe-core found 2 WCAG A/AA violation(s): color-contrast, image-alt",
            confidence=1.0,
            reasoning="Accessibility report ...",
        )
        mock_lens.check_accessibility = AsyncMock(return_value=mock_result)

        test_args = ["layoutlens", "test.html", "--a11y", "axe"]
        with (
            patch("sys.argv", test_args),
            patch("pathlib.Path.exists", return_value=True),
        ):
            result = await main()

        assert result == 0
        mock_lens.check_accessibility.assert_called_once_with(
            "test.html", viewport="desktop", mode="axe"
        )

    @patch("layoutlens.cli.LayoutLens")
    async def test_a11y_query_conflict_errors(self, mock_lens_class, capsys):
        """Combining --a11y with a query is an error."""
        mock_lens = Mock()
        mock_lens_class.return_value = mock_lens
        mock_lens.check_accessibility = AsyncMock()

        test_args = [
            "layoutlens",
            "test.html",
            "--a11y",
            "axe",
            "--query",
            "Is it good?",
        ]
        with (
            patch("sys.argv", test_args),
            patch("pathlib.Path.exists", return_value=True),
        ):
            result = await main()

        assert result == 1
        captured = capsys.readouterr()
        assert "--query cannot be combined with --a11y" in captured.err
        mock_lens.check_accessibility.assert_not_called()

    @patch("layoutlens.cli.LayoutLens")
    async def test_a11y_compare_conflict_errors(self, mock_lens_class, capsys):
        """Combining --a11y with --compare is an error (accessibility runs per source)."""
        mock_lens = Mock()
        mock_lens_class.return_value = mock_lens
        mock_lens.check_accessibility = AsyncMock()
        mock_lens.compare = AsyncMock()

        test_args = ["layoutlens", "a.html", "b.html", "--a11y", "axe", "--compare"]
        with (
            patch("sys.argv", test_args),
            patch("pathlib.Path.exists", return_value=True),
        ):
            result = await main()

        assert result == 1
        captured = capsys.readouterr()
        assert "--compare cannot be combined with --a11y" in captured.err
        mock_lens.check_accessibility.assert_not_called()
        mock_lens.compare.assert_not_called()

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


@pytest.mark.asyncio
class TestSuiteModeGuards:
    """Suite-mode option conflicts and parse failures exit cleanly."""

    async def test_suite_rejects_sarif_output(self, capsys, tmp_path):
        suite = tmp_path / "suite.yaml"
        suite.write_text("name: s\ndescription: d\ntest_cases: []\n")
        with patch(
            "sys.argv",
            ["layoutlens", "--suite", str(suite), "--output", "sarif"],
        ):
            result = await main()
        assert result == 1
        assert "sarif" in capsys.readouterr().err

    async def test_suite_rejects_layout_flag(self, capsys, tmp_path):
        suite = tmp_path / "suite.yaml"
        suite.write_text("name: s\ndescription: d\ntest_cases: []\n")
        with patch(
            "sys.argv",
            ["layoutlens", "--suite", str(suite), "--layout", "deterministic"],
        ):
            result = await main()
        assert result == 1
        assert "--layout" in capsys.readouterr().err

    async def test_malformed_suite_yaml_errors_without_traceback(
        self, capsys, tmp_path
    ):
        suite = tmp_path / "bad.yaml"
        suite.write_text("name: [unclosed\n")
        with patch("sys.argv", ["layoutlens", "--suite", str(suite)]):
            result = await main()
        assert result == 1
        assert "Error loading suite" in capsys.readouterr().err

    async def test_malformed_suite_json_errors_without_traceback(
        self, capsys, tmp_path
    ):
        suite = tmp_path / "bad.json"
        suite.write_text("{not json")
        with patch("sys.argv", ["layoutlens", "--suite", str(suite)]):
            result = await main()
        assert result == 1
        assert "Error loading suite" in capsys.readouterr().err


def _check_results() -> list[AnalysisResult]:
    layout = LayoutReport(
        source="a.html",
        viewport="desktop",
        findings=[
            LayoutFinding(
                defect_class="page-overflow",
                selector="html",
                bbox=[0, 0, 3000, 0],
                measured={"overflow_px": 1080},
                threshold={"viewport_width_px": 1920},
                description="page scrolls horizontally",
            )
        ],
        timestamp="2026-01-01T00:00:00+00:00",
    )
    return [
        AnalysisResult(
            source="a.html",
            query="",
            answer="No",
            confidence=1.0,
            reasoning="one defect",
            timestamp="2026-01-01 00:00:00",
            metadata={
                "layout": asdict(layout),
                "confidence_kind": "not_estimated",
                "gate_status": "pass",
            },
        ),
        AnalysisResult(
            source="b.html",
            query="",
            answer="Yes",
            confidence=0.25,
            reasoning="",
            timestamp="2026-01-01 00:00:00",
        ),
    ]


async def _run_check(capsys, flag, mode, output, lens=None, lens_error=None):
    argv = ["layoutlens", "a.html", "b.html", flag, mode, "--output", output]
    with (
        patch("layoutlens.cli.LayoutLens") as lens_class,
        patch("sys.argv", argv),
        patch("pathlib.Path.exists", return_value=True),
    ):
        if lens_error is not None:
            lens_class.side_effect = lens_error
        else:
            lens_class.return_value = lens
        code = await main()
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _lens_returning(results):
    lens = Mock()
    lens.check_accessibility = AsyncMock(side_effect=results)
    lens.check_layout = AsyncMock(side_effect=results)
    return lens


CHECK_MODES = [("--a11y", "hybrid"), ("--layout", "hybrid")]


@pytest.mark.asyncio
@pytest.mark.parametrize(("flag", "mode"), CHECK_MODES)
async def test_check_json_and_sarif_output(capsys, flag, mode):
    for output, expected in (
        ("json", "".join(r.to_json() + "\n" for r in _check_results())),
        ("sarif", json.dumps(to_sarif(_check_results()), indent=2) + "\n"),
    ):
        lens = _lens_returning(_check_results())
        code, out, err = await _run_check(capsys, flag, mode, output, lens)
        assert (code, out, err) == (0, expected, "")


@pytest.mark.asyncio
async def test_a11y_text_output(capsys):
    lens = _lens_returning(_check_results())
    code, out, err = await _run_check(capsys, "--a11y", "axe", "text", lens)
    assert (code, err) == (0, "")
    assert out == (
        "\n"
        "📍 a.html\n"
        "♿ Accessibility (axe): No\n"
        "📊 Confidence: 100%\n"
        "💭 one defect\n"
        "\n"
        "📍 b.html\n"
        "♿ Accessibility (axe): Yes\n"
        "📊 Confidence: 25%\n"
        "\n"
    )


@pytest.mark.asyncio
async def test_layout_text_output(capsys):
    lens = _lens_returning(_check_results())
    code, out, err = await _run_check(capsys, "--layout", "deterministic", "text", lens)
    assert (code, err) == (0, "")
    assert out == (
        "\n"
        "📍 a.html\n"
        "📐 Layout (deterministic): No\n"
        "💭 one defect\n"
        "\n"
        "📍 b.html\n"
        "📐 Layout (deterministic): Yes\n"
        "📊 Model confidence: 25%\n"
        "\n"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(("flag", "mode"), CHECK_MODES)
@pytest.mark.parametrize(
    ("error", "message"),
    [
        (LayoutLensError("boom"), "Error: boom\n"),
        (RuntimeError("boom"), "Unexpected error: boom\n"),
    ],
)
async def test_check_errors_print_and_exit_1(capsys, flag, mode, error, message):
    lens = _lens_returning(error)
    assert await _run_check(capsys, flag, mode, "text", lens) == (1, "", message)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("flag", "message"),
    [
        ("--a11y", "Error initializing LayoutLens: boom\n"),
        ("--layout", "Unexpected error: boom\n"),
    ],
)
async def test_check_init_errors(capsys, flag, message):
    code = await _run_check(
        capsys, flag, "hybrid", "text", lens_error=ValueError("boom")
    )
    assert code == (1, "", message)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("statuses", "expected"),
    [(["pass", "pass"], 0), (["pass", "fail"], 1), (["fail", "incomplete"], 2)],
)
async def test_layout_exit_code_follows_gate_status(capsys, statuses, expected):
    results = _check_results()
    for result, status in zip(results, statuses, strict=True):
        result.metadata["gate_status"] = status
    lens = _lens_returning(results)
    code, _, _ = await _run_check(capsys, "--layout", "hybrid", "json", lens)
    assert code == expected
