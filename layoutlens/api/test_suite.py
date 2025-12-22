"""Test suite functionality for LayoutLens."""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ..api.core import AnalysisResult, BatchResult, LayoutLens


@dataclass
class UITestCase:
    """Represents a single test case for UI testing."""

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
        """Create test suite from dictionary."""
        test_cases = [
            UITestCase(
                name=tc["name"],
                html_path=tc["html_path"],
                queries=tc["queries"],
                viewports=tc.get("viewports", ["desktop"]),
                metadata=tc.get("metadata", {}),
                expected_results=tc.get("expected_results"),
            )
            for tc in data["test_cases"]
        ]

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
                }
                for r in self.results
            ],
        }

    def to_json(self) -> str:
        """Export result to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)


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

                        # Determine pass/fail based on confidence threshold
                        if result.confidence >= 0.7:  # Default threshold
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
                                metadata={"error": str(e)},
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

        Args:
            name: Name of the test suite
            description: Description of the test suite
            test_cases: List of test case specifications

        Returns:
            UITestSuite object
        """
        cases = []
        for tc_spec in test_cases:
            test_case = UITestCase(
                name=tc_spec["name"],
                html_path=tc_spec["html_path"],
                queries=tc_spec["queries"],
                viewports=tc_spec.get("viewports", ["desktop"]),
                metadata=tc_spec.get("metadata", {}),
            )
            cases.append(test_case)

        return UITestSuite(name=name, description=description, test_cases=cases)

    # Add methods to LayoutLens class
    LayoutLens.run_test_suite = run_test_suite
    LayoutLens.create_test_suite = create_test_suite


# Auto-extend when module is imported
extend_layoutlens_with_test_suite()
