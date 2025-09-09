# Development Setup Guide

This guide helps contributors set up a development environment for LayoutLens and understand the development workflow.

## Quick Setup

### Prerequisites

1. **Python 3.8+** (3.9+ recommended)
2. **Git** for version control
3. **Make** (optional, for convenience commands)
4. **OpenAI API Key** for testing (optional but recommended)

### Clone and Setup

```bash
# Clone repository
git clone https://github.com/matmulai/layoutlens.git
cd layoutlens

# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode with all dependencies
make dev-setup
# Or manually:
pip install -e .
pip install pytest pytest-cov pytest-mock playwright beautifulsoup4 pyyaml
playwright install chromium
```

### Verify Setup

```bash
# Run tests to verify everything works
make test
# Or: pytest tests/ -v

# Check code formatting
make format
make lint

# Test CLI
layoutlens --help
```

## Project Structure

Understanding the codebase organization:

```
layoutlens/
├── layoutlens/              # Main package
│   ├── __init__.py         # Package exports
│   ├── core.py             # Enhanced LayoutLens class
│   ├── config.py           # Configuration management
│   ├── test_runner.py      # Test execution engine
│   └── cli.py              # Command-line interface
│
├── scripts/                # Testing and benchmark tools
│   ├── testing/            # Page testing orchestration
│   │   ├── page_tester.py  # Main testing orchestrator
│   │   ├── screenshot_manager.py  # Screenshot capture
│   │   ├── query_generator.py     # Query generation
│   │   └── __init__.py
│   ├── benchmark/          # Benchmark generation
│   │   ├── benchmark_generator.py
│   │   ├── template_engine.py
│   │   └── __init__.py
│   └── __init__.py
│
├── legacy/                 # Original/legacy components
│   ├── framework.py        # Original LayoutLens
│   ├── screenshot.py       # Basic screenshot utils
│   ├── benchmark_runner.py # Original benchmark runner
│   └── README.md
│
├── tests/                  # Test suite
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   ├── fixtures/           # Test data and samples
│   └── conftest.py         # Pytest configuration
│
├── docs/                   # Documentation
│   ├── user-guide/         # User documentation
│   ├── api/                # API reference
│   ├── developer-guide/    # Developer documentation
│   └── README.md
│
├── examples/               # Usage examples
│   ├── basic_usage.py
│   ├── advanced_usage.py
│   └── ci_cd_integration.py
│
├── benchmarks/             # Benchmark datasets
├── .github/               # GitHub Actions workflows
├── pyproject.toml         # Project configuration
├── Makefile              # Development commands
└── README.md
```

## Development Workflow

### 1. Branch Strategy

```bash
# Create feature branch
git checkout -b feature/new-feature-name

# Create bugfix branch
git checkout -b fix/bug-description

# Create documentation branch
git checkout -b docs/documentation-update
```

### 2. Code Style and Standards

LayoutLens follows Python best practices:

- **PEP 8** for code style
- **Type hints** for function parameters and return values
- **Docstrings** for all public functions and classes
- **88 character line limit** (Black formatter standard)

#### Formatting and Linting

```bash
# Format code
make format
# Or manually:
black layoutlens/ scripts/ tests/ examples/
isort layoutlens/ scripts/ tests/ examples/

# Lint code
make lint
# Or manually:
flake8 layoutlens/ scripts/ tests/
mypy layoutlens/ --ignore-missing-imports
```

#### Pre-commit Setup

```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run pre-commit manually
pre-commit run --all-files
```

### 3. Testing

Comprehensive testing is required for all changes:

```bash
# Run all tests
make test

# Run specific test categories
make test-unit          # Unit tests only
make test-integration   # Integration tests only
make test-fast          # Skip slow tests

# Run with coverage
make test-coverage

# Run tests in parallel
make test-parallel
```

#### Writing Tests

Follow these patterns for new tests:

**Unit Test Example:**
```python
import pytest
from unittest.mock import Mock, patch
from layoutlens.config import Config

@pytest.mark.unit
class TestConfig:
    def test_default_values(self):
        """Test configuration default values."""
        config = Config()
        assert config.llm.model == "gpt-4o-mini"
        assert config.testing.parallel is True
    
    @patch('layoutlens.config.os.environ.get')
    def test_environment_loading(self, mock_env):
        """Test configuration from environment variables."""
        mock_env.return_value = "custom-model"
        
        config = Config()
        config._load_from_env()
        
        assert config.llm.model == "custom-model"
```

**Integration Test Example:**
```python
import pytest
from unittest.mock import patch, Mock
from layoutlens import LayoutLens

@pytest.mark.integration
class TestLayoutLensIntegration:
    @patch('layoutlens.core.PageTester')
    def test_page_testing_workflow(self, mock_page_tester_class, sample_html_file):
        """Test complete page testing workflow."""
        # Setup mocks
        mock_tester = Mock()
        mock_page_tester_class.return_value = mock_tester
        
        mock_result = Mock()
        mock_result.success_rate = 0.9
        mock_tester.test_page.return_value = mock_result
        
        # Test
        layoutlens = LayoutLens()
        result = layoutlens.test_page(sample_html_file)
        
        # Verify
        assert result.success_rate == 0.9
        mock_tester.test_page.assert_called_once()
```

### 4. Documentation

Documentation is required for all new features:

#### Code Documentation

```python
def test_page(
    self,
    html_path: str,
    queries: Optional[List[str]] = None,
    viewports: Optional[List[str]] = None,
    auto_generate_queries: bool = True
) -> PageTestResult:
    """Test a single HTML page with natural language queries.
    
    This method captures screenshots of the page across different viewports
    and uses AI to analyze the visual layout based on natural language queries.
    
    Parameters
    ----------
    html_path : str
        Path to the HTML file to test
    queries : List[str], optional
        Custom test queries. If None and auto_generate_queries is True,
        queries will be generated automatically from HTML analysis.
    viewports : List[str], optional
        Viewport names to test across. Uses default viewports if None.
    auto_generate_queries : bool
        Whether to auto-generate queries from HTML analysis
        
    Returns
    -------
    PageTestResult
        Complete test results including success rate, individual test
        results, screenshots, and execution metadata
        
    Raises
    ------
    FileNotFoundError
        If the HTML file doesn't exist
    APIError
        If the AI API is unavailable or returns an error
    ScreenshotError
        If screenshot capture fails
        
    Examples
    --------
    >>> from layoutlens import LayoutLens
    >>> tester = LayoutLens()
    >>> result = tester.test_page("homepage.html")
    >>> print(f"Success rate: {result.success_rate:.2%}")
    
    >>> # Custom queries and viewports
    >>> result = tester.test_page(
    ...     "product.html",
    ...     queries=["Is the product image prominent?"],
    ...     viewports=["desktop", "mobile_portrait"]
    ... )
    """
```

#### User Documentation

Update relevant documentation files when adding features:
- User guides in `docs/user-guide/`
- API documentation in `docs/api/`
- Examples in `examples/`

### 5. Commit Guidelines

Use conventional commit format:

```bash
# Feature commits
git commit -m "feat: add multi-viewport screenshot capture"
git commit -m "feat(cli): add --parallel option to test command"

# Bug fix commits
git commit -m "fix: resolve API timeout issues"
git commit -m "fix(config): handle missing environment variables"

# Documentation commits
git commit -m "docs: add API reference for test runner"
git commit -m "docs(user-guide): update installation instructions"

# Test commits
git commit -m "test: add integration tests for page comparison"

# Refactor commits
git commit -m "refactor: simplify configuration loading logic"

# Build/CI commits
git commit -m "ci: add Python 3.12 to test matrix"
git commit -m "build: update dependencies"
```

## Architecture Guidelines

### Design Principles

1. **Modularity**: Keep components loosely coupled with clear interfaces
2. **Testability**: Design for easy testing with dependency injection
3. **Extensibility**: Allow easy extension through configuration and plugins
4. **Performance**: Efficient resource usage and parallel processing
5. **Reliability**: Graceful error handling and recovery

### Adding New Features

#### 1. Plan the Feature

- Create or update GitHub issue
- Design API interface
- Consider backward compatibility
- Plan testing strategy

#### 2. Implement Core Logic

```python
# Example: Adding new viewport preset
from layoutlens.config import ViewportConfig, VIEWPORT_PRESETS

def add_viewport_preset(name: str, width: int, height: int, **kwargs):
    """Add a new viewport preset to the global configuration."""
    viewport = ViewportConfig(
        name=name,
        width=width,
        height=height,
        **kwargs
    )
    VIEWPORT_PRESETS[name] = viewport
    return viewport

# Add to configuration system
class Config:
    def add_custom_viewport(self, name: str, viewport: ViewportConfig):
        """Add custom viewport to configuration."""
        self.viewports[name] = viewport
```

#### 3. Add Configuration Support

```python
# Update configuration schema
@dataclass
class CustomFeatureConfig:
    enabled: bool = True
    option_a: str = "default"
    option_b: int = 42

# Add to main Config class
@dataclass 
class Config:
    # ... existing fields
    custom_feature: CustomFeatureConfig = field(default_factory=CustomFeatureConfig)
```

#### 4. Add CLI Support

```python
# Add CLI command or options
class TestCommand(BaseCommand):
    def add_arguments(self, parser):
        # ... existing arguments
        parser.add_argument(
            "--new-option",
            help="Description of new option",
            default="default_value"
        )
    
    def execute(self, args):
        # Use the new option
        if args.new_option:
            # Implementation
            pass
```

#### 5. Add Comprehensive Tests

```python
# Unit tests
@pytest.mark.unit
class TestNewFeature:
    def test_new_feature_default_behavior(self):
        """Test new feature with default configuration."""
        pass
    
    def test_new_feature_custom_config(self):
        """Test new feature with custom configuration."""
        pass
    
    def test_new_feature_error_handling(self):
        """Test new feature error handling."""
        pass

# Integration tests
@pytest.mark.integration
class TestNewFeatureIntegration:
    def test_new_feature_with_existing_functionality(self):
        """Test new feature integration with existing code."""
        pass
```

#### 6. Update Documentation

- Add to API documentation
- Update user guides
- Create examples
- Update CLI reference

### Code Organization Patterns

#### Service Classes

```python
class SomeService:
    """Service class following dependency injection pattern."""
    
    def __init__(self, config: Config, dependency: SomeDependency):
        self.config = config
        self.dependency = dependency
    
    def perform_action(self, input_data: Any) -> Any:
        """Perform service action with proper error handling."""
        try:
            result = self._internal_logic(input_data)
            return self._process_result(result)
        except SomeSpecificError as e:
            self._handle_specific_error(e)
            raise
        except Exception as e:
            self._handle_general_error(e)
            raise ServiceError(f"Action failed: {e}") from e
```

#### Configuration Pattern

```python
@dataclass
class FeatureConfig:
    """Configuration for a specific feature."""
    enabled: bool = True
    timeout: int = 30
    retries: int = 3
    
    def validate(self) -> None:
        """Validate configuration values."""
        if self.timeout <= 0:
            raise ConfigurationError("Timeout must be positive")
        if self.retries < 0:
            raise ConfigurationError("Retries must be non-negative")

class Feature:
    """Feature implementation using configuration."""
    
    def __init__(self, config: FeatureConfig):
        config.validate()
        self.config = config
```

#### Error Handling Pattern

```python
class FeatureError(LayoutLensError):
    """Base exception for feature-related errors."""
    pass

class FeatureConfigurationError(FeatureError):
    """Configuration error for feature."""
    pass

class FeatureExecutionError(FeatureError):
    """Execution error for feature."""
    pass

def feature_function(input_data):
    """Function with proper error handling."""
    if not input_data:
        raise FeatureConfigurationError("Input data is required")
    
    try:
        result = process_data(input_data)
        return result
    except ExternalAPIError as e:
        raise FeatureExecutionError(f"External API failed: {e}") from e
    except Exception as e:
        raise FeatureError(f"Unexpected error: {e}") from e
```

## Debugging and Troubleshooting

### Development Debugging

#### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

from layoutlens import LayoutLens
tester = LayoutLens()
```

#### Debug Configuration

```bash
# Debug configuration loading
LAYOUTLENS_LOGGING_LEVEL=DEBUG layoutlens info --config

# Debug specific features
LAYOUTLENS_SCREENSHOTS_WAIT_FOR_LOAD=10 layoutlens test --page test.html --verbose
```

### Common Development Issues

#### 1. Import Errors

```python
# Check Python path
import sys
print(sys.path)

# Install in development mode
pip install -e .
```

#### 2. Test Failures

```bash
# Run specific test with verbose output
pytest tests/unit/test_specific.py::test_function -v -s

# Debug test with PDB
pytest tests/unit/test_specific.py::test_function --pdb

# Run test with coverage
pytest tests/unit/test_specific.py --cov=layoutlens
```

#### 3. API Issues During Development

```python
# Mock API calls in development
from unittest.mock import patch

@patch('layoutlens.core.OpenAI')
def test_without_api(mock_openai):
    mock_client = Mock()
    mock_openai.return_value = mock_client
    # Test implementation
```

#### 4. Browser/Screenshot Issues

```bash
# Reinstall Playwright
playwright uninstall
playwright install chromium --force

# Check browser installation
playwright --version
playwright install-deps  # On Linux
```

### Performance Profiling

#### Profile Test Execution

```python
import cProfile
import pstats
from layoutlens import LayoutLens

def profile_test():
    tester = LayoutLens()
    result = tester.test_page("complex-page.html")
    return result

# Profile execution
pr = cProfile.Profile()
pr.enable()
result = profile_test()
pr.disable()

# Analyze results
stats = pstats.Stats(pr)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20 functions
```

#### Memory Usage Monitoring

```python
import tracemalloc
import psutil
import os

def monitor_memory_usage():
    tracemalloc.start()
    process = psutil.Process(os.getpid())
    
    initial_memory = process.memory_info().rss
    print(f"Initial memory: {initial_memory / 1024 / 1024:.1f} MB")
    
    # Your code here
    tester = LayoutLens()
    result = tester.test_page("large-page.html")
    
    current, peak = tracemalloc.get_traced_memory()
    final_memory = process.memory_info().rss
    
    print(f"Final memory: {final_memory / 1024 / 1024:.1f} MB")
    print(f"Memory increase: {(final_memory - initial_memory) / 1024 / 1024:.1f} MB")
    print(f"Traced current: {current / 1024 / 1024:.1f} MB")
    print(f"Traced peak: {peak / 1024 / 1024:.1f} MB")
    
    tracemalloc.stop()

monitor_memory_usage()
```

## Release Process

### Preparing a Release

1. **Update Version Numbers**

```bash
# Update version in pyproject.toml
version = "1.1.0"

# Update version in layoutlens/__init__.py
__version__ = "1.1.0"
```

2. **Update CHANGELOG.md**

```markdown
## [1.1.0] - 2024-01-15

### Added
- New feature A with comprehensive testing
- Enhanced configuration options for feature B

### Changed
- Improved performance of screenshot capture by 25%
- Updated dependency versions

### Fixed
- Fixed bug in error handling for API timeouts
- Resolved issue with viewport configuration loading
```

3. **Run Complete Test Suite**

```bash
make release-check
# Or manually:
make clean
make install-dev
make test-coverage
make lint
make check-package
```

4. **Build and Test Package**

```bash
make build
make check-package

# Test installation in clean environment
pip install dist/*.whl
python -c "import layoutlens; print(layoutlens.__version__)"
```

5. **Create Release**

```bash
git add .
git commit -m "release: v1.1.0"
git tag v1.1.0
git push origin main --tags
```

### CI/CD Integration

GitHub Actions automatically handles:
- Running tests across multiple Python versions
- Building and publishing to PyPI
- Creating GitHub releases

Monitor the release process in GitHub Actions.

## Getting Help

### Development Questions

1. **Check existing documentation** in `docs/developer-guide/`
2. **Review similar implementations** in the codebase
3. **Look at test examples** in `tests/` directory
4. **Check GitHub issues** for similar problems
5. **Ask in GitHub Discussions** for design questions

### Code Review Process

1. **Self-review** your changes thoroughly
2. **Run all tests and checks** locally
3. **Update documentation** as needed
4. **Create descriptive pull request** with context
5. **Address review feedback** promptly

### Useful Development Resources

- [Python Type Hints](https://docs.python.org/3/library/typing.html)
- [pytest Documentation](https://docs.pytest.org/)
- [Playwright Documentation](https://playwright.dev/python/)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [YAML Specification](https://yaml.org/spec/1.2/spec.html)

Remember: Good code is not just working code, but code that is maintainable, testable, and understandable by other developers.