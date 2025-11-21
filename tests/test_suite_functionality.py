"""Test the new test suite functionality."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from layoutlens import LayoutLens, TestCase, TestSuite, TestResult, AnalysisResult


def test_test_case_creation():
    """Test creating a TestCase object."""
    test_case = TestCase(
        name="Homepage Test",
        html_path="test.html",
        queries=["Is it accessible?", "Is it mobile-friendly?"],
        viewports=["desktop", "mobile_portrait"],
        metadata={"priority": "high"}
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
    """Test creating a TestSuite object."""
    test_case1 = TestCase(
        name="Test 1",
        html_path="page1.html",
        queries=["Query 1"]
    )
    
    test_case2 = TestCase(
        name="Test 2",
        html_path="page2.html",
        queries=["Query 2"]
    )
    
    suite = TestSuite(
        name="UI Test Suite",
        description="Testing UI components",
        test_cases=[test_case1, test_case2],
        metadata={"version": "1.0"}
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
    test_case = TestCase(
        name="Save Test",
        html_path="save_test.html",
        queries=["Is it working?"]
    )
    
    suite = TestSuite(
        name="Save Suite",
        description="Test saving and loading",
        test_cases=[test_case]
    )
    
    # Save to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = Path(f.name)
    
    try:
        suite.save(temp_path)
        
        # Load the suite
        loaded_suite = TestSuite.load(temp_path)
        
        assert loaded_suite.name == suite.name
        assert loaded_suite.description == suite.description
        assert len(loaded_suite.test_cases) == 1
        assert loaded_suite.test_cases[0].name == "Save Test"
        
    finally:
        # Clean up
        if temp_path.exists():
            temp_path.unlink()


def test_test_result():
    """Test TestResult functionality."""
    mock_results = [
        AnalysisResult(
            source="test.html",
            query="Is it accessible?",
            answer="Yes, it's accessible",
            confidence=0.9,
            reasoning="Good contrast",
            metadata={}
        ),
        AnalysisResult(
            source="test.html",
            query="Is it mobile-friendly?",
            answer="No issues found",
            confidence=0.8,
            reasoning="Mobile optimized",
            metadata={}
        )
    ]
    
    result = TestResult(
        suite_name="Test Suite",
        test_case_name="Test Case",
        total_tests=2,
        passed_tests=2,
        failed_tests=0,
        results=mock_results,
        duration_seconds=5.5
    )
    
    assert result.success_rate == 1.0
    assert result.total_tests == 2
    assert result.passed_tests == 2
    
    # Test to_dict
    data = result.to_dict()
    assert data["suite_name"] == "Test Suite"
    assert data["success_rate"] == 1.0
    assert len(data["results"]) == 2


@patch('layoutlens.api.core.LayoutLens.analyze')
def test_run_test_suite(mock_analyze):
    """Test running a test suite with LayoutLens."""
    # Setup mock
    mock_analyze.return_value = AnalysisResult(
        source="test.html",
        query="Is it good?",
        answer="Test passed",
        confidence=0.85,
        reasoning="Good layout",
        metadata={}
    )
    
    # Create test suite
    test_case = TestCase(
        name="Test Case",
        html_path="test.html",
        queries=["Is it good?"],
        viewports=["desktop"]
    )
    
    suite = TestSuite(
        name="Test Suite",
        description="Test description",
        test_cases=[test_case]
    )
    
    # Run the suite
    lens = LayoutLens(api_key="test_key")
    results = lens.run_test_suite(suite)
    
    assert len(results) == 1
    result = results[0]
    assert result.suite_name == "Test Suite"
    assert result.test_case_name == "Test Case"
    assert result.total_tests == 1
    assert result.passed_tests == 1  # Confidence > 0.7
    assert result.failed_tests == 0
    
    # Verify analyze was called
    mock_analyze.assert_called_once()


@patch('layoutlens.api.core.LayoutLens.analyze')
def test_run_test_suite_with_failure(mock_analyze):
    """Test running a test suite with failures."""
    # Setup mock to fail
    mock_analyze.side_effect = Exception("API error")
    
    # Create test suite
    test_case = TestCase(
        name="Failing Test",
        html_path="fail.html",
        queries=["Will this fail?"],
        viewports=["desktop"]
    )
    
    suite = TestSuite(
        name="Failing Suite",
        description="Test with failures",
        test_cases=[test_case]
    )
    
    # Run the suite
    lens = LayoutLens(api_key="test_key")
    results = lens.run_test_suite(suite)
    
    assert len(results) == 1
    result = results[0]
    assert result.total_tests == 1
    assert result.passed_tests == 0
    assert result.failed_tests == 1
    assert result.success_rate == 0.0


def test_create_test_suite():
    """Test creating a test suite using LayoutLens."""
    lens = LayoutLens(api_key="test_key")
    
    test_cases = [
        {
            "name": "Homepage",
            "html_path": "homepage.html",
            "queries": ["Is the navigation visible?"],
            "viewports": ["desktop"],
            "metadata": {"page": "home"}
        },
        {
            "name": "About",
            "html_path": "about.html",
            "queries": ["Is the content readable?"],
            "viewports": ["mobile_portrait"]
        }
    ]
    
    suite = lens.create_test_suite(
        name="Website Tests",
        description="Test all pages",
        test_cases=test_cases
    )
    
    assert suite.name == "Website Tests"
    assert len(suite.test_cases) == 2
    assert suite.test_cases[0].name == "Homepage"
    assert suite.test_cases[1].viewports == ["mobile_portrait"]