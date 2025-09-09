# Core API Reference

The core module provides the main `LayoutLens` class and related functionality for AI-powered UI testing.

## LayoutLens Class

The primary interface for performing visual UI tests using natural language queries.

### Constructor

```python
class LayoutLens:
    def __init__(
        self,
        config: Optional[Config] = None,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        screenshot_dir: str = "screenshots",
        results_dir: str = "results",
        parallel: bool = True
    )
```

**Parameters:**
- `config` (Config, optional): Configuration object. If None, loads from default sources.
- `api_key` (str, optional): OpenAI API key. If None, loads from environment or config.
- `model` (str): OpenAI model to use. Default: "gpt-4o-mini"
- `screenshot_dir` (str): Directory for storing screenshots. Default: "screenshots"  
- `results_dir` (str): Directory for storing test results. Default: "results"
- `parallel` (bool): Enable parallel test execution. Default: True

**Example:**
```python
from layoutlens import LayoutLens

# Simple initialization
tester = LayoutLens(api_key="your-api-key")

# With custom configuration
tester = LayoutLens(
    model="gpt-4o",
    screenshot_dir="./test-screenshots",
    results_dir="./test-results",
    parallel=False
)
```

### Methods

#### test_page()

Test a single HTML page with natural language queries.

```python
def test_page(
    self,
    html_path: str,
    queries: Optional[List[str]] = None,
    viewports: Optional[List[Union[str, ViewportConfig]]] = None,
    auto_generate_queries: bool = True,
    screenshot_options: Optional[ScreenshotOptions] = None
) -> PageTestResult
```

**Parameters:**
- `html_path` (str): Path to HTML file to test
- `queries` (List[str], optional): Custom test queries. If None and auto_generate_queries is True, queries will be generated automatically.
- `viewports` (List[str|ViewportConfig], optional): Viewports to test. Default: ["desktop", "mobile_portrait"]
- `auto_generate_queries` (bool): Whether to auto-generate queries from HTML analysis. Default: True
- `screenshot_options` (ScreenshotOptions, optional): Custom screenshot capture options

**Returns:**
- `PageTestResult`: Comprehensive test results including success rate, individual test results, and metadata

**Example:**
```python
# Basic usage with auto-generated queries
result = tester.test_page("homepage.html")

# Custom queries and viewports
result = tester.test_page(
    html_path="product-page.html",
    queries=[
        "Is the product image clearly visible and prominent?",
        "Is the 'Add to Cart' button easily accessible?",
        "Is pricing information clearly displayed?"
    ],
    viewports=["desktop", "tablet_portrait", "mobile_portrait"]
)

print(f"Success rate: {result.success_rate:.2%}")
print(f"Tests passed: {result.passed_tests}/{result.total_tests}")
```

#### compare_pages()

Compare two HTML pages visually to detect differences.

```python
def compare_pages(
    self,
    page_a_path: str,
    page_b_path: str,
    viewport: Union[str, ViewportConfig] = "desktop",
    query: str = "Do these two layouts look the same?"
) -> Dict[str, Any]
```

**Parameters:**
- `page_a_path` (str): Path to first HTML file
- `page_b_path` (str): Path to second HTML file  
- `viewport` (str|ViewportConfig): Viewport for comparison. Default: "desktop"
- `query` (str): Comparison query. Default: "Do these two layouts look the same?"

**Returns:**
- `Dict[str, Any]`: Comparison result with screenshots and LLM analysis

**Example:**
```python
comparison = tester.compare_pages(
    page_a_path="designs/v1/homepage.html",
    page_b_path="designs/v2/homepage.html",
    viewport="desktop",
    query="Are these homepage layouts visually consistent? Are there any significant changes?"
)

print(f"Comparison result: {comparison['answer']}")
print(f"Screenshots: {comparison['screenshot_a']}, {comparison['screenshot_b']}")
```

#### run_test_suite()

Execute a comprehensive test suite from YAML configuration.

```python
def run_test_suite(
    self,
    suite_path_or_object: Union[str, TestSuite],
    parallel: Optional[bool] = None,
    max_workers: Optional[int] = None
) -> TestSuiteResult
```

**Parameters:**
- `suite_path_or_object` (str|TestSuite): Path to YAML test suite file or TestSuite object
- `parallel` (bool, optional): Override parallel execution setting
- `max_workers` (int, optional): Override number of parallel workers

**Returns:**
- `TestSuiteResult`: Complete test suite results with aggregated statistics

**Example:**
```python
# Run test suite from YAML file
results = tester.run_test_suite("ui-test-suite.yaml")

# Run with custom parallelization
results = tester.run_test_suite(
    suite_path="comprehensive-tests.yaml",
    parallel=True,
    max_workers=4
)

print(f"Suite: {results.name}")
print(f"Total test cases: {len(results.test_cases)}")
print(f"Overall success rate: {results.overall_success_rate:.2%}")
```

#### generate_benchmark_data()

Generate systematic benchmark datasets for testing.

```python
def generate_benchmark_data(
    self,
    output_dir: str = "benchmarks",
    categories: Optional[List[str]] = None,
    format: str = "csv"
) -> str
```

**Parameters:**
- `output_dir` (str): Directory for generated benchmark files. Default: "benchmarks"
- `categories` (List[str], optional): Benchmark categories to generate. Default: ["typography", "layout", "color", "accessibility"]
- `format` (str): Output format ("csv", "yaml", "json"). Default: "csv"

**Returns:**
- `str`: Path to generated benchmark directory

**Example:**
```python
# Generate comprehensive benchmarks
benchmark_path = tester.generate_benchmark_data(
    output_dir="./test-benchmarks",
    categories=["typography", "layout", "accessibility"],
    format="csv"
)

print(f"Benchmarks generated in: {benchmark_path}")
```

#### ask() - Legacy Compatibility

Direct question interface for backward compatibility with original framework.

```python
def ask(
    self,
    images: List[str],
    query: str,
    model: Optional[str] = None
) -> str
```

**Parameters:**
- `images` (List[str]): List of image file paths
- `query` (str): Natural language question
- `model` (str, optional): Override default model

**Returns:**
- `str`: AI response to the query

**Note:** This method is maintained for backward compatibility. New code should use `test_page()` or `compare_pages()`.

**Example:**
```python
# Legacy compatibility usage
answer = tester.ask(
    images=["screenshot1.png", "screenshot2.png"],
    query="Do these layouts look the same?"
)
print(f"AI Response: {answer}")
```

#### compare_layouts() - Legacy Compatibility

Compare two layouts using the original interface.

```python
def compare_layouts(
    self,
    image_a: str,
    image_b: str,
    query: str = "Do these two layouts look the same?"
) -> str
```

**Parameters:**
- `image_a` (str): Path to first image
- `image_b` (str): Path to second image
- `query` (str): Comparison query

**Returns:**
- `str`: AI comparison result

**Example:**
```python
# Legacy comparison
result = tester.compare_layouts(
    image_a="layout_v1.png",
    image_b="layout_v2.png",
    query="Are these layouts visually consistent?"
)
print(result)
```

## Data Classes

### PageTestResult

Result of testing a single HTML page.

```python
@dataclass
class PageTestResult:
    html_path: str
    timestamp: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    test_results: List[TestResult]
    screenshots: List[ScreenshotResult]
    metadata: Dict[str, Any]
    execution_time: float
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate of tests."""
```

**Attributes:**
- `html_path`: Path to the tested HTML file
- `timestamp`: Test execution timestamp
- `total_tests`: Total number of tests executed
- `passed_tests`: Number of tests that passed
- `failed_tests`: Number of tests that failed
- `test_results`: List of individual test results
- `screenshots`: List of captured screenshots
- `metadata`: Additional test metadata
- `execution_time`: Total execution time in seconds
- `success_rate`: Calculated success rate (0.0 to 1.0)

### TestResult

Result of a single visual test query.

```python
@dataclass
class TestResult:
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
    
    @property
    def passed(self) -> bool:
        """Determine if test passed based on answer."""
```

**Attributes:**
- `query`: The test query that was asked
- `answer`: AI response to the query
- `confidence`: Confidence level of the query generation (0.0 to 1.0)
- `element_id`: DOM element ID if query targets specific element
- `element_selector`: CSS selector if query targets specific element
- `category`: Query category (layout, typography, accessibility, etc.)
- `screenshot_path`: Path to associated screenshot
- `viewport`: Viewport name used for this test
- `metadata`: Additional test metadata
- `execution_time`: Time taken to execute this test
- `passed`: Whether the test passed (derived from answer)

### TestSuite

Configuration for organizing multiple test cases.

```python
@dataclass
class TestSuite:
    name: str
    description: str = ""
    version: str = "1.0"
    test_cases: List[TestCase] = field(default_factory=list)
    defaults: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_test_case(self, test_case: TestCase) -> None:
        """Add a test case to the suite."""
    
    @classmethod
    def from_yaml(cls, yaml_path: str) -> 'TestSuite':
        """Load test suite from YAML file."""
```

**Attributes:**
- `name`: Suite name
- `description`: Suite description
- `version`: Suite version
- `test_cases`: List of test cases in the suite
- `defaults`: Default settings for all test cases
- `metadata`: Additional suite metadata

### TestCase

Individual test case configuration.

```python
@dataclass
class TestCase:
    name: str
    html_path: str
    queries: List[str] = field(default_factory=list)
    viewports: List[str] = field(default_factory=list)
    expected_results: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
```

**Attributes:**
- `name`: Test case name
- `html_path`: Path to HTML file to test
- `queries`: List of test queries
- `viewports`: List of viewport names to test
- `expected_results`: Expected results for validation
- `metadata`: Additional test case metadata
- `tags`: Tags for organizing and filtering tests

### TestSuiteResult

Complete results from running a test suite.

```python
@dataclass
class TestSuiteResult:
    name: str
    description: str
    timestamp: str
    test_cases: List[TestCaseResult]
    total_test_cases: int
    passed_test_cases: int
    failed_test_cases: int
    total_tests: int
    passed_tests: int
    failed_tests: int
    execution_time: float
    metadata: Dict[str, Any]
    
    @property
    def overall_success_rate(self) -> float:
        """Calculate overall success rate across all tests."""
    
    @property
    def test_case_success_rate(self) -> float:
        """Calculate success rate at test case level."""
```

## Exceptions

### LayoutLensError

Base exception class for LayoutLens errors.

```python
class LayoutLensError(Exception):
    """Base exception for LayoutLens errors."""
    pass
```

### ConfigurationError

Raised when configuration is invalid or missing.

```python
class ConfigurationError(LayoutLensError):
    """Raised when configuration is invalid."""
    pass
```

### APIError

Raised when AI API calls fail.

```python
class APIError(LayoutLensError):
    """Raised when AI API calls fail."""
    pass
```

### ScreenshotError

Raised when screenshot capture fails.

```python
class ScreenshotError(LayoutLensError):
    """Raised when screenshot capture fails."""
    pass
```

## Usage Examples

### Basic Testing Workflow

```python
from layoutlens import LayoutLens, Config

# Initialize with configuration
config = Config()
config.llm.api_key = "your-api-key"
config.llm.model = "gpt-4o-mini"
config.screenshots.format = "png"

tester = LayoutLens(config=config)

# Test single page
result = tester.test_page(
    "homepage.html",
    queries=["Is the navigation clearly visible?", "Is the layout responsive?"]
)

# Check results
if result.success_rate >= 0.8:
    print("✓ Page tests passed")
else:
    print("✗ Page tests failed")
    for test in result.test_results:
        if not test.passed:
            print(f"  Failed: {test.query}")
            print(f"  Answer: {test.answer}")
```

### Advanced Test Suite

```python
from layoutlens import LayoutLens, TestSuite, TestCase

# Create test suite programmatically
suite = TestSuite(
    name="E-commerce Site Tests",
    description="Comprehensive UI testing for online store"
)

# Add test cases
suite.add_test_case(TestCase(
    name="Homepage Desktop",
    html_path="pages/homepage.html",
    queries=[
        "Is the hero section visually striking?",
        "Are product categories clearly organized?",
        "Is the search functionality prominent?"
    ],
    viewports=["desktop"],
    tags=["homepage", "desktop"]
))

suite.add_test_case(TestCase(
    name="Product Page Mobile",
    html_path="pages/product.html", 
    queries=[
        "Are product images clearly visible on mobile?",
        "Is the 'Add to Cart' button easily accessible?",
        "Is pricing information prominent?"
    ],
    viewports=["mobile_portrait"],
    tags=["product", "mobile"]
))

# Run suite
tester = LayoutLens()
results = tester.run_test_suite(suite)

# Analyze results
print(f"Suite Results: {results.overall_success_rate:.1%} success rate")
for test_case_result in results.test_cases:
    print(f"  {test_case_result.name}: {test_case_result.success_rate:.1%}")
```

### Error Handling

```python
from layoutlens import LayoutLens, APIError, ScreenshotError, ConfigurationError

tester = LayoutLens()

try:
    result = tester.test_page("complex-page.html")
    print(f"Success rate: {result.success_rate:.2%}")
    
except APIError as e:
    print(f"AI API error: {e}")
    # Handle API issues (rate limiting, network, etc.)
    
except ScreenshotError as e:
    print(f"Screenshot error: {e}")
    # Handle browser/rendering issues
    
except ConfigurationError as e:
    print(f"Configuration error: {e}")
    # Handle missing API keys, invalid settings, etc.
    
except Exception as e:
    print(f"Unexpected error: {e}")
    # Handle other issues
```

## See Also

- [Configuration API](config.md) - Configuration management
- [Test Runner API](test-runner.md) - Test execution engine
- [CLI API](cli.md) - Command-line interface
- [User Guide](../user-guide/quickstart.md) - Getting started tutorial