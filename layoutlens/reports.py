"""Rich reporting functionality for LayoutLens test results.

This module provides comprehensive reporting capabilities including
HTML and JSON report generation for test sessions and results.
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

# Import PageTestResult with fallback
try:
    from .vision import PageTestResult
except ImportError:
    # Create a placeholder if vision module not available
    from typing import NamedTuple
    class PageTestResult(NamedTuple):
        html_path: str = ""
        timestamp: str = ""
        total_tests: int = 0
        passed_tests: int = 0
        execution_time: float = 0.0
        metadata: dict = {}
        
        @property
        def success_rate(self) -> float:
            return self.passed_tests / self.total_tests if self.total_tests > 0 else 0.0


@dataclass
class TestSession:
    """Test execution session with results and metadata."""
    
    session_id: str
    start_time: float
    end_time: Optional[float] = None
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


class ReportGenerator:
    """Generate comprehensive reports for LayoutLens test results."""
    
    def __init__(self, output_dir: str = "layoutlens_output/reports"):
        """Initialize report generator.
        
        Parameters
        ----------
        output_dir : str
            Directory to save reports
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def create_session(self, session_id: Optional[str] = None) -> TestSession:
        """Create a new test session.
        
        Parameters
        ----------
        session_id : str, optional
            Custom session ID (auto-generated if not provided)
            
        Returns
        -------
        TestSession
            New test session instance
        """
        if not session_id:
            session_id = f"session_{int(time.time())}"
        
        return TestSession(
            session_id=session_id,
            start_time=time.time()
        )
    
    def finalize_session(self, session: TestSession) -> TestSession:
        """Finalize a test session and generate reports.
        
        Parameters
        ----------
        session : TestSession
            Test session to finalize
            
        Returns
        -------
        TestSession
            Finalized session with end time set
        """
        session.end_time = time.time()
        
        # Generate reports
        self.generate_json_report(session)
        self.generate_html_report(session)
        
        # Print summary
        self.print_session_summary(session)
        
        return session
    
    def generate_json_report(self, session: TestSession) -> Path:
        """Generate JSON format report.
        
        Parameters
        ----------
        session : TestSession
            Test session to report on
            
        Returns
        -------
        Path
            Path to generated JSON report
        """
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
        
        output_path = self.output_dir / f"{session.session_id}_report.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        print(f"JSON report saved: {output_path}")
        return output_path
    
    def generate_html_report(self, session: TestSession) -> Path:
        """Generate HTML format report.
        
        Parameters
        ----------
        session : TestSession
            Test session to report on
            
        Returns
        -------
        Path
            Path to generated HTML report
        """
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
        
        output_path = self.output_dir / f"{session.session_id}_report.html"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"HTML report saved: {output_path}")
        return output_path
    
    def print_session_summary(self, session: TestSession) -> None:
        """Print session summary to console.
        
        Parameters
        ----------
        session : TestSession
            Test session to summarize
        """
        print(f"\n{'='*60}")
        print(f"Test Session Complete: {session.session_id}")
        print(f"{'='*60}")
        print(f"Duration: {session.duration:.2f}s")
        print(f"Test cases: {len(session.results)}")
        print(f"Total tests: {session.total_tests}")
        print(f"Passed: {session.total_passed}")
        print(f"Failed: {session.total_tests - session.total_passed}")
        print(f"Success rate: {session.success_rate:.2%}")
        print(f"{'='*60}")