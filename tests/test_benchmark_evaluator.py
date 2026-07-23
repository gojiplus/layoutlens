"""Offline CI-guard tests for the deterministic benchmark evaluator.

These tests feed the evaluator canned answer keys + results (written to a
``tmp_path`` on disk, matching the CLI's directory-based interface) and assert
the scoring is deterministic yes/no with ambiguous answers counted as
incorrect. No network, no API key, no browser.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

# The evaluator lives under benchmarks/ (not an installed package), so load it
# by file path.
_EVALUATOR_PATH = Path(__file__).parent.parent / "benchmarks" / "evaluation" / "evaluator.py"
_spec = importlib.util.spec_from_file_location("benchmark_evaluator", _EVALUATOR_PATH)
assert _spec and _spec.loader
evaluator_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(evaluator_mod)

BenchmarkEvaluator = evaluator_mod.BenchmarkEvaluator


def _write_answer_keys(root: Path) -> Path:
    """Write two tiny per-category answer keys and return their directory."""
    keys_dir = root / "answer_keys"
    keys_dir.mkdir()

    accessibility = {
        "benchmark_info": {"category": "accessibility"},
        "test_cases": {
            "good.html": {
                "queries": {
                    "Is the contrast sufficient?": {"expected": "yes", "reasoning": "good contrast"},
                }
            },
            "bad.html": {
                "queries": {
                    "Does it meet WCAG?": {"expected": "no", "reasoning": "violations present"},
                    "Are images labeled?": {"expected": "no", "reasoning": "missing alt"},
                }
            },
        },
    }
    layout = {
        "benchmark_info": {"category": "layout_alignment"},
        "test_cases": {
            "nav.html": {
                "queries": {
                    "Is the nav centered?": {"expected": "yes", "reasoning": "centered"},
                }
            },
        },
    }
    (keys_dir / "accessibility.json").write_text(json.dumps(accessibility))
    (keys_dir / "layout_alignment.json").write_text(json.dumps(layout))
    return keys_dir


def _write_results(root: Path, results: list[dict]) -> Path:
    """Write a benchmark-results file in the runner's format; return its dir."""
    results_dir = root / "results"
    results_dir.mkdir()
    payload = {
        "benchmark_info": {"total_tests": len(results), "model_used": "gpt-4o-mini"},
        "results": results,
    }
    (results_dir / "benchmark_results.json").write_text(json.dumps(payload))
    return results_dir


@pytest.fixture
def evaluator(tmp_path: Path) -> BenchmarkEvaluator:
    keys_dir = _write_answer_keys(tmp_path)
    return BenchmarkEvaluator(str(keys_dir))


def test_correct_yes_scores_correct(evaluator):
    result = evaluator.evaluate_single_result("good.html", "Is the contrast sufficient?", "Yes, plenty.", 0.9)
    assert result is not None
    assert result.parsed_answer == "yes"
    assert result.is_correct is True


def test_correct_no_scores_correct(evaluator):
    result = evaluator.evaluate_single_result("bad.html", "Does it meet WCAG?", "No, it fails badly.", 0.9)
    assert result.parsed_answer == "no"
    assert result.is_correct is True


def test_wrong_answer_scores_incorrect(evaluator):
    # Expected "yes" but model says "no".
    result = evaluator.evaluate_single_result("good.html", "Is the contrast sufficient?", "No, too low.", 0.9)
    assert result.parsed_answer == "no"
    assert result.is_correct is False


def test_ambiguous_answer_scores_incorrect_not_no(evaluator):
    # Expected "no". An unparseable/hedged answer must NOT be treated as "no".
    result = evaluator.evaluate_single_result("bad.html", "Does it meet WCAG?", "It depends on interpretation.", 0.5)
    assert result.parsed_answer is None
    assert result.is_correct is False


def test_ambiguous_against_yes_also_incorrect(evaluator):
    result = evaluator.evaluate_single_result(
        "good.html", "Is the contrast sufficient?", "The page has some contrast.", 0.5
    )
    assert result.parsed_answer is None
    assert result.is_correct is False


def test_per_category_accuracy_math(tmp_path: Path):
    keys_dir = _write_answer_keys(tmp_path)
    results = [
        # accessibility: good.html yes/correct, bad.html one correct + one ambiguous(=incorrect)
        {"html_file": "good.html", "query": "Is the contrast sufficient?", "answer": "Yes.", "confidence": 0.9},
        {"html_file": "bad.html", "query": "Does it meet WCAG?", "answer": "No.", "confidence": 0.9},
        {"html_file": "bad.html", "query": "Are images labeled?", "answer": "Maybe?", "confidence": 0.4},
        # layout: nav.html wrong
        {"html_file": "nav.html", "query": "Is the nav centered?", "answer": "No.", "confidence": 0.9},
    ]
    results_dir = _write_results(tmp_path, results)

    ev = BenchmarkEvaluator(str(keys_dir))
    cat = ev.evaluate_layoutlens_results(str(results_dir))

    acc = cat["accessibility"]
    assert acc.total_tests == 3
    assert acc.correct_predictions == 2
    assert acc.ambiguous_answers == 1
    assert acc.accuracy == pytest.approx(2 / 3)

    layout = cat["layout_alignment"]
    assert layout.total_tests == 1
    assert layout.correct_predictions == 0
    assert layout.accuracy == 0.0


def test_report_overall_accuracy_and_metadata(tmp_path: Path):
    keys_dir = _write_answer_keys(tmp_path)
    results = [
        {"html_file": "good.html", "query": "Is the contrast sufficient?", "answer": "Yes.", "confidence": 0.9},
        {"html_file": "bad.html", "query": "Does it meet WCAG?", "answer": "No.", "confidence": 0.9},
        {"html_file": "nav.html", "query": "Is the nav centered?", "answer": "Yes.", "confidence": 0.9},
    ]
    results_dir = _write_results(tmp_path, results)
    ev = BenchmarkEvaluator(str(keys_dir))
    cat = ev.evaluate_layoutlens_results(str(results_dir))
    report = ev.generate_report(cat, str(tmp_path / "report.json"))

    summary = report["evaluation_summary"]
    assert summary["total_queries"] == 3
    assert summary["total_correct"] == 3
    assert summary["overall_accuracy"] == pytest.approx(1.0)
    assert summary["model"] == "gpt-4o-mini"
    assert summary["evaluator_version"] == evaluator_mod.EVALUATOR_VERSION
    assert "date" in summary
