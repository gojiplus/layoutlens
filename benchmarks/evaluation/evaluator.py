#!/usr/bin/env python3
"""LayoutLens Benchmark Evaluator.

Scores LayoutLens answers against ground-truth answer keys using a
**deterministic** structured yes/no comparison:

- The answer key's ``expected`` is always ``"yes"`` or ``"no"``.
- The model answer's leading yes/no token is parsed with the same
  word-boundary parser used by the runtime test suite
  (:func:`layoutlens.api.test_suite._parse_yes_no`).
- An answer whose yes/no cannot be parsed (ambiguous / hedged) counts as
  **incorrect** — it is never silently mapped to "no".

This replaces the previous keyword-sentiment matcher, which defaulted
ambiguous answers to "negative" (a free "no") and produced accuracy numbers
that traced to nothing.
"""

import argparse
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from layoutlens.api.test_suite import _parse_yes_no

# Bump when the scoring semantics change so committed artifacts are traceable.
EVALUATOR_VERSION = "2.0"
EVALUATOR_METHOD = (
    "Deterministic structured yes/no: the model answer's leading yes/no token "
    "(word-boundary parse) is compared to the answer key's expected value. "
    "Ambiguous/unparseable answers count as incorrect (never defaulted to 'no')."
)


@dataclass
class EvaluationResult:
    """Single query evaluation result."""

    html_file: str
    query: str
    expected: str
    ai_answer: str
    ai_confidence: float
    parsed_answer: str | None
    is_correct: bool
    reasoning: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkResults:
    """Aggregated evaluation results for a single category."""

    category: str
    total_tests: int = 0
    correct_predictions: int = 0
    accuracy: float = 0.0
    ambiguous_answers: int = 0
    high_confidence_correct: int = 0
    medium_confidence_correct: int = 0
    low_confidence_correct: int = 0
    avg_ai_confidence: float = 0.0
    results: list[EvaluationResult] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class BenchmarkEvaluator:
    """Deterministic benchmark evaluation engine."""

    def __init__(self, answer_keys_dir: str):
        self.answer_keys_dir = Path(answer_keys_dir)
        self.answer_keys = self.load_answer_keys()
        # Map each fixture filename to the category (answer-key stem) that owns it.
        self.file_to_category = self._build_file_category_map()
        # Model recorded in the results file(s); filled during evaluation.
        self.model_used: str | None = None

    def load_answer_keys(self) -> dict[str, dict]:
        """Load all answer key files, keyed by category (file stem)."""
        answer_keys = {}
        for json_file in sorted(self.answer_keys_dir.glob("*.json")):
            category = json_file.stem
            with open(json_file) as f:
                answer_keys[category] = json.load(f)
            print(f"[loaded] answer key: {category}")
        return answer_keys

    def _build_file_category_map(self) -> dict[str, str]:
        """Build a fixture-filename -> category map from the answer keys."""
        mapping: dict[str, str] = {}
        for category, key_data in self.answer_keys.items():
            for filename in key_data.get("test_cases", {}):
                mapping[filename] = category
        return mapping

    def find_expected_answer(self, html_file: str, query: str) -> dict[str, Any] | None:
        """Find the expected-answer record for an (HTML file, query) pair."""
        filename = Path(html_file).name
        for key_data in self.answer_keys.values():
            test_cases = key_data.get("test_cases", {})
            if filename in test_cases:
                queries = test_cases[filename].get("queries", {})
                if query in queries:
                    return queries[query]
        return None

    def _category_for(self, html_file: str) -> str:
        """Return the category owning a fixture, or 'unknown' if unmapped."""
        return self.file_to_category.get(Path(html_file).name, "unknown")

    def evaluate_single_result(
        self, html_file: str, query: str, ai_answer: str, ai_confidence: float
    ) -> EvaluationResult | None:
        """Evaluate a single LayoutLens answer against the ground truth."""
        expected_data = self.find_expected_answer(html_file, query)
        if not expected_data:
            print(f"[warn] no expected answer for: {Path(html_file).name} - {query[:60]}...")
            return None

        expected = str(expected_data["expected"]).strip().lower()
        parsed = _parse_yes_no(ai_answer)
        # Ambiguous/unparseable answers are incorrect — never defaulted to "no".
        is_correct = parsed is not None and parsed == expected

        return EvaluationResult(
            html_file=html_file,
            query=query,
            expected=expected,
            ai_answer=ai_answer,
            ai_confidence=ai_confidence,
            parsed_answer=parsed,
            is_correct=is_correct,
            reasoning=expected_data.get("reasoning", ""),
            metadata=expected_data,
        )

    def evaluate_layoutlens_results(self, results_dir: str) -> dict[str, BenchmarkResults]:
        """Evaluate LayoutLens benchmark result JSON files in a directory."""
        results_path = Path(results_dir)
        category_results: dict[str, BenchmarkResults] = {}
        conf_totals: dict[str, float] = {}

        for result_file in sorted(results_path.glob("*.json")):
            print(f"\n[evaluating] {result_file.name}")
            with open(result_file) as f:
                ll_data = json.load(f)

            if not ("benchmark_info" in ll_data and "results" in ll_data):
                print(f"[skip] {result_file.name}: not a benchmark results file")
                continue

            self.model_used = ll_data["benchmark_info"].get("model_used") or self.model_used

            for test_result in ll_data["results"]:
                html_file = test_result["html_file"]
                query = test_result["query"]
                answer = test_result["answer"]
                confidence = test_result.get("confidence", 1.0)

                eval_result = self.evaluate_single_result(html_file, query, answer, confidence)
                if eval_result is None:
                    continue

                category = self._category_for(html_file)
                if category not in category_results:
                    category_results[category] = BenchmarkResults(category=category)
                    conf_totals[category] = 0.0

                cat = category_results[category]
                cat.results.append(eval_result)
                cat.total_tests += 1
                conf_totals[category] += confidence

                if eval_result.parsed_answer is None:
                    cat.ambiguous_answers += 1

                if eval_result.is_correct:
                    cat.correct_predictions += 1
                    if confidence >= 0.8:
                        cat.high_confidence_correct += 1
                    elif confidence >= 0.6:
                        cat.medium_confidence_correct += 1
                    else:
                        cat.low_confidence_correct += 1

        # Finalize per-category accuracy and average confidence.
        for category, cat in category_results.items():
            if cat.total_tests > 0:
                cat.accuracy = cat.correct_predictions / cat.total_tests
                cat.avg_ai_confidence = conf_totals[category] / cat.total_tests
            print(f"[category] {category}: {cat.accuracy:.1%} ({cat.correct_predictions}/{cat.total_tests})")

        return category_results

    def generate_report(self, category_results: dict[str, BenchmarkResults], output_file: str) -> dict[str, Any]:
        """Generate and write a JSON evaluation report; return the report dict."""
        total_tests = sum(r.total_tests for r in category_results.values())
        total_correct = sum(r.correct_predictions for r in category_results.values())
        total_ambiguous = sum(r.ambiguous_answers for r in category_results.values())
        overall_accuracy = total_correct / total_tests if total_tests > 0 else 0.0

        report: dict[str, Any] = {
            "evaluation_summary": {
                "timestamp": datetime.now().isoformat(),
                "date": date.today().isoformat(),
                "model": self.model_used or "unknown",
                "total_queries": total_tests,
                "total_correct": total_correct,
                "ambiguous_answers": total_ambiguous,
                "overall_accuracy": overall_accuracy,
                "categories_evaluated": len(category_results),
                "evaluator_version": EVALUATOR_VERSION,
                "evaluator_method": EVALUATOR_METHOD,
            },
            "category_results": {},
            "detailed_results": {},
        }

        for category, results in category_results.items():
            report["category_results"][category] = {
                "total_queries": results.total_tests,
                "correct_predictions": results.correct_predictions,
                "accuracy": results.accuracy,
                "ambiguous_answers": results.ambiguous_answers,
                "high_confidence_correct": results.high_confidence_correct,
                "medium_confidence_correct": results.medium_confidence_correct,
                "low_confidence_correct": results.low_confidence_correct,
                "avg_ai_confidence": results.avg_ai_confidence,
            }

            detailed: list[dict[str, Any]] = []
            for result in results.results:
                detailed.append(
                    {
                        "html_file": result.html_file,
                        "query": result.query,
                        "expected": result.expected,
                        "parsed_answer": result.parsed_answer,
                        "ai_answer": (
                            result.ai_answer[:200] + "..." if len(result.ai_answer) > 200 else result.ai_answer
                        ),
                        "is_correct": result.is_correct,
                        "ai_confidence": result.ai_confidence,
                        "reasoning": result.reasoning,
                    }
                )
            report["detailed_results"][category] = detailed

        with open(output_file, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\n{'=' * 60}")
        print("BENCHMARK EVALUATION SUMMARY")
        print(f"{'=' * 60}")
        print(f"Model: {self.model_used or 'unknown'}")
        print(f"Overall Accuracy: {overall_accuracy:.1%} ({total_correct}/{total_tests})")
        print(f"Ambiguous (unparseable) answers: {total_ambiguous}")
        print(f"Categories Evaluated: {len(category_results)}")
        for category, results in category_results.items():
            print(f"\n{category.replace('_', ' ').title()}:")
            print(f"  Accuracy: {results.accuracy:.1%} ({results.correct_predictions}/{results.total_tests})")
            print(f"  Ambiguous: {results.ambiguous_answers}")
            print(f"  Avg AI Confidence: {results.avg_ai_confidence:.2f}")
        print(f"\nReport saved to: {output_file}")

        return report


def main():
    parser = argparse.ArgumentParser(description="Evaluate LayoutLens benchmark performance")
    parser.add_argument(
        "--answer-keys",
        "-k",
        default="benchmarks/answer_keys",
        help="Directory containing answer key JSON files",
    )
    parser.add_argument(
        "--results",
        "-r",
        default="benchmarks/layoutlens_output",
        help="Directory containing LayoutLens result JSON files",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="benchmark_evaluation_report.json",
        help="Output file for evaluation report",
    )
    args = parser.parse_args()

    print("LayoutLens Benchmark Evaluator")
    print("=" * 50)

    evaluator = BenchmarkEvaluator(args.answer_keys)
    results = evaluator.evaluate_layoutlens_results(args.results)
    evaluator.generate_report(results, args.output)


if __name__ == "__main__":
    main()
