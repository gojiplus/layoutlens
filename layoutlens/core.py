"""Enhanced core LayoutLens class with user-friendly API.

This module provides the main LayoutLens class with comprehensive
testing capabilities and simple API for end users.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

from .config import Config, ViewportConfig

# Import the original LayoutLens for compatibility
import sys
sys.path.append(str(Path(__file__).parent.parent))
try:
    from framework import LayoutLens as OriginalLayoutLens
except ImportError:
    OriginalLayoutLens = None

# Import testing modules
sys.path.append(str(Path(__file__).parent.parent / "scripts"))
try:
    from testing import PageTester, PageTestResult, ScreenshotManager, ScreenshotOptions
    from benchmark import BenchmarkGenerator
except ImportError:
    PageTester = None
    PageTestResult = None
    ScreenshotManager = None
    ScreenshotOptions = None
    BenchmarkGenerator = None


@dataclass
class TestCase:
    """Individual test case for a test suite."""
    
    name: str
    html_path: str
    queries: List[str] = field(default_factory=list)
    viewports: List[str] = field(default_factory=list)  # viewport names
    expected_results: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass 
class TestSuite:
    """Collection of test cases with shared configuration."""
    
    name: str
    description: str
    test_cases: List[TestCase] = field(default_factory=list)
    config: Optional[Config] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class LayoutLens:
    """Enhanced LayoutLens class with comprehensive testing capabilities.
    
    This class provides a user-friendly API for UI testing with features like:
    - Simple page testing with automatic query generation
    - Regression testing between page versions  
    - Test suite management and execution
    - Multi-viewport testing
    - Integration with CI/CD pipelines
    
    Examples
    --------
    Basic usage:
    
    >>> tester = LayoutLens()
    >>> result = tester.test_page("page.html", queries=["Is the layout responsive?"])
    
    Regression testing:
    
    >>> tester.compare_pages("before.html", "after.html")
    
    Test suite execution:
    
    >>> tester.run_test_suite("config.yaml")
    """
    
    def __init__(
        self,
        config: Optional[Union[str, Config]] = None,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        output_dir: str = "layoutlens_output"
    ):
        """Initialize LayoutLens testing framework.
        
        Parameters
        ----------
        config : str or Config, optional
            Configuration file path or Config instance
        api_key : str, optional
            OpenAI API key (can also use OPENAI_API_KEY env var)
        model : str
            OpenAI model to use for testing
        output_dir : str
            Base directory for test outputs
        """
        # Load configuration
        if isinstance(config, str):
            self.config = Config(config)
        elif isinstance(config, Config):
            self.config = config
        else:
            self.config = Config()
        
        # Override config with provided parameters
        if api_key:
            self.config.llm.api_key = api_key
        if model != "gpt-4o-mini":
            self.config.llm.model = model
        if output_dir != "layoutlens_output":
            self.config.output.base_dir = output_dir
        
        # Validate configuration
        errors = self.config.validate()
        if errors:
            print("Configuration warnings:")
            for error in errors:
                print(f"  - {error}")
        
        # Initialize testing components
        self.page_tester = None
        self.benchmark_generator = None
        
        self._initialize_components()
    
    def _initialize_components(self) -> None:
        """Initialize testing components."""
        if PageTester:
            try:
                self.page_tester = PageTester(
                    screenshot_dir=str(self.config.get_output_path("screenshots")),
                    results_dir=str(self.config.get_output_path("results")),
                    openai_api_key=self.config.llm.api_key,
                    model=self.config.llm.model
                )
            except Exception as e:
                print(f"Warning: Could not initialize PageTester: {e}")
        
        if BenchmarkGenerator:
            try:
                self.benchmark_generator = BenchmarkGenerator(
                    output_dir=str(self.config.get_output_path("benchmarks"))
                )
            except Exception as e:
                print(f"Warning: Could not initialize BenchmarkGenerator: {e}")
    
    def test_page(
        self,
        html_path: str,
        queries: Optional[List[str]] = None,
        viewports: Optional[List[str]] = None,
        auto_generate_queries: bool = True
    ) -> Optional[PageTestResult]:
        """Test a single HTML page with visual validation.
        
        Parameters
        ----------
        html_path : str
            Path to HTML file to test
        queries : List[str], optional
            Custom test queries to run
        viewports : List[str], optional
            Names of viewports to test (from config)
        auto_generate_queries : bool
            Whether to auto-generate queries from HTML analysis
            
        Returns
        -------
        PageTestResult, optional
            Test results, or None if testing failed
            
        Examples
        --------
        >>> tester = LayoutLens()
        >>> result = tester.test_page(
        ...     "homepage.html",
        ...     queries=["Is the navigation menu visible?", "Is the logo centered?"],
        ...     viewports=["mobile_portrait", "desktop"]
        ... )
        >>> print(f"Success rate: {result.success_rate:.2%}")
        """
        if not self.page_tester:
            print("PageTester not available. Check dependencies.")
            return None
        
        # Convert viewport names to configurations
        viewport_configs = []
        if viewports:
            for viewport_name in viewports:
                viewport = self.config.get_viewport_by_name(viewport_name)
                if viewport:
                    # Convert to ScreenshotManager ViewportConfig
                    from scripts.testing.screenshot_manager import ViewportConfig as SMViewportConfig
                    sm_viewport = SMViewportConfig(
                        name=viewport.name,
                        width=viewport.width,
                        height=viewport.height,
                        device_scale_factor=viewport.device_scale_factor,
                        is_mobile=viewport.is_mobile,
                        has_touch=viewport.has_touch,
                        user_agent=viewport.user_agent
                    )
                    viewport_configs.append(sm_viewport)
                else:
                    print(f"Warning: Unknown viewport '{viewport_name}'")
        
        try:
            result = self.page_tester.test_page(
                html_path=html_path,
                viewports=viewport_configs if viewport_configs else None,
                custom_queries=queries,
                auto_generate_queries=auto_generate_queries
            )
            return result
        except Exception as e:
            print(f"Error testing page {html_path}: {e}")
            return None
    
    def compare_pages(
        self,
        page_a_path: str,
        page_b_path: str,
        viewport: str = "desktop",
        query: str = "Do these two layouts look the same?"
    ) -> Optional[Dict[str, Any]]:
        """Compare two HTML pages visually.
        
        Parameters
        ----------
        page_a_path : str
            Path to first HTML file
        page_b_path : str
            Path to second HTML file
        viewport : str
            Viewport name to use for comparison
        query : str
            Question to ask about the comparison
            
        Returns
        -------
        Dict[str, Any], optional
            Comparison results with screenshots and analysis
            
        Examples
        --------
        >>> tester = LayoutLens()
        >>> result = tester.compare_pages(
        ...     "before_redesign.html", 
        ...     "after_redesign.html",
        ...     query="Are the layouts visually consistent?"
        ... )
        >>> print(result['answer'])
        """
        if not self.page_tester:
            print("PageTester not available. Check dependencies.")
            return None
        
        # Get viewport configuration
        viewport_config = self.config.get_viewport_by_name(viewport)
        if not viewport_config:
            print(f"Unknown viewport: {viewport}")
            return None
        
        # Convert to ScreenshotManager ViewportConfig
        from scripts.testing.screenshot_manager import ViewportConfig as SMViewportConfig
        sm_viewport = SMViewportConfig(
            name=viewport_config.name,
            width=viewport_config.width,
            height=viewport_config.height,
            device_scale_factor=viewport_config.device_scale_factor,
            is_mobile=viewport_config.is_mobile,
            has_touch=viewport_config.has_touch,
            user_agent=viewport_config.user_agent
        )
        
        try:
            result = self.page_tester.compare_pages(
                page_a_path=page_a_path,
                page_b_path=page_b_path,
                viewport=sm_viewport,
                comparison_query=query
            )
            return result
        except Exception as e:
            print(f"Error comparing pages: {e}")
            return None
    
    def run_test_suite(self, test_suite: Union[str, TestSuite]) -> List[PageTestResult]:
        """Run a complete test suite.
        
        Parameters
        ----------
        test_suite : str or TestSuite
            Path to YAML test suite file or TestSuite instance
            
        Returns
        -------
        List[PageTestResult]
            Results for all test cases in the suite
            
        Examples
        --------
        >>> tester = LayoutLens()
        >>> results = tester.run_test_suite("regression_tests.yaml")
        >>> success_rate = sum(r.success_rate for r in results) / len(results)
        >>> print(f"Overall success rate: {success_rate:.2%}")
        """
        if isinstance(test_suite, str):
            # Load test suite from YAML file
            suite = self._load_test_suite(test_suite)
        else:
            suite = test_suite
        
        if not suite:
            print("Could not load test suite")
            return []
        
        results = []
        print(f"Running test suite: {suite.name}")
        print(f"Test cases: {len(suite.test_cases)}")
        
        for i, test_case in enumerate(suite.test_cases):
            print(f"\n[{i+1}/{len(suite.test_cases)}] Running: {test_case.name}")
            
            try:
                result = self.test_page(
                    html_path=test_case.html_path,
                    queries=test_case.queries,
                    viewports=test_case.viewports,
                    auto_generate_queries=len(test_case.queries) == 0
                )
                
                if result:
                    results.append(result)
                    print(f"  Completed: {result.passed_tests}/{result.total_tests} tests passed")
                else:
                    print(f"  Failed to test {test_case.name}")
                    
            except Exception as e:
                print(f"  Error: {e}")
                continue
        
        # Generate summary
        if results:
            total_tests = sum(r.total_tests for r in results)
            total_passed = sum(r.passed_tests for r in results)
            overall_rate = total_passed / total_tests if total_tests > 0 else 0
            
            print(f"\nTest Suite Summary:")
            print(f"  Test cases: {len(results)}/{len(suite.test_cases)}")
            print(f"  Total tests: {total_tests}")
            print(f"  Overall success rate: {overall_rate:.2%}")
        
        return results
    
    def create_test_suite(
        self,
        name: str,
        description: str,
        test_cases: List[Dict[str, Any]],
        save_path: Optional[str] = None
    ) -> TestSuite:
        """Create a new test suite programmatically.
        
        Parameters
        ----------
        name : str
            Test suite name
        description : str
            Test suite description
        test_cases : List[Dict[str, Any]]
            List of test case definitions
        save_path : str, optional
            Path to save the test suite YAML file
            
        Returns
        -------
        TestSuite
            Created test suite instance
            
        Examples
        --------
        >>> tester = LayoutLens()
        >>> suite = tester.create_test_suite(
        ...     name="Homepage Tests",
        ...     description="Test homepage across devices",
        ...     test_cases=[
        ...         {
        ...             "name": "Mobile Homepage",
        ...             "html_path": "homepage.html",
        ...             "queries": ["Is the menu collapsed?"],
        ...             "viewports": ["mobile_portrait"]
        ...         }
        ...     ]
        ... )
        """
        # Convert dict test cases to TestCase objects
        cases = []
        for case_data in test_cases:
            test_case = TestCase(
                name=case_data['name'],
                html_path=case_data['html_path'],
                queries=case_data.get('queries', []),
                viewports=case_data.get('viewports', []),
                expected_results=case_data.get('expected_results', {}),
                metadata=case_data.get('metadata', {})
            )
            cases.append(test_case)
        
        suite = TestSuite(
            name=name,
            description=description,
            test_cases=cases,
            config=self.config
        )
        
        if save_path:
            self._save_test_suite(suite, save_path)
        
        return suite
    
    def generate_benchmark_data(self, output_dir: Optional[str] = None) -> None:
        """Generate comprehensive benchmark test data.
        
        Parameters
        ----------
        output_dir : str, optional
            Directory to save benchmark data (uses config default if not provided)
            
        Examples
        --------
        >>> tester = LayoutLens()
        >>> tester.generate_benchmark_data()
        >>> print("Benchmark data generated successfully")
        """
        if not self.benchmark_generator:
            print("BenchmarkGenerator not available. Check dependencies.")
            return
        
        if output_dir:
            # Create new generator with custom output dir
            if BenchmarkGenerator:
                generator = BenchmarkGenerator(output_dir)
            else:
                print("BenchmarkGenerator not available.")
                return
        else:
            generator = self.benchmark_generator
        
        print("Generating comprehensive benchmark data...")
        suites = generator.generate_all_suites()
        
        for suite in suites:
            csv_path = generator.export_to_csv(suite)
            json_path = generator.export_to_json(suite)
            print(f"Generated {suite.name}: {len(suite.test_cases)} test cases")
        
        print(f"Benchmark data saved to: {generator.output_dir}")
    
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
    
    def _save_test_suite(self, suite: TestSuite, save_path: str) -> None:
        """Save test suite to YAML file."""
        import yaml
        
        data = {
            'name': suite.name,
            'description': suite.description,
            'test_cases': [
                {
                    'name': case.name,
                    'html_path': case.html_path,
                    'queries': case.queries,
                    'viewports': case.viewports,
                    'expected_results': case.expected_results,
                    'metadata': case.metadata
                }
                for case in suite.test_cases
            ],
            'metadata': suite.metadata
        }
        
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, indent=2)
    
    # Backward compatibility with original LayoutLens
    def ask(self, images: List[str], query: str) -> str:
        """Ask a question about images (backward compatibility method).
        
        Parameters
        ----------
        images : List[str]
            List of image file paths
        query : str
            Question to ask about the images
            
        Returns
        -------
        str
            Model response
        """
        if OriginalLayoutLens and self.config.llm.api_key:
            try:
                lens = OriginalLayoutLens(
                    api_key=self.config.llm.api_key,
                    model=self.config.llm.model
                )
                return lens.ask(images, query)
            except Exception as e:
                return f"Error: {str(e)}"
        else:
            return "Error: LayoutLens not available or no API key configured"
    
    def compare_layouts(self, image_a: str, image_b: str) -> str:
        """Compare two layout images (backward compatibility method).
        
        Parameters
        ----------
        image_a : str
            Path to first image
        image_b : str
            Path to second image
            
        Returns
        -------
        str
            Comparison result
        """
        return self.ask([image_a, image_b], "Do these two layouts look the same?")