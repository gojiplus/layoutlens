#!/usr/bin/env python3
"""LayoutLens Benchmark Evaluator

This script evaluates LayoutLens performance against ground truth answer keys
using semantic answer matching and comprehensive reporting.
"""

import argparse
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


@dataclass
class EvaluationResult:
    """Single test evaluation result."""

    html_file: str
    query: str
    expected: str
    ai_answer: str
    ai_confidence: float
    is_correct: bool
    confidence_threshold: float
    reasoning: str
    semantic_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkResults:
    """Complete benchmark evaluation results."""

    category: str
    total_tests: int
    correct_predictions: int
    accuracy: float
    high_confidence_correct: int
    medium_confidence_correct: int
    low_confidence_correct: int
    avg_ai_confidence: float
    results: list[EvaluationResult] = field(default_factory=list)
    execution_time: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class SemanticAnswerMatcher:
    """Matches AI answers to expected answers using semantic understanding."""

    def __init__(self):
        # Define semantic indicators for positive/negative responses
        self.positive_indicators = {
            "strong": [
                "yes",
                "correct",
                "proper",
                "good",
                "excellent",
                "appropriate",
                "well",
                "clearly",
                "properly",
                "effectively",
            ],
            "medium": ["mostly", "generally", "adequately", "reasonably", "fairly"],
            "weak": ["somewhat", "partially", "to some extent"],
        }

        self.negative_indicators = {
            "strong": [
                "no",
                "incorrect",
                "wrong",
                "poor",
                "bad",
                "inappropriate",
                "violates",
                "fails",
                "broken",
                "missing",
            ],
            "medium": [
                "not quite",
                "somewhat poor",
                "needs improvement",
                "could be better",
            ],
            "weak": ["not entirely", "not completely", "partially incorrect"],
        }

        # Common qualifications that modify meaning
        self.qualifiers = [
            "not",
            "very",
            "extremely",
            "quite",
            "rather",
            "somewhat",
            "partially",
        ]

    def extract_primary_sentiment(self, answer: str) -> tuple[str, float]:
        """Extract the primary positive/negative sentiment from an AI answer.

        Returns:
            Tuple of (sentiment, confidence) where sentiment is 'positive'/'negative'
            and confidence is 0.0-1.0
        """
        answer_lower = answer.lower().strip()

        # Handle direct yes/no responses first
        if answer_lower.startswith("yes"):
            return "positive", 0.9
        elif answer_lower.startswith("no"):
            return "negative", 0.9

        # Count positive and negative indicators with weights
        positive_score = 0
        negative_score = 0

        for strength, indicators in self.positive_indicators.items():
            weight = {"strong": 3, "medium": 2, "weak": 1}[strength]
            for indicator in indicators:
                if indicator in answer_lower:
                    positive_score += weight

        for strength, indicators in self.negative_indicators.items():
            weight = {"strong": 3, "medium": 2, "weak": 1}[strength]
            for indicator in indicators:
                if indicator in answer_lower:
                    negative_score += weight

        # Check for negation patterns that flip meaning
        negation_patterns = [
            r"not\s+(?:very\s+)?(?:" + "|".join(self.positive_indicators["strong"]) + ")",
            r"(?:isn\'t|doesn\'t|don\'t|won\'t)\s+" + "|".join(self.positive_indicators["strong"]),
        ]

        for pattern in negation_patterns:
            if re.search(pattern, answer_lower):
                positive_score -= 2  # Reduce positive score for negated positives
                negative_score += 1  # Add to negative score

        # Determine primary sentiment
        if positive_score > negative_score:
            confidence = min(0.9, 0.5 + (positive_score - negative_score) * 0.1)
            return "positive", confidence
        elif negative_score > positive_score:
            confidence = min(0.9, 0.5 + (negative_score - positive_score) * 0.1)
            return "negative", confidence
        else:
            # Unclear or neutral - look for specific patterns
            if any(phrase in answer_lower for phrase in ["unclear", "difficult to determine", "cannot tell"]):
                return "negative", 0.3  # Assume negative if AI is uncertain
            return "negative", 0.2  # Default to negative with low confidence

    def match_answer(self, ai_answer: str, expected: str) -> tuple[bool, float]:
        """Match AI answer to expected answer with confidence score.

        Returns:
            Tuple of (is_correct, semantic_confidence)
        """
        expected_lower = expected.lower().strip()

        # Extract sentiment from AI answer
        ai_sentiment, sentiment_confidence = self.extract_primary_sentiment(ai_answer)

        # Map expected answer to sentiment
        if expected_lower in ["yes", "correct", "good", "proper", "appropriate"]:
            expected_sentiment = "positive"
        elif expected_lower in ["no", "incorrect", "wrong", "poor", "inappropriate"]:
            expected_sentiment = "negative"
        else:
            # Try to infer from expected answer text
            expected_sentiment, _ = self.extract_primary_sentiment(expected)

        # Check if sentiments match
        is_correct = ai_sentiment == expected_sentiment

        # Calculate final confidence based on sentiment confidence and match
        final_confidence = sentiment_confidence if is_correct else 1.0 - sentiment_confidence

        return is_correct, final_confidence


class BenchmarkEvaluator:
    """Main benchmark evaluation engine."""

    def __init__(self, answer_keys_dir: str):
        self.answer_keys_dir = Path(answer_keys_dir)
        self.answer_keys = self.load_answer_keys()
        self.matcher = SemanticAnswerMatcher()

    def load_answer_keys(self) -> dict[str, dict]:
        """Load all answer key files."""
        answer_keys = {}

        for json_file in self.answer_keys_dir.glob("*.json"):
            category = json_file.stem
            with open(json_file) as f:
                answer_keys[category] = json.load(f)
            print(f"✓ Loaded answer key: {category}")

        return answer_keys

    def find_expected_answer(self, html_file: str, query: str) -> dict[str, Any] | None:
        """Find expected answer for a given HTML file and query."""
        filename = Path(html_file).name

        # Search through all categories
        for _category, key_data in self.answer_keys.items():
            test_cases = key_data.get("test_cases", {})

            if filename in test_cases:
                queries = test_cases[filename].get("queries", {})

                # Exact match first
                if query in queries:
                    return queries[query]

                # Fuzzy match on similar queries
                query_lower = query.lower()
                for key_query, answer_data in queries.items():
                    if self._queries_similar(query_lower, key_query.lower()):
                        return answer_data

        return None

    def _queries_similar(self, query1: str, query2: str) -> bool:
        """Check if two queries are semantically similar."""
        # Simple similarity check - can be improved with NLP
        query1_words = set(re.findall(r"\\b\\w+\\b", query1))
        query2_words = set(re.findall(r"\\b\\w+\\b", query2))

        # Remove common words
        common_words = {"is", "the", "a", "an", "are", "does", "do", "this", "that"}
        query1_words -= common_words
        query2_words -= common_words

        if not query1_words or not query2_words:
            return False

        # Calculate Jaccard similarity
        intersection = query1_words & query2_words
        union = query1_words | query2_words
        similarity = len(intersection) / len(union)

        return similarity > 0.5

    def evaluate_single_result(
        self, html_file: str, query: str, ai_answer: str, ai_confidence: float
    ) -> EvaluationResult | None:
        """Evaluate a single LayoutLens test result."""
        expected_data = self.find_expected_answer(html_file, query)

        if not expected_data:
            print(f"⚠️  No expected answer found for: {Path(html_file).name} - {query[:50]}...")
            return None

        expected = expected_data["expected"]
        confidence_threshold = expected_data.get("confidence_threshold", 0.7)
        reasoning = expected_data.get("reasoning", "")

        # Use semantic matching
        is_correct, semantic_score = self.matcher.match_answer(ai_answer, expected)

        return EvaluationResult(
            html_file=html_file,
            query=query,
            expected=expected,
            ai_answer=ai_answer,
            ai_confidence=ai_confidence,
            is_correct=is_correct,
            confidence_threshold=confidence_threshold,
            reasoning=reasoning,
            semantic_score=semantic_score,
            metadata=expected_data,
        )

    def evaluate_layoutlens_results(self, results_dir: str) -> dict[str, BenchmarkResults]:
        """Evaluate LayoutLens results from JSON output files."""
        results_path = Path(results_dir)
        category_results = {}

        # Find all LayoutLens result files
        for result_file in results_path.glob("*.json"):
            print(f"\\n📊 Evaluating: {result_file.name}")

            with open(result_file) as f:
                ll_data = json.load(f)

            # Handle new benchmark format (has benchmark_info and results array)
            if "benchmark_info" in ll_data and "results" in ll_data:
                print(f"📋 Found new benchmark format with {ll_data['benchmark_info']['total_tests']} tests")

                # Process each test result
                for test_result in ll_data["results"]:
                    html_file = test_result["html_file"]
                    category = self._determine_category(html_file)

                    if category not in category_results:
                        category_results[category] = BenchmarkResults(
                            category=category,
                            total_tests=0,
                            correct_predictions=0,
                            accuracy=0.0,
                            high_confidence_correct=0,
                            medium_confidence_correct=0,
                            low_confidence_correct=0,
                            avg_ai_confidence=0.0,
                        )

                    query = test_result["query"]
                    answer = test_result["answer"]
                    confidence = test_result.get("confidence", 1.0)

                    eval_result = self.evaluate_single_result(html_file, query, answer, confidence)
                    category_results[category].results.append(eval_result)
                    category_results[category].total_tests += 1

                    if eval_result.is_correct:
                        category_results[category].correct_predictions += 1

                        if confidence >= 0.8:
                            category_results[category].high_confidence_correct += 1
                        elif confidence >= 0.6:
                            category_results[category].medium_confidence_correct += 1
                        else:
                            category_results[category].low_confidence_correct += 1

                continue

            # Handle legacy format
            html_file = ll_data.get("html_path") or ll_data.get("html_file")
            if not html_file:
                print(f"⚠️  Skipping {result_file.name}: No html_file or html_path found")
                continue
            category = self._determine_category(html_file)

            if category not in category_results:
                category_results[category] = BenchmarkResults(
                    category=category,
                    total_tests=0,
                    correct_predictions=0,
                    accuracy=0.0,
                    high_confidence_correct=0,
                    medium_confidence_correct=0,
                    low_confidence_correct=0,
                    avg_ai_confidence=0.0,
                )

            # Evaluate each test result
            total_confidence = 0
            for test_result in ll_data.get("test_results", []):
                query = test_result["query"]
                answer = test_result["answer"]

                # LayoutLens doesn't always provide confidence, assume 1.0
                confidence = test_result.get("confidence", 1.0)
                total_confidence += confidence

                eval_result = self.evaluate_single_result(html_file, query, answer, confidence)

                if eval_result:
                    category_results[category].results.append(eval_result)
                    category_results[category].total_tests += 1

                    if eval_result.is_correct:
                        category_results[category].correct_predictions += 1

                        # Categorize by AI confidence level
                        if confidence >= 0.8:
                            category_results[category].high_confidence_correct += 1
                        elif confidence >= 0.6:
                            category_results[category].medium_confidence_correct += 1
                        else:
                            category_results[category].low_confidence_correct += 1

            # Calculate averages for this file
            if ll_data.get("test_results"):
                avg_conf = total_confidence / len(ll_data["test_results"])
                category_results[category].avg_ai_confidence = avg_conf

        # Calculate final accuracies
        for category, results in category_results.items():
            if results.total_tests > 0:
                results.accuracy = results.correct_predictions / results.total_tests
            print(
                f"✓ {category}: {results.accuracy:.1%} accuracy ({results.correct_predictions}/{results.total_tests})"
            )

        return category_results

    def _determine_category(self, html_file: str) -> str:
        """Determine benchmark category from HTML file path."""
        filename = Path(html_file).name.lower()

        if "nav" in filename or "logo" in filename or "align" in filename:
            return "layout_alignment"
        elif "wcag" in filename or "accessibility" in filename:
            return "accessibility"
        elif "mobile" in filename or "responsive" in filename:
            return "responsive_design"
        elif "form" in filename or "component" in filename:
            return "ui_components"
        else:
            return "general"

    def generate_report(self, category_results: dict[str, BenchmarkResults], output_file: str) -> None:
        """Generate comprehensive evaluation report."""

        # Calculate overall metrics
        total_tests = sum(r.total_tests for r in category_results.values())
        total_correct = sum(r.correct_predictions for r in category_results.values())
        overall_accuracy = total_correct / total_tests if total_tests > 0 else 0

        report = {
            "evaluation_summary": {
                "timestamp": datetime.now().isoformat(),
                "total_tests": total_tests,
                "total_correct": total_correct,
                "overall_accuracy": overall_accuracy,
                "categories_evaluated": len(category_results),
            },
            "category_results": {},
            "detailed_results": {},
        }

        # Add category summaries
        for category, results in category_results.items():
            report["category_results"][category] = {
                "total_tests": results.total_tests,
                "correct_predictions": results.correct_predictions,
                "accuracy": results.accuracy,
                "high_confidence_correct": results.high_confidence_correct,
                "medium_confidence_correct": results.medium_confidence_correct,
                "low_confidence_correct": results.low_confidence_correct,
                "avg_ai_confidence": results.avg_ai_confidence,
            }

            # Add detailed results
            detailed_results: list[dict[str, Any]] = []
            for result in results.results:
                detailed_results.append(
                    {
                        "html_file": result.html_file,
                        "query": result.query,
                        "expected": result.expected,
                        "ai_answer": (
                            result.ai_answer[:200] + "..." if len(result.ai_answer) > 200 else result.ai_answer
                        ),
                        "is_correct": result.is_correct,
                        "ai_confidence": result.ai_confidence,
                        "semantic_score": result.semantic_score,
                        "reasoning": result.reasoning,
                    }
                )
            report["detailed_results"][category] = detailed_results

        # Write report
        with open(output_file, "w") as f:
            json.dump(report, f, indent=2)

        # Print summary
        print(f"\\n{'=' * 60}")
        print("📊 BENCHMARK EVALUATION SUMMARY")
        print(f"{'=' * 60}")
        print(f"Overall Accuracy: {overall_accuracy:.1%} ({total_correct}/{total_tests})")
        print(f"Categories Evaluated: {len(category_results)}")

        for category, results in category_results.items():
            print(f"\\n📂 {category.replace('_', ' ').title()}:")
            print(f"  Accuracy: {results.accuracy:.1%} ({results.correct_predictions}/{results.total_tests})")
            print(f"  High Confidence Correct: {results.high_confidence_correct}")
            print(f"  Avg AI Confidence: {results.avg_ai_confidence:.2f}")

        print(f"\\n📄 Detailed report saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate LayoutLens benchmark performance")
    parser.add_argument(
        "--answer-keys",
        "-k",
        default="benchmarks_new/answer_keys",
        help="Directory containing answer key JSON files",
    )
    parser.add_argument(
        "--results",
        "-r",
        default="layoutlens_output/results",
        help="Directory containing LayoutLens result JSON files",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="benchmark_evaluation_report.json",
        help="Output file for evaluation report",
    )

    args = parser.parse_args()

    print("🔍 LayoutLens Benchmark Evaluator")
    print("=" * 50)

    # Initialize evaluator
    evaluator = BenchmarkEvaluator(args.answer_keys)

    # Evaluate results
    results = evaluator.evaluate_layoutlens_results(args.results)

    # Generate report
    evaluator.generate_report(results, args.output)


if __name__ == "__main__":
    main()
