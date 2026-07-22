"""Test suite functionality for LayoutLens."""

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ..api.core import AnalysisResult, BatchResult, LayoutLens
from ..exceptions import ValidationError


def _parse_yes_no(text: str) -> str | None:
    """Parse a leading yes/no token from an analysis answer.

    Structured analysis answers (see ``LayoutLens._parse_structured_response``)
    typically begin with "Yes" or "No" followed by an explanation, e.g.
    "Yes, the page has good contrast." or "No — there are violations...".

    Args:
        text: The answer text to parse.

    Returns:
        "yes" or "no" if the text starts with that token (case-insensitive),
        otherwise None if no yes/no answer can be recognized.
    """
    match = re.match(r"\s*(yes|no)\b", text or "", re.IGNORECASE)
    if match:
        return match.group(1).lower()
    return None


def _require_expected_results(name: str, expected_results: dict[str, Any] | None) -> dict[str, Any]:
    """Validate that a test case declares at least one assertion to grade against.

    This is the single source of truth for the "expected_results is required"
    rule — used at suite load time (``UITestSuite.from_dict``), at
    programmatic suite construction (``LayoutLens.create_test_suite``), and
    defensively at assertion-evaluation time (``_evaluate_case_assertions``)
    so no path can silently fall back to confidence-only grading.

    Args:
        name: The test case name, used in the error message.
        expected_results: The case's ``expected_results`` dict, if any.

    Returns:
        The validated ``expected_results`` dict, unchanged.

    Raises:
        ValidationError: If ``expected_results`` is missing, empty, or
            declares neither "answer" nor "contains".
    """
    if not expected_results or not ({"answer", "contains"} & expected_results.keys()):
        raise ValidationError(
            f"Test case '{name}' is missing 'expected_results'. Every test case must "
            "declare what to assert against — add at least one of 'answer' or "
            "'contains', e.g.:\n"
            "  expected_results:\n"
            '    answer: "yes"          # or "no"\n'
            '    contains: ["term1", "term2"]   # optional',
            field="expected_results",
            value=str(expected_results),
        )
    return expected_results


@dataclass
class UITestCase:
    """Represents a single test case for UI testing.

    ``expected_results`` declares what the analysis must assert against and is
    required (see ``UITestSuite.from_dict``). Schema::

        expected_results:
          answer: "yes"                    # or "no" — compared against the
                                            # parsed yes/no of the analysis answer
          contains: ["nav", "contrast"]    # optional; each term must appear
                                            # (case-insensitively) in answer + reasoning

    Both keys are individually optional, but at least one of them must be
    present — an empty or missing ``expected_results`` is a load-time error.
    ``expected_confidence`` sets the minimum ``result.confidence`` required in
    addition to any content assertions.
    """

    name: str
    html_path: str
    queries: list[str]
    viewports: list[str] = field(default_factory=lambda: ["desktop"])
    metadata: dict[str, Any] = field(default_factory=dict)
    expected_results: dict[str, Any] | None = None
    expected_confidence: float = 0.7

    def to_dict(self) -> dict[str, Any]:
        """Convert test case to dictionary."""
        return {
            "name": self.name,
            "html_path": str(self.html_path),
            "queries": self.queries,
            "viewports": self.viewports,
            "metadata": self.metadata,
            "expected_results": self.expected_results,
            "expected_confidence": self.expected_confidence,
        }


@dataclass
class UITestSuite:
    """Represents a collection of test cases."""

    name: str
    description: str
    test_cases: list[UITestCase]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert test suite to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "test_cases": [tc.to_dict() for tc in self.test_cases],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UITestSuite":
        """Create test suite from dictionary.

        Raises:
            ValidationError: If any test case is missing ``expected_results``
                (or declares neither "answer" nor "contains"). Assertions are
                required per case — there is no confidence-only fallback.
        """
        test_cases = []
        for tc in data["test_cases"]:
            name = tc.get("name", "<unnamed test case>")
            expected_results = _require_expected_results(name, tc.get("expected_results"))

            test_cases.append(
                UITestCase(
                    name=name,
                    html_path=tc["html_path"],
                    queries=tc["queries"],
                    viewports=tc.get("viewports", ["desktop"]),
                    metadata=tc.get("metadata", {}),
                    expected_results=expected_results,
                    expected_confidence=tc.get("expected_confidence", 0.7),
                )
            )

        return cls(
            name=data["name"],
            description=data["description"],
            test_cases=test_cases,
            metadata=data.get("metadata", {}),
        )

    def save(self, filepath: Path) -> None:
        """Save test suite to JSON file."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, filepath: Path) -> "UITestSuite":
        """Load test suite from JSON file."""
        with open(filepath) as f:
            data = json.load(f)
        return cls.from_dict(data)


@dataclass
class UITestResult:
    """Results from running a test suite."""

    suite_name: str
    test_case_name: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    results: list[AnalysisResult]
    duration_seconds: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_tests == 0:
            return 0.0
        return self.passed_tests / self.total_tests

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "suite_name": self.suite_name,
            "test_case_name": self.test_case_name,
            "total_tests": self.total_tests,
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
            "success_rate": self.success_rate,
            "duration_seconds": self.duration_seconds,
            "metadata": self.metadata,
            "results": [
                {
                    "query": r.metadata.get("query", ""),
                    "answer": r.answer,
                    "confidence": r.confidence,
                    "reasoning": r.reasoning,
                    "passed": (r.metadata.get("assertion_detail") or {}).get("passed"),
                    "assertion_detail": r.metadata.get("assertion_detail"),
                }
                for r in self.results
            ],
        }

    def to_json(self) -> str:
        """Export result to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)


def _evaluate_case_assertions(case: UITestCase, result: AnalysisResult) -> dict[str, Any]:
    """Evaluate a test case's expectations against an analysis result.

    Checks the case's ``expected_results`` ("answer" and/or "contains") plus
    its ``expected_confidence`` gate. A case passes iff every applicable
    assertion passes.

    Args:
        case: The test case declaring the expectations.
        result: The analysis result to check.

    Returns:
        A dict with "passed" (bool), "checks" (list of per-assertion detail
        dicts), and "failure_reasons" (list of human-readable strings for the
        failed checks) — enough to diagnose a failure without re-running.

    Raises:
        ValidationError: If ``case.expected_results`` is missing or empty.
            This should already be caught at suite load / construction time
            (``UITestSuite.from_dict``, ``LayoutLens.create_test_suite``);
            this is a defensive backstop so a case can never silently fall
            back to confidence-only grading.
    """
    expected = _require_expected_results(case.name, case.expected_results)
    checks: list[dict[str, Any]] = []

    expected_answer = expected.get("answer")
    if expected_answer is not None:
        expected_answer_norm = str(expected_answer).strip().lower()
        actual_answer = _parse_yes_no(result.answer)
        answer_passed = actual_answer is not None and actual_answer == expected_answer_norm
        if actual_answer is None:
            detail = f"expected answer '{expected_answer_norm}' but could not parse yes/no from: {result.answer!r}"
        else:
            detail = f"expected answer '{expected_answer_norm}', got '{actual_answer}'"
        checks.append(
            {
                "type": "answer",
                "expected": expected_answer_norm,
                "actual": actual_answer,
                "passed": answer_passed,
                "detail": detail,
            }
        )

    for term in expected.get("contains") or []:
        haystack = f"{result.answer} {result.reasoning}".lower()
        term_passed = term.lower() in haystack
        checks.append(
            {
                "type": "contains",
                "term": term,
                "passed": term_passed,
                "detail": (
                    f"term '{term}' found in answer/reasoning"
                    if term_passed
                    else f"term '{term}' not found in answer/reasoning"
                ),
            }
        )

    confidence_passed = result.confidence >= case.expected_confidence
    checks.append(
        {
            "type": "confidence",
            "expected_min": case.expected_confidence,
            "actual": result.confidence,
            "passed": confidence_passed,
            "detail": (
                f"confidence {result.confidence} >= required {case.expected_confidence}"
                if confidence_passed
                else f"confidence {result.confidence} below required {case.expected_confidence}"
            ),
        }
    )

    return {
        "passed": all(c["passed"] for c in checks),
        "checks": checks,
        "failure_reasons": [c["detail"] for c in checks if not c["passed"]],
    }


def extend_layoutlens_with_test_suite():
    """Extend LayoutLens class with test suite functionality."""

    async def run_test_suite(
        self, suite: UITestSuite, parallel: bool = False, max_workers: int = 4
    ) -> list[UITestResult]:
        """
        Run a test suite and return results.

        Args:
            suite: The test suite to run
            parallel: Whether to run tests in parallel
            max_workers: Maximum number of parallel workers

        Returns:
            List of UITestResult objects
        """
        results = []

        for test_case in suite.test_cases:
            start_time = time.time()
            test_results = []
            passed = 0
            failed = 0

            # Run analysis for each query and viewport combination
            for viewport in test_case.viewports:
                for query in test_case.queries:
                    try:
                        # Use the existing analyze method
                        result = await self.analyze(
                            source=test_case.html_path,
                            query=query,
                            viewport=viewport,
                            context=test_case.metadata,
                        )

                        # Assert against the case's expected_results / expected_confidence
                        # rather than trusting the model's self-reported confidence alone.
                        assertion_detail = _evaluate_case_assertions(test_case, result)
                        result.metadata["assertion_detail"] = assertion_detail

                        if assertion_detail["passed"]:
                            passed += 1
                        else:
                            failed += 1

                        test_results.append(result)

                    except Exception as e:
                        # Failed test
                        failed += 1
                        # Create a failed result
                        test_results.append(
                            AnalysisResult(
                                source=test_case.html_path,
                                query=query,
                                answer=f"Test failed: {str(e)}",
                                confidence=0.0,
                                reasoning="Test execution failed",
                                metadata={
                                    "error": str(e),
                                    "assertion_detail": {
                                        "passed": False,
                                        "checks": [],
                                        "failure_reasons": [f"Analysis raised an exception: {e}"],
                                    },
                                },
                            )
                        )

            duration = time.time() - start_time

            # Create test result
            test_result = UITestResult(
                suite_name=suite.name,
                test_case_name=test_case.name,
                total_tests=len(test_case.queries) * len(test_case.viewports),
                passed_tests=passed,
                failed_tests=failed,
                results=test_results,
                duration_seconds=duration,
                metadata=test_case.metadata,
            )

            results.append(test_result)

        return results

    def create_test_suite(self, name: str, description: str, test_cases: list[dict[str, Any]]) -> UITestSuite:
        """
        Create a test suite from specifications.

        Each spec in ``test_cases`` follows the same shape as a YAML test
        case, including a required ``expected_results`` (see the
        ``UITestCase`` docstring for schema) — validated identically to, and
        via the same helper as, ``UITestSuite.from_dict``.

        Args:
            name: Name of the test suite
            description: Description of the test suite
            test_cases: List of test case specifications, each requiring
                "name", "html_path", "queries", and "expected_results".

        Returns:
            UITestSuite object

        Raises:
            ValidationError: If any spec is missing ``expected_results``.
        """
        cases = []
        for tc_spec in test_cases:
            case_name = tc_spec.get("name", "<unnamed test case>")
            expected_results = _require_expected_results(case_name, tc_spec.get("expected_results"))
            test_case = UITestCase(
                name=case_name,
                html_path=tc_spec["html_path"],
                queries=tc_spec["queries"],
                viewports=tc_spec.get("viewports", ["desktop"]),
                metadata=tc_spec.get("metadata", {}),
                expected_results=expected_results,
                expected_confidence=tc_spec.get("expected_confidence", 0.7),
            )
            cases.append(test_case)

        return UITestSuite(name=name, description=description, test_cases=cases)

    # Add methods to LayoutLens class
    LayoutLens.run_test_suite = run_test_suite
    LayoutLens.create_test_suite = create_test_suite


# Auto-extend when module is imported
extend_layoutlens_with_test_suite()
