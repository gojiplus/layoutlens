"""Test the new test suite functionality."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from layoutlens import AnalysisResult, LayoutLens, UITestCase, UITestResult, UITestSuite, ValidationError


def test_test_case_creation():
    """Test creating a UITestCase object."""
    test_case = UITestCase(
        name="Homepage Test",
        html_path="test.html",
        queries=["Is it accessible?", "Is it mobile-friendly?"],
        viewports=["desktop", "mobile_portrait"],
        metadata={"priority": "high"},
    )

    assert test_case.name == "Homepage Test"
    assert test_case.html_path == "test.html"
    assert len(test_case.queries) == 2
    assert len(test_case.viewports) == 2
    assert test_case.metadata["priority"] == "high"

    # Test to_dict
    data = test_case.to_dict()
    assert data["name"] == "Homepage Test"
    assert data["html_path"] == "test.html"


def test_test_suite_creation():
    """Test creating a UITestSuite object."""
    test_case1 = UITestCase(name="Test 1", html_path="page1.html", queries=["Query 1"])

    test_case2 = UITestCase(name="Test 2", html_path="page2.html", queries=["Query 2"])

    suite = UITestSuite(
        name="UI Test Suite",
        description="Testing UI components",
        test_cases=[test_case1, test_case2],
        metadata={"version": "1.0"},
    )

    assert suite.name == "UI Test Suite"
    assert len(suite.test_cases) == 2
    assert suite.test_cases[0].name == "Test 1"

    # Test to_dict
    data = suite.to_dict()
    assert data["name"] == "UI Test Suite"
    assert len(data["test_cases"]) == 2


def test_test_suite_save_and_load():
    """Test saving and loading a test suite."""
    test_case = UITestCase(
        name="Save Test",
        html_path="save_test.html",
        queries=["Is it working?"],
        expected_results={"answer": "yes"},
    )

    suite = UITestSuite(name="Save Suite", description="Test saving and loading", test_cases=[test_case])

    # Save to temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_path = Path(f.name)

    try:
        suite.save(temp_path)

        # Load the suite
        loaded_suite = UITestSuite.load(temp_path)

        assert loaded_suite.name == suite.name
        assert loaded_suite.description == suite.description
        assert len(loaded_suite.test_cases) == 1
        assert loaded_suite.test_cases[0].name == "Save Test"

    finally:
        # Clean up
        if temp_path.exists():
            temp_path.unlink()


def test_test_result():
    """Test UITestResult functionality."""
    mock_results = [
        AnalysisResult(
            source="test.html",
            query="Is it accessible?",
            answer="Yes, it's accessible",
            confidence=0.9,
            reasoning="Good contrast",
            metadata={},
        ),
        AnalysisResult(
            source="test.html",
            query="Is it mobile-friendly?",
            answer="No issues found",
            confidence=0.8,
            reasoning="Mobile optimized",
            metadata={},
        ),
    ]

    result = UITestResult(
        suite_name="Test Suite",
        test_case_name="Test Case",
        total_tests=2,
        passed_tests=2,
        failed_tests=0,
        results=mock_results,
        duration_seconds=5.5,
    )

    assert result.success_rate == 1.0
    assert result.total_tests == 2
    assert result.passed_tests == 2

    # Test to_dict
    data = result.to_dict()
    assert data["suite_name"] == "Test Suite"
    assert data["success_rate"] == 1.0
    assert len(data["results"]) == 2


@patch("layoutlens.api.core.LayoutLens.analyze")
@pytest.mark.asyncio
async def test_run_test_suite(mock_analyze):
    """Test running a test suite with LayoutLens."""
    # Setup async mock for analyze method
    mock_result = AnalysisResult(
        source="test.html",
        query="Is it good?",
        answer="Test passed",
        confidence=0.85,
        reasoning="Good layout",
        metadata={},
    )

    # Mock analyze as async method
    mock_analyze.return_value = mock_result

    # Create test suite
    test_case = UITestCase(
        name="Test Case",
        html_path="test.html",
        queries=["Is it good?"],
        viewports=["desktop"],
        expected_results={"contains": ["passed"]},
    )

    suite = UITestSuite(name="Test Suite", description="Test description", test_cases=[test_case])

    # Run the suite - now async
    lens = LayoutLens(api_key="test_key")
    results = await lens.run_test_suite(suite)

    assert len(results) == 1
    result = results[0]
    assert result.suite_name == "Test Suite"
    assert result.test_case_name == "Test Case"
    assert result.total_tests == 1
    assert result.passed_tests == 1  # Confidence > 0.7
    assert result.failed_tests == 0

    # Verify analyze was called
    mock_analyze.assert_called_once()


@patch("layoutlens.api.core.LayoutLens.analyze")
@pytest.mark.asyncio
async def test_run_test_suite_with_failure(mock_analyze):
    """Test running a test suite with failures."""
    # Setup mock to fail
    mock_analyze.side_effect = Exception("API error")

    # Create test suite
    test_case = UITestCase(
        name="Failing Test",
        html_path="fail.html",
        queries=["Will this fail?"],
        viewports=["desktop"],
        expected_results={"answer": "yes"},
    )

    suite = UITestSuite(name="Failing Suite", description="Test with failures", test_cases=[test_case])

    # Run the suite - now async
    lens = LayoutLens(api_key="test_key")
    results = await lens.run_test_suite(suite)

    assert len(results) == 1
    result = results[0]
    assert result.total_tests == 1
    assert result.passed_tests == 0
    assert result.failed_tests == 1
    assert result.success_rate == 0.0


@patch("layoutlens.api.core.LayoutLens.analyze")
@pytest.mark.asyncio
async def test_run_test_suite_case_with_no_expected_results_never_passes(mock_analyze):
    """A hand-built case with no expected_results must never pass on confidence alone.

    This simulates a case bypassing from_dict/create_test_suite validation
    (e.g. constructed directly). The defensive check in
    _evaluate_case_assertions must turn it into a failure, not a silent pass.
    """
    mock_analyze.return_value = AnalysisResult(
        source="test.html",
        query="Is it good?",
        answer="Yes, it is good.",
        confidence=0.99,
        reasoning="Looks great.",
        metadata={},
    )

    test_case = UITestCase(
        name="No Expectations At All",
        html_path="test.html",
        queries=["Is it good?"],
        viewports=["desktop"],
        # expected_results intentionally left at its default (None) to
        # simulate a case slipping past construction-time validation.
    )
    suite = UITestSuite(name="Suite", description="d", test_cases=[test_case])

    lens = LayoutLens(api_key="test_key")
    results = await lens.run_test_suite(suite)

    result = results[0]
    assert result.passed_tests == 0
    assert result.failed_tests == 1
    assert "expected_results" in result.results[0].metadata["error"]


def test_create_test_suite():
    """Test creating a test suite using LayoutLens."""
    lens = LayoutLens(api_key="test_key")

    test_cases = [
        {
            "name": "Homepage",
            "html_path": "homepage.html",
            "queries": ["Is the navigation visible?"],
            "viewports": ["desktop"],
            "metadata": {"page": "home"},
            "expected_results": {"answer": "yes"},
        },
        {
            "name": "About",
            "html_path": "about.html",
            "queries": ["Is the content readable?"],
            "viewports": ["mobile_portrait"],
            "expected_results": {"contains": ["readable"]},
            "expected_confidence": 0.8,
        },
    ]

    suite = lens.create_test_suite(name="Website Tests", description="Test all pages", test_cases=test_cases)

    assert suite.name == "Website Tests"
    assert len(suite.test_cases) == 2
    assert suite.test_cases[0].name == "Homepage"
    assert suite.test_cases[0].expected_results == {"answer": "yes"}
    assert suite.test_cases[1].viewports == ["mobile_portrait"]
    assert suite.test_cases[1].expected_confidence == 0.8


def test_create_test_suite_requires_expected_results():
    """A spec missing 'expected_results' raises the same ValidationError as from_dict.

    create_test_suite must not offer a silent confidence-only path.
    """
    lens = LayoutLens(api_key="test_key")

    test_cases = [
        {
            "name": "No Expectations",
            "html_path": "homepage.html",
            "queries": ["Is the navigation visible?"],
        }
    ]

    with pytest.raises(ValidationError) as exc_info:
        lens.create_test_suite(name="Website Tests", description="Test all pages", test_cases=test_cases)

    message = str(exc_info.value)
    assert "No Expectations" in message
    assert "expected_results" in message


@patch("layoutlens.api.core.LayoutLens.analyze")
@pytest.mark.asyncio
async def test_run_test_suite_answer_mismatch_fails(mock_analyze):
    """A case expecting answer 'no' fails when the model answers 'yes', with diagnosable detail."""
    mock_analyze.return_value = AnalysisResult(
        source="test.html",
        query="Are there accessibility violations?",
        answer="Yes, the page has several contrast issues.",
        confidence=0.9,
        reasoning="Contrast ratio is below WCAG AA.",
        metadata={},
    )

    test_case = UITestCase(
        name="No Violations Expected",
        html_path="test.html",
        queries=["Are there accessibility violations?"],
        viewports=["desktop"],
        expected_results={"answer": "no"},
    )
    suite = UITestSuite(name="Suite", description="d", test_cases=[test_case])

    lens = LayoutLens(api_key="test_key")
    results = await lens.run_test_suite(suite)

    result = results[0]
    assert result.passed_tests == 0
    assert result.failed_tests == 1

    detail = result.results[0].metadata["assertion_detail"]
    assert detail["passed"] is False
    answer_check = next(c for c in detail["checks"] if c["type"] == "answer")
    assert answer_check["expected"] == "no"
    assert answer_check["actual"] == "yes"
    assert answer_check["passed"] is False


@patch("layoutlens.api.core.LayoutLens.analyze")
@pytest.mark.asyncio
async def test_run_test_suite_to_json_includes_assertion_detail(mock_analyze):
    """to_json() must carry each result's assertion_detail so failures are diagnosable from output alone."""
    mock_analyze.return_value = AnalysisResult(
        source="test.html",
        query="Are there accessibility violations?",
        answer="Yes, the page has several contrast issues.",
        confidence=0.9,
        reasoning="Contrast ratio is below WCAG AA.",
        metadata={},
    )

    test_case = UITestCase(
        name="No Violations Expected",
        html_path="test.html",
        queries=["Are there accessibility violations?"],
        viewports=["desktop"],
        expected_results={"answer": "no"},
    )
    suite = UITestSuite(name="Suite", description="d", test_cases=[test_case])

    lens = LayoutLens(api_key="test_key")
    results = await lens.run_test_suite(suite)
    result = results[0]
    assert result.failed_tests == 1

    serialized = json.loads(result.to_json())
    assert len(serialized["results"]) == 1
    entry = serialized["results"][0]
    assert entry["passed"] is False
    assert entry["assertion_detail"]["passed"] is False
    failure_reasons = entry["assertion_detail"]["failure_reasons"]
    assert any("expected answer 'no', got 'yes'" in reason for reason in failure_reasons)


@patch("layoutlens.api.core.LayoutLens.analyze")
@pytest.mark.asyncio
async def test_run_test_suite_answer_match_passes(mock_analyze):
    """A case expecting answer 'no' passes when the model answers 'no' with sufficient confidence."""
    mock_analyze.return_value = AnalysisResult(
        source="test.html",
        query="Are there accessibility violations?",
        answer="No — there are violations found on this page.",
        confidence=0.9,
        reasoning="All contrast and focus checks passed.",
        metadata={},
    )

    test_case = UITestCase(
        name="No Violations Expected",
        html_path="test.html",
        queries=["Are there accessibility violations?"],
        viewports=["desktop"],
        expected_results={"answer": "no"},
    )
    suite = UITestSuite(name="Suite", description="d", test_cases=[test_case])

    lens = LayoutLens(api_key="test_key")
    results = await lens.run_test_suite(suite)

    result = results[0]
    assert result.passed_tests == 1
    assert result.failed_tests == 0
    assert result.results[0].metadata["assertion_detail"]["passed"] is True


@patch("layoutlens.api.core.LayoutLens.analyze")
@pytest.mark.asyncio
async def test_run_test_suite_contains_missing_term_fails(mock_analyze):
    """A missing 'contains' term fails the case and names the missing term in the detail."""
    mock_analyze.return_value = AnalysisResult(
        source="test.html",
        query="Describe any accessibility issues.",
        answer="Yes, there are issues.",
        confidence=0.9,
        reasoning="The layout has spacing problems near the footer.",
        metadata={},
    )

    test_case = UITestCase(
        name="Contains Check",
        html_path="test.html",
        queries=["Describe any accessibility issues."],
        viewports=["desktop"],
        expected_results={"contains": ["contrast"]},
    )
    suite = UITestSuite(name="Suite", description="d", test_cases=[test_case])

    lens = LayoutLens(api_key="test_key")
    results = await lens.run_test_suite(suite)

    result = results[0]
    assert result.passed_tests == 0
    assert result.failed_tests == 1

    detail = result.results[0].metadata["assertion_detail"]
    contains_check = next(c for c in detail["checks"] if c["type"] == "contains")
    assert contains_check["term"] == "contrast"
    assert contains_check["passed"] is False


@patch("layoutlens.api.core.LayoutLens.analyze")
@pytest.mark.asyncio
async def test_run_test_suite_unparseable_answer_fails(mock_analyze):
    """An answer expectation against an unparseable (neither yes nor no) answer always fails."""
    mock_analyze.return_value = AnalysisResult(
        source="test.html",
        query="Is this good?",
        answer="The layout is somewhat acceptable overall.",
        confidence=0.9,
        reasoning="Mixed signals.",
        metadata={},
    )

    test_case = UITestCase(
        name="Unparseable Answer",
        html_path="test.html",
        queries=["Is this good?"],
        viewports=["desktop"],
        expected_results={"answer": "yes"},
    )
    suite = UITestSuite(name="Suite", description="d", test_cases=[test_case])

    lens = LayoutLens(api_key="test_key")
    results = await lens.run_test_suite(suite)

    result = results[0]
    assert result.passed_tests == 0
    assert result.failed_tests == 1

    detail = result.results[0].metadata["assertion_detail"]
    answer_check = next(c for c in detail["checks"] if c["type"] == "answer")
    assert answer_check["actual"] is None
    assert answer_check["passed"] is False


@patch("layoutlens.api.core.LayoutLens.analyze")
@pytest.mark.asyncio
async def test_run_test_suite_confidence_below_expected_fails(mock_analyze):
    """Content assertions passing is not enough; confidence below the per-case threshold still fails."""
    mock_analyze.return_value = AnalysisResult(
        source="test.html",
        query="Is this accessible?",
        answer="Yes, it is accessible.",
        confidence=0.5,
        reasoning="Looks fine overall.",
        metadata={},
    )

    test_case = UITestCase(
        name="High Confidence Required",
        html_path="test.html",
        queries=["Is this accessible?"],
        viewports=["desktop"],
        expected_results={"answer": "yes"},
        expected_confidence=0.9,
    )
    suite = UITestSuite(name="Suite", description="d", test_cases=[test_case])

    lens = LayoutLens(api_key="test_key")
    results = await lens.run_test_suite(suite)

    result = results[0]
    assert result.passed_tests == 0
    assert result.failed_tests == 1

    detail = result.results[0].metadata["assertion_detail"]
    confidence_check = next(c for c in detail["checks"] if c["type"] == "confidence")
    assert confidence_check["passed"] is False
    # Content assertion itself passed; only the confidence gate should have failed it.
    answer_check = next(c for c in detail["checks"] if c["type"] == "answer")
    assert answer_check["passed"] is True


def test_from_dict_requires_expected_results():
    """UITestSuite.from_dict raises a helpful ValidationError naming a case that lacks expected_results."""
    data = {
        "name": "Suite",
        "description": "d",
        "test_cases": [
            {
                "name": "Missing Expectations",
                "html_path": "test.html",
                "queries": ["Is this good?"],
            }
        ],
    }

    with pytest.raises(ValidationError) as exc_info:
        UITestSuite.from_dict(data)

    message = str(exc_info.value)
    assert "Missing Expectations" in message
    assert "expected_results" in message


def test_from_dict_requires_expected_results_nonempty():
    """An empty expected_results dict is treated the same as a missing one."""
    data = {
        "name": "Suite",
        "description": "d",
        "test_cases": [
            {
                "name": "Empty Expectations",
                "html_path": "test.html",
                "queries": ["Is this good?"],
                "expected_results": {},
            }
        ],
    }

    with pytest.raises(ValidationError) as exc_info:
        UITestSuite.from_dict(data)

    assert "Empty Expectations" in str(exc_info.value)


def test_from_dict_handles_missing_name_without_keyerror():
    """A test case dict without 'name' loads (using a placeholder), never KeyError.

    Regression: from_dict computed a fallback ``name`` but then indexed
    ``tc["name"]``, raising KeyError instead of using the fallback.
    """
    data = {
        "name": "Suite",
        "description": "d",
        "test_cases": [
            {
                "html_path": "test.html",
                "queries": ["Is this good?"],
                "expected_results": {"answer": "yes"},
            }
        ],
    }

    suite = UITestSuite.from_dict(data)
    assert suite.test_cases[0].name == "<unnamed test case>"


def test_create_test_suite_handles_missing_name_without_keyerror():
    """create_test_suite mirrors from_dict: a spec without 'name' loads cleanly."""
    lens = LayoutLens(api_key="sk-test")
    suite = lens.create_test_suite(
        name="Suite",
        description="d",
        test_cases=[
            {
                "html_path": "test.html",
                "queries": ["Is this good?"],
                "expected_results": {"answer": "yes"},
            }
        ],
    )
    assert suite.test_cases[0].name == "<unnamed test case>"


def test_shipped_sample_suite_uses_valid_viewports():
    """The shipped example YAML must reference only real viewport names.

    Invalid viewport strings only fail at capture time, so parse the example
    suite and assert every viewport is one the browser engine can resolve.
    """
    import yaml

    from layoutlens.browser import VIEWPORTS

    suite_path = Path(__file__).parent.parent / "examples" / "sample_test_suite.yaml"
    data = yaml.safe_load(suite_path.read_text())
    suite = UITestSuite.from_dict(data)

    for case in suite.test_cases:
        for viewport in case.viewports:
            assert viewport in VIEWPORTS, f"case '{case.name}' uses unknown viewport '{viewport}'"


def test_from_dict_to_dict_round_trip_preserves_expected_fields():
    """expected_confidence and expected_results survive a from_dict -> to_dict round trip."""
    data = {
        "name": "Suite",
        "description": "d",
        "test_cases": [
            {
                "name": "Case",
                "html_path": "test.html",
                "queries": ["Is this good?"],
                "expected_results": {"answer": "yes", "contains": ["nav"]},
                "expected_confidence": 0.85,
            }
        ],
    }

    suite = UITestSuite.from_dict(data)
    case = suite.test_cases[0]
    assert case.expected_results == {"answer": "yes", "contains": ["nav"]}
    assert case.expected_confidence == 0.85

    round_tripped = case.to_dict()
    assert round_tripped["expected_results"] == {"answer": "yes", "contains": ["nav"]}
    assert round_tripped["expected_confidence"] == 0.85
