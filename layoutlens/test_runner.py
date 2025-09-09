"""Unified test execution system for LayoutLens framework.

This module provides comprehensive test execution capabilities including
parallel processing, CI/CD integration, and detailed reporting.
"""

from __future__ import annotations

import json
import time
import concurrent.futures
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Union

from .config import Config
from .core import TestSuite, TestCase

# Import components
try:
    from .vision import PageTester, PageTestResult
except ImportError:
    PageTester = None
    PageTestResult = None


@dataclass
class TestSession:
    """Test execution session with results and metadata."""
    
    session_id: str
    start_time: float
    end_time: Optional[float] = None
    config: Optional[Config] = None
    test_suites: List[TestSuite] = field(default_factory=list)
    results: List[PageTestResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> float:
        """Get session duration in seconds."""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time
    
    @property
    def total_tests(self) -> int:
        """Get total number of tests executed."""
        return sum(result.total_tests for result in self.results)
    
    @property
    def total_passed(self) -> int:
        """Get total number of passed tests."""
        return sum(result.passed_tests for result in self.results)
    
    @property
    def success_rate(self) -> float:
        """Get overall success rate."""
        if self.total_tests == 0:
            return 0.0
        return self.total_passed / self.total_tests


class TestRunner:
    """Unified test runner for comprehensive test execution.
    
    This class provides:
    - Sequential and parallel test execution
    - Progress monitoring and reporting
    - Integration with CI/CD systems
    - Flexible result formatting
    - Error handling and recovery
    """
    
    def __init__(self, config: Optional[Config] = None):
        """Initialize the test runner.
        
        Parameters
        ----------
        config : Config, optional
            Configuration instance (creates default if not provided)
        """
        self.config = config or Config()
        self.current_session: Optional[TestSession] = None
        self.progress_callback: Optional[Callable[[str, int, int], None]] = None
    
    def run_test_suite(
        self,
        test_suite: Union[str, TestSuite],
        parallel: Optional[bool] = None,
        max_workers: Optional[int] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> TestSession:
        """Execute a complete test suite.
        
        Parameters
        ----------
        test_suite : str or TestSuite
            Test suite file path or TestSuite instance
        parallel : bool, optional
            Override config parallel execution setting
        max_workers : int, optional
            Override config max workers setting
        progress_callback : Callable, optional
            Callback function for progress updates: callback(stage, current, total)
            
        Returns
        -------
        TestSession
            Complete test session with results
        """
        # Load test suite if path provided
        if isinstance(test_suite, str):
            suite = self._load_test_suite(test_suite)
            if not suite:
                raise ValueError(f"Could not load test suite: {test_suite}")
        else:
            suite = test_suite
        
        # Create test session
        session_id = f"session_{int(time.time())}"
        self.current_session = TestSession(
            session_id=session_id,
            start_time=time.time(),
            config=self.config,
            test_suites=[suite]
        )
        
        # Set progress callback
        if progress_callback:
            self.progress_callback = progress_callback
        
        print(f"Starting test session: {session_id}")
        print(f"Test suite: {suite.name}")
        print(f"Test cases: {len(suite.test_cases)}")
        
        # Determine execution mode
        use_parallel = parallel if parallel is not None else self.config.test.parallel_execution
        workers = max_workers if max_workers is not None else self.config.test.max_workers
        
        if use_parallel and len(suite.test_cases) > 1:
            print(f"Executing in parallel with {workers} workers")
            results = self._execute_parallel(suite, workers)
        else:
            print("Executing sequentially")
            results = self._execute_sequential(suite)
        
        # Finalize session
        self.current_session.results = results
        self.current_session.end_time = time.time()
        
        # Generate reports
        self._generate_session_report(self.current_session)
        
        # Print summary
        self._print_session_summary(self.current_session)
        
        return self.current_session
    
    def run_multiple_suites(
        self,
        test_suites: List[Union[str, TestSuite]],
        parallel: Optional[bool] = None,
        max_workers: Optional[int] = None
    ) -> TestSession:
        """Execute multiple test suites in a single session.
        
        Parameters
        ----------
        test_suites : List[Union[str, TestSuite]]
            List of test suite paths or TestSuite instances
        parallel : bool, optional
            Override config parallel execution setting
        max_workers : int, optional
            Override config max workers setting
            
        Returns
        -------
        TestSession
            Complete test session with results from all suites
        """
        # Load all test suites
        suites = []
        for suite_def in test_suites:
            if isinstance(suite_def, str):
                suite = self._load_test_suite(suite_def)
                if suite:
                    suites.append(suite)
                else:
                    print(f"Warning: Could not load test suite: {suite_def}")
            else:
                suites.append(suite_def)
        
        if not suites:
            raise ValueError("No valid test suites provided")
        
        # Create combined test session
        session_id = f"multi_session_{int(time.time())}"
        self.current_session = TestSession(
            session_id=session_id,
            start_time=time.time(),
            config=self.config,
            test_suites=suites
        )
        
        print(f"Starting multi-suite session: {session_id}")
        print(f"Test suites: {len(suites)}")
        total_cases = sum(len(suite.test_cases) for suite in suites)
        print(f"Total test cases: {total_cases}")
        
        # Execute all suites
        all_results = []
        for i, suite in enumerate(suites):
            print(f"\n[{i+1}/{len(suites)}] Executing suite: {suite.name}")
            
            if self.progress_callback:
                self.progress_callback(f"Suite {suite.name}", i, len(suites))
            
            # Execute suite
            use_parallel = parallel if parallel is not None else self.config.test.parallel_execution
            workers = max_workers if max_workers is not None else self.config.test.max_workers
            
            if use_parallel and len(suite.test_cases) > 1:
                suite_results = self._execute_parallel(suite, workers)
            else:
                suite_results = self._execute_sequential(suite)
            
            all_results.extend(suite_results)
        
        # Finalize session
        self.current_session.results = all_results
        self.current_session.end_time = time.time()
        
        # Generate reports
        self._generate_session_report(self.current_session)
        
        # Print summary
        self._print_session_summary(self.current_session)
        
        return self.current_session
    
    def run_regression_tests(
        self,
        baseline_dir: str,
        current_dir: str,
        test_patterns: List[str],
        viewports: Optional[List[str]] = None
    ) -> TestSession:
        """Run regression tests comparing baseline and current versions.
        
        Parameters
        ----------
        baseline_dir : str
            Directory containing baseline HTML files
        current_dir : str
            Directory containing current HTML files
        test_patterns : List[str]
            File patterns to match for testing (e.g., ["*.html", "pages/*.html"])
        viewports : List[str], optional
            Viewport names to test across
            
        Returns
        -------
        TestSession
            Regression test session results
        """
        import glob
        
        # Find matching files
        baseline_files = []
        current_files = []
        
        for pattern in test_patterns:
            baseline_matches = glob.glob(str(Path(baseline_dir) / pattern))
            current_matches = glob.glob(str(Path(current_dir) / pattern))
            
            baseline_files.extend(baseline_matches)
            current_files.extend(current_matches)
        
        # Match baseline and current files
        test_pairs = []
        for baseline_file in baseline_files:
            baseline_name = Path(baseline_file).name
            current_file = None
            
            for cf in current_files:
                if Path(cf).name == baseline_name:
                    current_file = cf
                    break
            
            if current_file:
                test_pairs.append((baseline_file, current_file))
            else:
                print(f"Warning: No current version found for {baseline_name}")
        
        if not test_pairs:
            raise ValueError("No matching file pairs found for regression testing")
        
        # Create test cases for comparison
        test_cases = []
        for i, (baseline_file, current_file) in enumerate(test_pairs):
            file_name = Path(baseline_file).name
            test_case = TestCase(
                name=f"Regression_{file_name}",
                html_path=current_file,  # Test the current version
                queries=[
                    f"Does this layout match the baseline design?",
                    f"Are there any visual regressions compared to the baseline?",
                    f"Is the layout consistent with the previous version?"
                ],
                viewports=viewports or ["desktop"],
                metadata={
                    "baseline_file": baseline_file,
                    "current_file": current_file,
                    "test_type": "regression"
                }
            )
            test_cases.append(test_case)
        
        # Create regression test suite
        regression_suite = TestSuite(
            name="Regression_Tests",
            description=f"Regression testing: {baseline_dir} vs {current_dir}",
            test_cases=test_cases,
            metadata={
                "baseline_dir": baseline_dir,
                "current_dir": current_dir,
                "test_patterns": test_patterns
            }
        )
        
        # Execute regression tests
        return self.run_test_suite(regression_suite)
    
    def _execute_sequential(self, suite: TestSuite) -> List[PageTestResult]:
        """Execute test cases sequentially."""
        results = []
        
        page_tester = self._get_page_tester()
        if not page_tester:
            print("Error: PageTester not available")
            return results
        
        for i, test_case in enumerate(suite.test_cases):
            if self.progress_callback:
                self.progress_callback(f"Test {test_case.name}", i, len(suite.test_cases))
            
            print(f"  [{i+1}/{len(suite.test_cases)}] {test_case.name}")
            
            try:
                # Convert viewport names to configurations
                viewport_configs = self._get_viewport_configs(test_case.viewports)
                
                result = page_tester.test_page(
                    html_path=test_case.html_path,
                    viewports=viewport_configs,
                    custom_queries=test_case.queries,
                    auto_generate_queries=len(test_case.queries) == 0
                )
                
                if result:
                    results.append(result)
                    print(f"    Passed: {result.passed_tests}/{result.total_tests}")
                else:
                    print(f"    Error: Test execution failed")
                    
            except Exception as e:
                print(f"    Error: {e}")
                if not self.config.test.continue_on_error:
                    break
                continue
        
        return results
    
    def _execute_parallel(self, suite: TestSuite, max_workers: int) -> List[PageTestResult]:
        """Execute test cases in parallel."""
        results = []
        
        def execute_test_case(test_case: TestCase) -> Optional[PageTestResult]:
            """Execute a single test case (for parallel execution)."""
            try:
                # Create separate page tester for this thread
                page_tester = self._get_page_tester()
                if not page_tester:
                    return None
                
                # Convert viewport names to configurations
                viewport_configs = self._get_viewport_configs(test_case.viewports)
                
                result = page_tester.test_page(
                    html_path=test_case.html_path,
                    viewports=viewport_configs,
                    custom_queries=test_case.queries,
                    auto_generate_queries=len(test_case.queries) == 0
                )
                
                return result
                
            except Exception as e:
                print(f"Error in parallel execution for {test_case.name}: {e}")
                return None
        
        # Execute test cases in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all test cases
            future_to_test = {
                executor.submit(execute_test_case, test_case): test_case 
                for test_case in suite.test_cases
            }
            
            # Collect results as they complete
            for i, future in enumerate(concurrent.futures.as_completed(future_to_test)):
                test_case = future_to_test[future]
                
                if self.progress_callback:
                    self.progress_callback(f"Test {test_case.name}", i, len(suite.test_cases))
                
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                        print(f"  Completed {test_case.name}: {result.passed_tests}/{result.total_tests}")
                    else:
                        print(f"  Failed {test_case.name}")
                        
                except Exception as e:
                    print(f"  Error in {test_case.name}: {e}")
                    if not self.config.test.continue_on_error:
                        # Cancel remaining futures
                        for remaining_future in future_to_test:
                            remaining_future.cancel()
                        break
        
        return results
    
    def _get_page_tester(self) -> Optional[PageTester]:
        """Get a PageTester instance."""
        if not PageTester:
            return None
        
        return PageTester(
            screenshot_dir=str(self.config.get_output_path("screenshots")),
            results_dir=str(self.config.get_output_path("results")),
            openai_api_key=self.config.llm.api_key,
            model=self.config.llm.model
        )
    
    def _get_viewport_configs(self, viewport_names: List[str]):
        """Convert viewport names to ScreenshotManager configurations."""
        if not viewport_names:
            return None
        
        from .capture.screenshot_manager import ViewportConfig as SMViewportConfig
        
        configs = []
        for name in viewport_names:
            viewport = self.config.get_viewport_by_name(name)
            if viewport:
                sm_viewport = SMViewportConfig(
                    name=viewport.name,
                    width=viewport.width,
                    height=viewport.height,
                    device_scale_factor=viewport.device_scale_factor,
                    is_mobile=viewport.is_mobile,
                    has_touch=viewport.has_touch,
                    user_agent=viewport.user_agent
                )
                configs.append(sm_viewport)
            else:
                print(f"Warning: Unknown viewport '{name}'")
        
        return configs if configs else None
    
    def _load_test_suite(self, suite_path: str) -> Optional[TestSuite]:
        """Load test suite from YAML file."""
        import yaml
        
        try:
            with open(suite_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            test_cases = []
            for case_data in data.get('test_cases', []):
                test_case = TestCase(
                    name=case_data['name'],
                    html_path=case_data['html_path'],
                    queries=case_data.get('queries', []),
                    viewports=case_data.get('viewports', []),
                    expected_results=case_data.get('expected_results', {}),
                    metadata=case_data.get('metadata', {})
                )
                test_cases.append(test_case)
            
            suite = TestSuite(
                name=data['name'],
                description=data.get('description', ''),
                test_cases=test_cases,
                metadata=data.get('metadata', {})
            )
            
            return suite
            
        except Exception as e:
            print(f"Error loading test suite {suite_path}: {e}")
            return None
    
    def _generate_session_report(self, session: TestSession) -> None:
        """Generate comprehensive session report."""
        reports_dir = self.config.get_output_path("reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        # JSON report
        json_report_path = reports_dir / f"{session.session_id}_report.json"
        self._generate_json_report(session, json_report_path)
        
        # HTML report (if requested)
        if self.config.output.format == "html":
            html_report_path = reports_dir / f"{session.session_id}_report.html"
            self._generate_html_report(session, html_report_path)
    
    def _generate_json_report(self, session: TestSession, output_path: Path) -> None:
        """Generate JSON format report."""
        report_data = {
            "session": {
                "session_id": session.session_id,
                "start_time": session.start_time,
                "end_time": session.end_time,
                "duration": session.duration,
                "total_tests": session.total_tests,
                "total_passed": session.total_passed,
                "success_rate": session.success_rate
            },
            "test_suites": [
                {
                    "name": suite.name,
                    "description": suite.description,
                    "test_cases": len(suite.test_cases)
                }
                for suite in session.test_suites
            ],
            "results": [
                {
                    "html_path": result.html_path,
                    "timestamp": result.timestamp,
                    "total_tests": result.total_tests,
                    "passed_tests": result.passed_tests,
                    "success_rate": result.success_rate,
                    "execution_time": result.execution_time,
                    "metadata": result.metadata
                }
                for result in session.results
            ],
            "metadata": session.metadata
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        print(f"JSON report saved: {output_path}")
    
    def _generate_html_report(self, session: TestSession, output_path: Path) -> None:
        """Generate HTML format report."""
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>LayoutLens Test Report - {session.session_id}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }}
                .header {{ background-color: #343a40; color: white; padding: 20px; border-radius: 8px; }}
                .summary {{ background-color: white; padding: 20px; margin: 20px 0; border-radius: 8px; }}
                .results {{ background-color: white; padding: 20px; border-radius: 8px; }}
                .success {{ color: #28a745; }}
                .failure {{ color: #dc3545; }}
                .warning {{ color: #ffc107; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #f8f9fa; }}
                .progress-bar {{ width: 100%; height: 20px; background-color: #e9ecef; border-radius: 10px; overflow: hidden; }}
                .progress-fill {{ height: 100%; background-color: #28a745; transition: width 0.3s; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>LayoutLens Test Report</h1>
                <p>Session: {session.session_id}</p>
                <p>Duration: {session.duration:.2f}s</p>
            </div>
            
            <div class="summary">
                <h2>Test Summary</h2>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {session.success_rate * 100}%"></div>
                </div>
                <p><strong>Success Rate:</strong> {session.success_rate:.2%} ({session.total_passed}/{session.total_tests} tests)</p>
                <p><strong>Test Suites:</strong> {len(session.test_suites)}</p>
                <p><strong>Test Cases:</strong> {len(session.results)}</p>
            </div>
            
            <div class="results">
                <h2>Test Results</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Test Case</th>
                            <th>Tests</th>
                            <th>Success Rate</th>
                            <th>Duration</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for result in session.results:
            status_class = "success" if result.success_rate > 0.8 else "warning" if result.success_rate > 0.5 else "failure"
            status_text = "✓ Passed" if result.success_rate > 0.8 else "⚠ Warning" if result.success_rate > 0.5 else "✗ Failed"
            
            html_content += f"""
                        <tr>
                            <td>{Path(result.html_path).name}</td>
                            <td>{result.passed_tests}/{result.total_tests}</td>
                            <td>{result.success_rate:.2%}</td>
                            <td>{result.execution_time:.2f}s</td>
                            <td class="{status_class}">{status_text}</td>
                        </tr>
            """
        
        html_content += """
                    </tbody>
                </table>
            </div>
        </body>
        </html>
        """
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"HTML report saved: {output_path}")
    
    def _print_session_summary(self, session: TestSession) -> None:
        """Print session summary to console."""
        print(f"\n{'='*60}")
        print(f"Test Session Complete: {session.session_id}")
        print(f"{'='*60}")
        print(f"Duration: {session.duration:.2f}s")
        print(f"Test suites: {len(session.test_suites)}")
        print(f"Test cases: {len(session.results)}")
        print(f"Total tests: {session.total_tests}")
        print(f"Passed: {session.total_passed}")
        print(f"Failed: {session.total_tests - session.total_passed}")
        print(f"Success rate: {session.success_rate:.2%}")
        print(f"{'='*60}")