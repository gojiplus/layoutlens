# Test Runner API Reference

The test runner module provides the engine for executing comprehensive test suites with parallel processing, result aggregation, and flexible reporting.

## TestRunner Class

The main test execution engine that orchestrates test suite execution.

### Constructor

```python
class TestRunner:
    def __init__(
        self,
        config: Optional[Config] = None,
        layoutlens: Optional[LayoutLens] = None
    )
```

**Parameters:**
- `config` (Config, optional): Configuration object. If None, loads default configuration.
- `layoutlens` (LayoutLens, optional): LayoutLens instance to use. If None, creates one from config.

**Example:**
```python
from layoutlens import TestRunner, Config

# Simple initialization
runner = TestRunner()

# With custom configuration
config = Config.from_file("test-config.yaml")
runner = TestRunner(config=config)
```

### Methods

#### run_suite()

Execute a complete test suite with parallel processing and result aggregation.

```python
def run_suite(
    self,
    suite: Union[str, TestSuite],
    parallel: Optional[bool] = None,
    max_workers: Optional[int] = None,
    tags: Optional[List[str]] = None
) -> TestSuiteResult
```

**Parameters:**
- `suite` (str|TestSuite): Path to YAML test suite file or TestSuite object
- `parallel` (bool, optional): Override parallel execution setting
- `max_workers` (int, optional): Override number of parallel workers
- `tags` (List[str], optional): Run only test cases with these tags

**Returns:**
- `TestSuiteResult`: Complete test suite results with aggregated statistics

**Example:**
```python
# Run complete test suite
results = runner.run_suite("ui-test-suite.yaml")

# Run with specific tags
results = runner.run_suite(
    suite="comprehensive-tests.yaml",
    tags=["mobile", "accessibility"]
)

# Custom parallelization
results = runner.run_suite(
    suite="large-test-suite.yaml",
    parallel=True,
    max_workers=8
)

print(f"Suite: {results.name}")
print(f"Success rate: {results.overall_success_rate:.2%}")
```

#### run_test_case()

Execute a single test case.

```python
def run_test_case(
    self,
    test_case: TestCase,
    suite_defaults: Optional[Dict[str, Any]] = None
) -> TestCaseResult
```

**Parameters:**
- `test_case` (TestCase): Test case to execute
- `suite_defaults` (Dict, optional): Default settings from test suite

**Returns:**
- `TestCaseResult`: Results for the individual test case

**Example:**
```python
from layoutlens import TestCase

test_case = TestCase(
    name="Homepage Test",
    html_path="pages/homepage.html",
    queries=["Is the navigation clearly visible?"],
    viewports=["desktop", "mobile_portrait"]
)

result = runner.run_test_case(test_case)
print(f"Test case success rate: {result.success_rate:.2%}")
```

#### run_multiple_test_cases()

Execute multiple test cases with parallel processing.

```python
def run_multiple_test_cases(
    self,
    test_cases: List[TestCase],
    parallel: bool = True,
    max_workers: Optional[int] = None
) -> List[TestCaseResult]
```

**Parameters:**
- `test_cases` (List[TestCase]): List of test cases to execute
- `parallel` (bool): Enable parallel execution
- `max_workers` (int, optional): Number of parallel workers

**Returns:**
- `List[TestCaseResult]`: Results for all test cases

**Example:**
```python
test_cases = [
    TestCase(name="Homepage", html_path="home.html"),
    TestCase(name="About", html_path="about.html"),
    TestCase(name="Contact", html_path="contact.html")
]

results = runner.run_multiple_test_cases(
    test_cases=test_cases,
    parallel=True,
    max_workers=4
)

for result in results:
    print(f"{result.name}: {result.success_rate:.2%}")
```

#### validate_suite()

Validate a test suite configuration without executing tests.

```python
def validate_suite(
    self,
    suite: Union[str, TestSuite]
) -> Dict[str, Any]
```

**Parameters:**
- `suite` (str|TestSuite): Test suite to validate

**Returns:**
- `Dict[str, Any]`: Validation results with errors and warnings

**Example:**
```python
validation = runner.validate_suite("test-suite.yaml")

if validation["valid"]:
    print("Test suite is valid")
else:
    print("Validation errors:")
    for error in validation["errors"]:
        print(f"  - {error}")
    
    print("Warnings:")
    for warning in validation["warnings"]:
        print(f"  - {warning}")
```

#### generate_report()

Generate formatted reports from test results.

```python
def generate_report(
    self,
    results: TestSuiteResult,
    output_dir: str = "reports",
    formats: List[str] = ["html", "json"]
) -> Dict[str, str]
```

**Parameters:**
- `results` (TestSuiteResult): Test suite results to report on
- `output_dir` (str): Directory for generated reports
- `formats` (List[str]): Report formats to generate

**Returns:**
- `Dict[str, str]`: Mapping of format to generated file path

**Example:**
```python
results = runner.run_suite("ui-tests.yaml")

report_files = runner.generate_report(
    results=results,
    output_dir="./test-reports",
    formats=["html", "json", "junit"]
)

for format, file_path in report_files.items():
    print(f"{format.upper()} report: {file_path}")
```

## Data Classes

### TestCaseResult

Results from executing a single test case.

```python
@dataclass
class TestCaseResult:
    name: str
    html_path: str
    timestamp: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    test_results: List[TestResult]
    screenshots: List[ScreenshotResult]
    execution_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate for this test case."""
    
    @property
    def passed(self) -> bool:
        """Whether this test case passed overall."""
```

**Attributes:**
- `name`: Test case name
- `html_path`: Path to tested HTML file
- `timestamp`: Execution timestamp
- `total_tests`: Total number of individual tests
- `passed_tests`: Number of tests that passed
- `failed_tests`: Number of tests that failed
- `test_results`: Individual test results
- `screenshots`: Captured screenshots
- `execution_time`: Execution time in seconds
- `metadata`: Additional test case metadata
- `success_rate`: Calculated success rate (0.0 to 1.0)
- `passed`: Whether test case passed based on threshold

### TestSuiteResult

Aggregated results from a complete test suite execution.

```python
@dataclass
class TestSuiteResult:
    name: str
    description: str
    version: str
    timestamp: str
    test_cases: List[TestCaseResult]
    total_test_cases: int
    passed_test_cases: int
    failed_test_cases: int
    total_tests: int
    passed_tests: int
    failed_tests: int
    execution_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def overall_success_rate(self) -> float:
        """Calculate overall success rate across all tests."""
    
    @property
    def test_case_success_rate(self) -> float:
        """Calculate success rate at test case level."""
```

**Attributes:**
- `name`: Test suite name
- `description`: Test suite description
- `version`: Test suite version
- `timestamp`: Execution timestamp
- `test_cases`: Results for individual test cases
- `total_test_cases`: Total number of test cases
- `passed_test_cases`: Number of test cases that passed
- `failed_test_cases`: Number of test cases that failed
- `total_tests`: Total number of individual tests across all cases
- `passed_tests`: Total number of individual tests that passed
- `failed_tests`: Total number of individual tests that failed
- `execution_time`: Total execution time in seconds
- `metadata`: Additional suite metadata
- `overall_success_rate`: Success rate across all individual tests
- `test_case_success_rate`: Success rate at test case level

### ExecutionContext

Context information for test execution.

```python
@dataclass
class ExecutionContext:
    parallel: bool
    max_workers: int
    start_time: float
    tags: List[str]
    config: Config
    metadata: Dict[str, Any] = field(default_factory=dict)
```

**Attributes:**
- `parallel`: Whether parallel execution is enabled
- `max_workers`: Number of parallel workers
- `start_time`: Execution start time
- `tags`: Tags filter for test execution
- `config`: Configuration used for execution
- `metadata`: Additional execution metadata

## Advanced Features

### Parallel Execution

The test runner automatically handles parallel execution of test cases:

```python
# Configure parallel execution
runner = TestRunner()
runner.config.testing.parallel = True
runner.config.testing.max_workers = 6

# Run suite with parallelization
results = runner.run_suite("large-test-suite.yaml")

# Check execution performance
print(f"Executed {results.total_test_cases} test cases in {results.execution_time:.1f}s")
print(f"Average time per test case: {results.execution_time / results.total_test_cases:.1f}s")
```

### Progress Monitoring

Monitor test execution progress with callbacks:

```python
class ProgressMonitor:
    def __init__(self):
        self.completed = 0
        self.total = 0
    
    def on_suite_start(self, context: ExecutionContext, total_cases: int):
        self.total = total_cases
        print(f"Starting test suite with {total_cases} test cases")
    
    def on_test_case_complete(self, result: TestCaseResult):
        self.completed += 1
        progress = (self.completed / self.total) * 100
        print(f"[{progress:.1f}%] Completed: {result.name} ({result.success_rate:.1%})")
    
    def on_suite_complete(self, results: TestSuiteResult):
        print(f"Suite completed: {results.overall_success_rate:.1%} success rate")

# Use progress monitoring
monitor = ProgressMonitor()
runner = TestRunner()
runner.add_progress_callback(monitor)

results = runner.run_suite("comprehensive-tests.yaml")
```

### Error Handling and Recovery

Robust error handling with recovery strategies:

```python
from layoutlens import TestRunner, APIError, ScreenshotError

class RobustTestRunner:
    def __init__(self, config=None):
        self.runner = TestRunner(config=config)
        self.retry_count = 0
        self.max_retries = 3
    
    def run_suite_with_recovery(self, suite_path: str) -> TestSuiteResult:
        """Run test suite with error recovery."""
        attempt = 0
        
        while attempt < self.max_retries:
            try:
                results = self.runner.run_suite(suite_path)
                
                # Check if we need to retry failed tests
                if results.failed_test_cases > 0 and attempt < self.max_retries - 1:
                    failed_cases = [tc for tc in results.test_cases if not tc.passed]
                    print(f"Retrying {len(failed_cases)} failed test cases")
                    
                    # Retry failed cases
                    retry_results = self.runner.run_multiple_test_cases(
                        test_cases=[self._test_case_from_result(tc) for tc in failed_cases]
                    )
                    
                    # Merge results
                    results = self._merge_results(results, retry_results)
                
                return results
                
            except APIError as e:
                attempt += 1
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"API error, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    raise
            
            except ScreenshotError as e:
                print(f"Screenshot error: {e}")
                # Continue with reduced functionality
                self.runner.config.screenshots.enabled = False
                
            except Exception as e:
                print(f"Unexpected error: {e}")
                raise
        
        raise RuntimeError(f"Failed to complete test suite after {self.max_retries} attempts")
    
    def _test_case_from_result(self, result: TestCaseResult) -> TestCase:
        """Convert test case result back to test case for retry."""
        # Implementation details...
        pass
    
    def _merge_results(self, original: TestSuiteResult, retry: List[TestCaseResult]) -> TestSuiteResult:
        """Merge original and retry results."""
        # Implementation details...
        pass

# Usage
robust_runner = RobustTestRunner()
results = robust_runner.run_suite_with_recovery("flaky-tests.yaml")
```

### Custom Result Processing

Process and analyze results with custom logic:

```python
class ResultAnalyzer:
    def __init__(self):
        self.failure_patterns = {}
        self.performance_metrics = {}
    
    def analyze_results(self, results: TestSuiteResult) -> Dict[str, Any]:
        """Analyze test results for patterns and insights."""
        analysis = {
            "summary": self._generate_summary(results),
            "failure_analysis": self._analyze_failures(results),
            "performance_analysis": self._analyze_performance(results),
            "recommendations": self._generate_recommendations(results)
        }
        
        return analysis
    
    def _generate_summary(self, results: TestSuiteResult) -> Dict[str, Any]:
        return {
            "total_test_cases": results.total_test_cases,
            "success_rate": results.overall_success_rate,
            "execution_time": results.execution_time,
            "avg_time_per_case": results.execution_time / results.total_test_cases
        }
    
    def _analyze_failures(self, results: TestSuiteResult) -> Dict[str, Any]:
        """Analyze failure patterns."""
        failed_cases = [tc for tc in results.test_cases if not tc.passed]
        
        # Group failures by type
        failure_categories = {}
        for case in failed_cases:
            for test in case.test_results:
                if not test.passed:
                    category = test.category
                    if category not in failure_categories:
                        failure_categories[category] = []
                    failure_categories[category].append(test.query)
        
        return {
            "failed_test_cases": len(failed_cases),
            "failure_categories": failure_categories,
            "common_failures": self._find_common_failures(failed_cases)
        }
    
    def _analyze_performance(self, results: TestSuiteResult) -> Dict[str, Any]:
        """Analyze performance metrics."""
        execution_times = [tc.execution_time for tc in results.test_cases]
        
        return {
            "min_time": min(execution_times),
            "max_time": max(execution_times),
            "avg_time": sum(execution_times) / len(execution_times),
            "total_time": results.execution_time,
            "slowest_cases": sorted(
                results.test_cases,
                key=lambda x: x.execution_time,
                reverse=True
            )[:5]
        }
    
    def _generate_recommendations(self, results: TestSuiteResult) -> List[str]:
        """Generate recommendations based on results."""
        recommendations = []
        
        if results.overall_success_rate < 0.8:
            recommendations.append("Consider reviewing failed test queries for clarity")
        
        if results.execution_time > 300:  # 5 minutes
            recommendations.append("Consider enabling parallel execution to improve performance")
        
        # Add more recommendation logic...
        
        return recommendations

# Usage
runner = TestRunner()
analyzer = ResultAnalyzer()

results = runner.run_suite("comprehensive-tests.yaml")
analysis = analyzer.analyze_results(results)

print("Test Analysis:")
print(f"Success Rate: {analysis['summary']['success_rate']:.2%}")
print(f"Execution Time: {analysis['summary']['execution_time']:.1f}s")
print("\nRecommendations:")
for rec in analysis['recommendations']:
    print(f"  - {rec}")
```

## Integration Examples

### CI/CD Integration

Integration with continuous integration systems:

```python
import sys
from layoutlens import TestRunner, Config

def ci_test_runner(suite_path: str, threshold: float = 0.8) -> int:
    """Run tests in CI environment with exit code handling."""
    try:
        # Configure for CI
        config = Config()
        config.testing.fail_fast = True
        config.testing.parallel = True
        config.output.formats = ["junit", "json"]
        config.output.verbose = False
        
        runner = TestRunner(config=config)
        results = runner.run_suite(suite_path)
        
        # Generate reports for CI
        report_files = runner.generate_report(
            results=results,
            output_dir="test-results",
            formats=["junit", "json"]
        )
        
        print(f"Generated reports: {report_files}")
        
        # Check if tests meet threshold
        if results.overall_success_rate >= threshold:
            print(f"✓ Tests passed: {results.overall_success_rate:.2%} success rate")
            return 0
        else:
            print(f"✗ Tests failed: {results.overall_success_rate:.2%} success rate (threshold: {threshold:.2%})")
            
            # Print failed test details for CI logs
            for test_case in results.test_cases:
                if not test_case.passed:
                    print(f"Failed: {test_case.name}")
                    for test in test_case.test_results:
                        if not test.passed:
                            print(f"  - {test.query}: {test.answer}")
            
            return 1
    
    except Exception as e:
        print(f"Error running tests: {e}")
        return 2

if __name__ == "__main__":
    suite_path = sys.argv[1] if len(sys.argv) > 1 else "ci-tests.yaml"
    threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 0.8
    
    exit_code = ci_test_runner(suite_path, threshold)
    sys.exit(exit_code)
```

### pytest Integration

Use TestRunner within pytest framework:

```python
import pytest
from layoutlens import TestRunner, TestSuite, TestCase

@pytest.fixture(scope="session")
def test_runner():
    """Shared test runner instance."""
    return TestRunner()

@pytest.fixture(scope="session")
def ui_test_suite():
    """UI test suite fixture."""
    suite = TestSuite(
        name="pytest UI Tests",
        description="UI tests for pytest integration"
    )
    
    suite.add_test_case(TestCase(
        name="Homepage",
        html_path="tests/fixtures/homepage.html",
        queries=["Is the navigation visible?"]
    ))
    
    return suite

class TestUIValidation:
    def test_homepage_ui(self, test_runner):
        """Test homepage UI individually."""
        test_case = TestCase(
            name="Homepage Test",
            html_path="tests/fixtures/homepage.html",
            queries=["Is the header properly positioned?"]
        )
        
        result = test_runner.run_test_case(test_case)
        assert result.success_rate >= 0.8, f"Homepage UI test failed: {result.success_rate:.2%}"
    
    def test_ui_suite(self, test_runner, ui_test_suite):
        """Test complete UI suite."""
        results = test_runner.run_suite(ui_test_suite)
        
        assert results.overall_success_rate >= 0.8, (
            f"UI test suite failed: {results.overall_success_rate:.2%} success rate"
        )
        
        # Individual assertions
        assert results.passed_test_cases > 0, "No test cases passed"
        assert results.failed_test_cases == 0, f"{results.failed_test_cases} test cases failed"

    @pytest.mark.slow
    def test_comprehensive_ui(self, test_runner):
        """Test comprehensive UI suite (marked as slow)."""
        results = test_runner.run_suite("tests/comprehensive-ui-tests.yaml")
        assert results.overall_success_rate >= 0.7  # Lower threshold for comprehensive tests
```

## See Also

- [Core API](core.md) - Main LayoutLens class
- [Configuration API](config.md) - Configuration management
- [CLI API](cli.md) - Command-line interface
- [User Guide](../user-guide/quickstart.md) - Getting started guide