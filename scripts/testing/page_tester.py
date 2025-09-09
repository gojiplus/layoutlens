"""Main page testing orchestrator for comprehensive UI validation.

This module coordinates screenshot capture, query generation,
and LLM-based visual testing for HTML pages.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

from .screenshot_manager import (
    ScreenshotManager, ViewportConfig, ScreenshotOptions, ScreenshotResult
)
from .query_generator import QueryGenerator, GeneratedQuery

# Import OpenAI for LLM functionality
import os
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None


@dataclass
class TestResult:
    """Result of a single visual test."""
    
    query: str
    answer: str
    confidence: float
    element_id: Optional[str] = None
    element_selector: Optional[str] = None
    category: str = "general"
    screenshot_path: Optional[str] = None
    viewport: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0


@dataclass
class PageTestResult:
    """Complete test results for a single page."""
    
    html_path: str
    timestamp: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    test_results: List[TestResult] = field(default_factory=list)
    screenshots: List[ScreenshotResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate of tests."""
        if self.total_tests == 0:
            return 0.0
        return self.passed_tests / self.total_tests


class PageTester:
    """Main orchestrator for comprehensive page testing.
    
    This class coordinates:
    - Screenshot capture across multiple viewports
    - Automatic query generation from HTML analysis
    - LLM-based visual validation
    - Result aggregation and reporting
    """
    
    def __init__(
        self,
        screenshot_dir: str = "test_screenshots",
        results_dir: str = "test_results",
        openai_api_key: Optional[str] = None,
        model: str = "gpt-4o-mini"
    ):
        """Initialize the page tester.
        
        Parameters
        ----------
        screenshot_dir : str
            Directory for storing test screenshots
        results_dir : str
            Directory for storing test results
        openai_api_key : str, optional
            OpenAI API key for LLM testing
        model : str
            OpenAI model to use for testing
        """
        self.screenshot_dir = Path(screenshot_dir)
        self.results_dir = Path(results_dir)
        
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        self.query_generator = QueryGenerator()
        
        # Initialize OpenAI client
        self.openai_client = None
        self.model = model
        
        if OPENAI_AVAILABLE and openai_api_key:
            try:
                self.openai_client = openai.OpenAI(api_key=openai_api_key)
                print(f"OpenAI client initialized with model: {model}")
            except Exception as e:
                print(f"Warning: Could not initialize OpenAI client: {e}")
        elif not OPENAI_AVAILABLE:
            print("Warning: OpenAI not available. Install 'openai' package for LLM testing.")
        else:
            print("Warning: No OpenAI API key provided.")
    
    def test_page(
        self,
        html_path: str,
        viewports: Optional[List[ViewportConfig]] = None,
        custom_queries: Optional[List[str]] = None,
        screenshot_options: Optional[ScreenshotOptions] = None,
        auto_generate_queries: bool = True
    ) -> PageTestResult:
        """Test a single HTML page comprehensively.
        
        Parameters
        ----------
        html_path : str
            Path to HTML file to test
        viewports : List[ViewportConfig], optional
            Viewports to test across
        custom_queries : List[str], optional
            Custom test queries to include
        screenshot_options : ScreenshotOptions, optional
            Options for screenshot capture
        auto_generate_queries : bool
            Whether to auto-generate queries from HTML analysis
            
        Returns
        -------
        PageTestResult
            Complete test results for the page
        """
        start_time = time.time()
        
        print(f"Testing page: {html_path}")
        
        # Capture screenshots across viewports
        screenshots = self._capture_screenshots(html_path, viewports, screenshot_options)
        
        # Generate test queries
        queries = self._generate_test_queries(html_path, custom_queries, auto_generate_queries)
        
        # Execute visual tests
        test_results = self._execute_visual_tests(screenshots, queries)
        
        # Aggregate results
        passed_tests = sum(1 for result in test_results if self._is_test_passed(result))
        failed_tests = len(test_results) - passed_tests
        
        execution_time = time.time() - start_time
        
        page_result = PageTestResult(
            html_path=html_path,
            timestamp=str(int(time.time())),
            total_tests=len(test_results),
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            test_results=test_results,
            screenshots=screenshots,
            execution_time=execution_time,
            metadata={
                "viewports_tested": len(screenshots),
                "auto_generated_queries": len(queries) - len(custom_queries or []),
                "custom_queries": len(custom_queries or [])
            }
        )
        
        # Save results
        self._save_results(page_result)
        
        print(f"Completed testing {html_path}: {passed_tests}/{len(test_results)} tests passed")
        
        return page_result
    
    def test_multiple_pages(
        self,
        html_files: List[str],
        viewports: Optional[List[ViewportConfig]] = None,
        screenshot_options: Optional[ScreenshotOptions] = None
    ) -> List[PageTestResult]:
        """Test multiple HTML pages.
        
        Parameters
        ----------
        html_files : List[str]
            List of HTML file paths to test
        viewports : List[ViewportConfig], optional
            Viewports to test across
        screenshot_options : ScreenshotOptions, optional
            Options for screenshot capture
            
        Returns
        -------
        List[PageTestResult]
            Results for all tested pages
        """
        results = []
        
        print(f"Testing {len(html_files)} pages...")
        
        for i, html_path in enumerate(html_files):
            try:
                print(f"\n[{i+1}/{len(html_files)}] Testing {html_path}")
                result = self.test_page(html_path, viewports, screenshot_options=screenshot_options)
                results.append(result)
            except Exception as e:
                print(f"Error testing {html_path}: {e}")
                continue
        
        # Generate summary report
        self._generate_summary_report(results)
        
        return results
    
    def compare_pages(
        self,
        page_a_path: str,
        page_b_path: str,
        viewport: Optional[ViewportConfig] = None,
        comparison_query: str = "Do these two layouts look the same?"
    ) -> Dict[str, Any]:
        """Compare two pages visually.
        
        Parameters
        ----------
        page_a_path : str
            Path to first HTML file
        page_b_path : str
            Path to second HTML file
        viewport : ViewportConfig, optional
            Viewport for comparison
        comparison_query : str
            Query to use for comparison
            
        Returns
        -------
        Dict[str, Any]
            Comparison result with screenshots and LLM analysis
        """
        if not self.openai_client:
            raise RuntimeError("OpenAI client not available for comparison")
        
        if viewport is None:
            viewport = ScreenshotManager.VIEWPORT_PRESETS["desktop"]
        
        # Capture screenshots
        with ScreenshotManager(str(self.screenshot_dir)) as manager:
            screenshot_a = manager.capture_single(
                page_a_path, 
                viewport,
                output_name=f"compare_a_{Path(page_a_path).stem}"
            )
            screenshot_b = manager.capture_single(
                page_b_path,
                viewport,
                output_name=f"compare_b_{Path(page_b_path).stem}"
            )
        
        # Compare using OpenAI
        try:
            if self.openai_client:
                answer = self._compare_screenshots_with_openai(
                    screenshot_a.path, screenshot_b.path, comparison_query
                )
            else:
                answer = "Error: No OpenAI client available for comparison"
        except Exception as e:
            answer = f"Error during comparison: {e}"
        
        return {
            "page_a": page_a_path,
            "page_b": page_b_path,
            "screenshot_a": screenshot_a.path,
            "screenshot_b": screenshot_b.path,
            "query": comparison_query,
            "answer": answer,
            "viewport": viewport.name,
            "timestamp": str(int(time.time()))
        }
    
    def _capture_screenshots(
        self,
        html_path: str,
        viewports: Optional[List[ViewportConfig]],
        options: Optional[ScreenshotOptions]
    ) -> List[ScreenshotResult]:
        """Capture screenshots for the page."""
        with ScreenshotManager(str(self.screenshot_dir)) as manager:
            if viewports:
                screenshots = manager.capture_multiple_viewports(html_path, viewports, options)
            else:
                # Use default viewports
                screenshots = manager.capture_multiple_viewports(html_path, options=options)
        
        return screenshots
    
    def _generate_test_queries(
        self,
        html_path: str,
        custom_queries: Optional[List[str]],
        auto_generate: bool
    ) -> List[GeneratedQuery]:
        """Generate test queries for the page."""
        queries = []
        
        # Add custom queries
        if custom_queries:
            for query_text in custom_queries:
                queries.append(GeneratedQuery(
                    query=query_text,
                    category="custom",
                    confidence=1.0
                ))
        
        # Auto-generate queries from HTML analysis
        if auto_generate:
            try:
                generated = self.query_generator.generate_queries_from_file(html_path)
                queries.extend(generated)
            except Exception as e:
                print(f"Warning: Could not auto-generate queries: {e}")
        
        return queries
    
    def _execute_visual_tests(
        self,
        screenshots: List[ScreenshotResult],
        queries: List[GeneratedQuery]
    ) -> List[TestResult]:
        """Execute visual tests using screenshots and queries."""
        results = []
        
        if not self.openai_client:
            print("Warning: No OpenAI client available. Skipping visual validation.")
            return results
        
        for screenshot in screenshots:
            for query in queries:
                start_time = time.time()
                
                try:
                    # Use OpenAI Vision to analyze screenshot
                    answer = self._analyze_screenshot_with_openai(screenshot.path, query.query)
                    execution_time = time.time() - start_time
                    
                    result = TestResult(
                        query=query.query,
                        answer=answer,
                        confidence=query.confidence,
                        element_id=query.element_id,
                        element_selector=query.element_selector,
                        category=query.category,
                        screenshot_path=screenshot.path,
                        viewport=screenshot.viewport.name,
                        execution_time=execution_time,
                        metadata=query.metadata
                    )
                    results.append(result)
                    
                except Exception as e:
                    execution_time = time.time() - start_time
                    result = TestResult(
                        query=query.query,
                        answer=f"Error: {str(e)}",
                        confidence=0.0,
                        category=query.category,
                        screenshot_path=screenshot.path,
                        viewport=screenshot.viewport.name,
                        execution_time=execution_time
                    )
                    results.append(result)
        
        return results
    
    def _analyze_screenshot_with_openai(self, screenshot_path: str, question: str) -> str:
        """Analyze screenshot using OpenAI Vision API."""
        import base64
        
        # Read and encode the screenshot
        with open(screenshot_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode()
        
        response = self.openai_client.chat.completions.create(
            model="gpt-4o",  # Use vision model
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Please analyze this screenshot and answer the question: {question}"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_data}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=500
        )
        
        return response.choices[0].message.content
    
    def _compare_screenshots_with_openai(self, screenshot_a: str, screenshot_b: str, question: str) -> str:
        """Compare two screenshots using OpenAI Vision API."""
        import base64
        
        # Read and encode both screenshots
        with open(screenshot_a, "rb") as image_file:
            image_a_data = base64.b64encode(image_file.read()).decode()
            
        with open(screenshot_b, "rb") as image_file:
            image_b_data = base64.b64encode(image_file.read()).decode()
        
        response = self.openai_client.chat.completions.create(
            model="gpt-4o",  # Use vision model
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Please compare these two screenshots and answer: {question}"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_a_data}"
                            }
                        },
                        {"type": "text", "text": "Second image:"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b_data}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=500
        )
        
        return response.choices[0].message.content
    
    def _is_test_passed(self, result: TestResult) -> bool:
        """Determine if a test result indicates success."""
        if result.answer.startswith("Error:"):
            return False
        
        # Simple heuristic: positive responses indicate success
        answer_lower = result.answer.lower()
        positive_indicators = ["yes", "correct", "properly", "visible", "aligned", "true"]
        negative_indicators = ["no", "incorrect", "not", "missing", "hidden", "false"]
        
        positive_score = sum(1 for indicator in positive_indicators if indicator in answer_lower)
        negative_score = sum(1 for indicator in negative_indicators if indicator in answer_lower)
        
        # If we have an expected answer, compare against it
        if hasattr(result, 'expected_answer') and result.metadata.get('expected_answer'):
            expected = result.metadata['expected_answer'].lower()
            return expected in answer_lower
        
        # Otherwise use heuristic
        return positive_score > negative_score
    
    def _save_results(self, page_result: PageTestResult) -> None:
        """Save test results to file."""
        base_name = Path(page_result.html_path).stem
        results_file = self.results_dir / f"{base_name}_{page_result.timestamp}.json"
        
        # Convert to serializable format
        results_data = {
            "html_path": page_result.html_path,
            "timestamp": page_result.timestamp,
            "summary": {
                "total_tests": page_result.total_tests,
                "passed_tests": page_result.passed_tests,
                "failed_tests": page_result.failed_tests,
                "success_rate": page_result.success_rate,
                "execution_time": page_result.execution_time
            },
            "screenshots": [
                {
                    "path": shot.path,
                    "viewport": shot.viewport.name,
                    "file_size": shot.file_size
                }
                for shot in page_result.screenshots
            ],
            "test_results": [
                {
                    "query": result.query,
                    "answer": result.answer,
                    "category": result.category,
                    "viewport": result.viewport,
                    "screenshot_path": result.screenshot_path,
                    "execution_time": result.execution_time,
                    "passed": self._is_test_passed(result)
                }
                for result in page_result.test_results
            ],
            "metadata": page_result.metadata
        }
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)
        
        print(f"Results saved to: {results_file}")
    
    def _generate_summary_report(self, results: List[PageTestResult]) -> None:
        """Generate a summary report for multiple page tests."""
        if not results:
            return
        
        total_pages = len(results)
        total_tests = sum(r.total_tests for r in results)
        total_passed = sum(r.passed_tests for r in results)
        total_failed = sum(r.failed_tests for r in results)
        overall_success_rate = total_passed / total_tests if total_tests > 0 else 0
        
        summary = {
            "summary": {
                "total_pages": total_pages,
                "total_tests": total_tests,
                "total_passed": total_passed,
                "total_failed": total_failed,
                "overall_success_rate": overall_success_rate,
                "timestamp": str(int(time.time()))
            },
            "page_results": [
                {
                    "html_path": r.html_path,
                    "success_rate": r.success_rate,
                    "total_tests": r.total_tests,
                    "execution_time": r.execution_time
                }
                for r in results
            ]
        }
        
        summary_file = self.results_dir / f"summary_{summary['summary']['timestamp']}.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"\nSummary Report:")
        print(f"  Pages tested: {total_pages}")
        print(f"  Total tests: {total_tests}")
        print(f"  Success rate: {overall_success_rate:.2%}")
        print(f"  Report saved: {summary_file}")


def test_html_file(
    html_path: str,
    output_dir: str = "test_output",
    openai_api_key: Optional[str] = None
) -> PageTestResult:
    """Convenience function to test a single HTML file.
    
    Parameters
    ----------
    html_path : str
        Path to HTML file to test
    output_dir : str
        Directory for test outputs
    openai_api_key : str, optional
        OpenAI API key for LLM testing
        
    Returns
    -------
    PageTestResult
        Test results for the page
    """
    tester = PageTester(
        screenshot_dir=f"{output_dir}/screenshots",
        results_dir=f"{output_dir}/results",
        openai_api_key=openai_api_key
    )
    
    return tester.test_page(html_path)