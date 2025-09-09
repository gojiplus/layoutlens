# Testing Guide for LayoutLens

This document provides comprehensive information about testing the LayoutLens framework, including running tests, writing new tests, and understanding the testing architecture.

## Quick Start

### Prerequisites

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Install Playwright browsers
playwright install chromium

# Set up environment (optional for most tests)
export OPENAI_API_KEY="your-test-api-key"
```

### Running Tests

```bash
# Run all tests
pytest

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run with coverage reporting
pytest --cov=layoutlens --cov=framework --cov=scripts --cov-report=html

# Run specific test file
pytest tests/unit/test_framework.py

# Run tests matching a pattern
pytest -k "test_screenshot"

# Run tests in parallel
pytest -n auto
```

## Test Structure

### Directory Layout

```
tests/
├── unit/                    # Unit tests
│   ├── test_framework.py    # Original framework tests
│   ├── test_screenshot.py   # Screenshot utility tests
│   ├── test_config.py       # Configuration tests
│   ├── test_core.py         # Enhanced LayoutLens tests
│   └── test_query_generator.py # Query generation tests
├── integration/             # Integration tests
│   ├── test_page_testing.py # End-to-end workflow tests
│   └── test_test_runner.py  # Test runner integration
├── e2e/                     # End-to-end tests (future)
├── fixtures/                # Test data and samples
│   ├── sample_pages/        # HTML test files
│   ├── expected_outputs/    # Expected test results
│   └── mock_responses/      # Mock API responses
└── conftest.py             # Pytest configuration and fixtures
```

### Test Categories

Tests are categorized using pytest markers:

- `@pytest.mark.unit` - Fast, isolated unit tests
- `@pytest.mark.integration` - Integration between components
- `@pytest.mark.e2e` - End-to-end system tests
- `@pytest.mark.slow` - Tests that take longer to run
- `@pytest.mark.requires_api` - Tests requiring API access

### Running Specific Categories

```bash
# Run only unit tests
pytest -m unit

# Run integration tests
pytest -m integration  

# Skip slow tests
pytest -m "not slow"

# Run tests that require API
pytest -m requires_api
```

## Writing Tests

### Unit Test Example

```python
import pytest
from unittest.mock import Mock, patch
from layoutlens.config import Config

@pytest.mark.unit
class TestConfig:
    def test_config_defaults(self):
        """Test configuration default values."""
        config = Config()
        
        assert config.llm.provider == "openai"
        assert config.llm.model == "gpt-4o-mini"
        assert config.output.base_dir == "layoutlens_output"
    
    @patch('layoutlens.config.os.environ.get')
    def test_config_from_env(self, mock_env_get):
        """Test configuration loading from environment."""
        mock_env_get.return_value = "custom-model"
        
        config = Config()
        config._load_from_env()
        
        assert config.llm.model == "custom-model"
```

### Integration Test Example

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
        mock_page_tester = Mock()
        mock_page_tester_class.return_value = mock_page_tester
        
        mock_result = Mock()
        mock_result.success_rate = 0.9
        mock_page_tester.test_page.return_value = mock_result
        
        # Test
        tester = LayoutLens()
        result = tester.test_page(sample_html_file, queries=["Is the layout correct?"])
        
        # Verify
        assert result.success_rate == 0.9
        mock_page_tester.test_page.assert_called_once()
```

### Using Fixtures

Common fixtures are available in `conftest.py`:

```python
def test_with_temp_directory(temp_dir):
    """Use temporary directory fixture."""
    test_file = temp_dir / "test.txt"
    test_file.write_text("content")
    assert test_file.exists()

def test_with_sample_html(sample_html_file):
    """Use sample HTML file fixture."""
    with open(sample_html_file, 'r') as f:
        content = f.read()
    assert "Test Page" in content

def test_with_mock_response(mock_openai_response):
    """Use mock OpenAI response."""
    assert "correct" in mock_openai_response.lower()
```

## Mocking Guidelines

### Mocking External APIs

Always mock external API calls in tests:

```python
@patch('legacy.framework.OpenAI')
def test_layoutlens_with_mock_api(mock_openai):
    """Test with mocked OpenAI API."""
    mock_client = Mock()
    mock_openai.return_value = mock_client
    
    mock_response = Mock()
    mock_response.output_text = "Test response"
    mock_client.responses.create.return_value = mock_response
    
    lens = LayoutLens(api_key="test-key")
    result = lens.ask(["image.png"], "Test query")
    
    assert result == "Test response"
```

### Mocking File Operations

Mock file operations to avoid creating actual files:

```python
@patch('builtins.open', create=True)
def test_file_reading(mock_open):
    """Test file reading with mocked open."""
    mock_file = Mock()
    mock_file.read.return_value = b"fake_image_data"
    mock_open.return_value.__enter__.return_value = mock_file
    
    # Test code that reads files
    with open("test.png", "rb") as f:
        data = f.read()
    
    assert data == b"fake_image_data"
```

### Mocking Playwright

Mock browser automation for screenshot tests:

```python
@patch('legacy.screenshot.sync_playwright')
def test_screenshot_capture(mock_playwright, temp_dir):
    """Test screenshot capture with mocked Playwright."""
    mock_playwright_instance = Mock()
    mock_playwright.return_value.__enter__.return_value = mock_playwright_instance
    
    mock_browser = Mock()
    mock_page = Mock()
    
    mock_playwright_instance.chromium.launch.return_value = mock_browser
    mock_browser.new_page.return_value = mock_page
    
    # Test screenshot function
    from legacy.screenshot import html_to_image
    html_to_image("test.html", "output.png")
    
    # Verify calls
    mock_page.goto.assert_called_once()
    mock_page.screenshot.assert_called_once()
```

## Test Data and Fixtures

### Sample HTML Files

Test HTML files are located in `tests/fixtures/sample_pages/`:

- `simple_page.html` - Basic page with common elements
- `responsive_page.html` - Responsive design test page
- More specialized pages as needed

### Expected Outputs

`tests/fixtures/expected_outputs/` contains expected test results:

- Query expectations for different page types
- Viewport-specific test results
- Accessibility assessment expectations

### Mock Responses

`tests/fixtures/mock_responses/openai_responses.json` contains:

- Successful API responses
- Error responses
- Comparison responses
- Accessibility-focused responses

## Continuous Integration

### GitHub Actions

Tests run automatically on:

- Push to `main` or `develop` branches
- Pull requests to `main`
- Multiple Python versions (3.8-3.12)

### Local CI Simulation

Run the same tests as CI locally:

```bash
# Install all dependencies
pip install -r requirements-test.txt
playwright install chromium

# Run full test suite with coverage
pytest tests/ -v --cov=layoutlens --cov=framework --cov=scripts --cov-report=html

# Run tests in parallel like CI
pytest tests/ -n auto

# Test package installation
pip install -e .
python -c "import layoutlens; print('OK')"
```

## Performance Testing

### Timing Tests

Mark slow tests appropriately:

```python
@pytest.mark.slow
def test_large_page_processing():
    """Test processing of large pages - marked as slow."""
    # Test implementation
    pass
```

### Memory Usage

Monitor memory usage in integration tests:

```python
import psutil
import os

def test_memory_usage():
    """Test that memory usage stays reasonable."""
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss
    
    # Run memory-intensive operations
    tester = LayoutLens()
    results = []
    for i in range(100):
        result = tester.test_page("large_page.html")
        results.append(result)
    
    final_memory = process.memory_info().rss
    memory_increase = final_memory - initial_memory
    
    # Assert memory increase is reasonable (e.g., less than 100MB)
    assert memory_increase < 100 * 1024 * 1024
```

## Debugging Tests

### Verbose Output

```bash
# Run with maximum verbosity
pytest -vvv

# Show local variables in tracebacks
pytest --tb=long

# Drop into debugger on failure
pytest --pdb

# Only show failed test output
pytest --tb=short
```

### Test-Specific Debugging

```python
def test_debug_example():
    """Example with debug information."""
    result = some_function()
    
    # Add debug prints (remove before committing)
    print(f"Debug: result = {result}")
    
    # Use pytest's built-in debugging
    import pytest
    pytest.set_trace()  # Drops into pdb debugger
    
    assert result == expected_value
```

## Contributing Tests

### Test Requirements

When adding new features, ensure you include:

1. **Unit tests** for individual functions/methods
2. **Integration tests** for component interactions  
3. **Mock tests** for external dependencies
4. **Error handling tests** for edge cases
5. **Documentation** for complex test scenarios

### Test Quality Guidelines

- Tests should be **fast** (unit tests < 100ms each)
- Tests should be **independent** (order doesn't matter)
- Tests should be **repeatable** (same result every time)
- Use **descriptive names** that explain what's being tested
- **Mock external dependencies** (APIs, file system, etc.)
- **Test error conditions** as well as success cases

### Code Coverage

Maintain high code coverage:

```bash
# Generate coverage report
pytest --cov=layoutlens --cov-report=html

# View coverage report
open htmlcov/index.html

# Fail if coverage drops below threshold
pytest --cov=layoutlens --cov-fail-under=85
```

Target coverage levels:
- **Unit tests**: > 90% coverage
- **Integration tests**: > 80% coverage  
- **Overall**: > 85% coverage

## Troubleshooting

### Common Issues

**Playwright browser not found:**
```bash
playwright install chromium
```

**Import errors in tests:**
```bash
pip install -e .
```

**API rate limiting:**
- Use mocks for most tests
- Set up test API keys with higher limits
- Add delays between API tests if needed

**Test isolation issues:**
- Ensure tests clean up after themselves
- Use fresh temporary directories
- Reset global state between tests

### Getting Help

- Check existing tests for patterns
- Review `conftest.py` for available fixtures
- Look at GitHub Actions logs for CI failures
- Ask questions in issues or discussions