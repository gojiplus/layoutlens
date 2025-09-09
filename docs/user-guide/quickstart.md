# Quick Start Guide

Get started with LayoutLens in just a few minutes!

## Installation

```bash
pip install layoutlens
```

### Prerequisites
```bash
# Install Playwright browsers (required for screenshots)
playwright install chromium

# Set your OpenAI API key
export OPENAI_API_KEY="your-api-key-here"
```

## Basic Usage

### 1. Test a Single Page

```python
from layoutlens import LayoutLens

# Initialize the tester
tester = LayoutLens()

# Test a webpage
result = tester.test_page(
    html_path="homepage.html",
    queries=[
        "Is the navigation menu visible?",
        "Is the logo properly positioned?", 
        "Is the layout responsive?"
    ]
)

# Check results
print(f"Success rate: {result.success_rate:.2%}")
print(f"Tests passed: {result.passed_tests}/{result.total_tests}")
```

### 2. Compare Two Pages

```python
# Compare before/after versions
comparison = tester.compare_pages(
    page_a_path="before.html",
    page_b_path="after.html",
    query="Are the layouts visually consistent?"
)

print(f"Comparison result: {comparison['answer']}")
```

### 3. Command Line Interface

```bash
# Test a single page
layoutlens test --page homepage.html --queries "Is the header visible?,Is the content readable?"

# Run a test suite
layoutlens test --suite my_tests.yaml

# Compare pages  
layoutlens compare old_design.html new_design.html

# Generate configuration
layoutlens generate config --output my_config.yaml
```

## Your First Test Suite

Create a test suite file `my_tests.yaml`:

```yaml
name: "Website Test Suite"
description: "Basic website testing"

test_cases:
  - name: "Homepage Desktop"
    html_path: "homepage.html"
    queries:
      - "Is the main navigation clearly visible?"
      - "Is the hero section prominent?"
      - "Are the call-to-action buttons visible?"
    viewports: ["desktop"]
    
  - name: "Homepage Mobile"
    html_path: "homepage.html"
    queries:
      - "Is the mobile menu accessible?"
      - "Is the content readable without scrolling?"
    viewports: ["mobile_portrait"]
```

Run it:
```bash
layoutlens test --suite my_tests.yaml
```

## Automatic Query Generation

LayoutLens can automatically generate test queries by analyzing your HTML:

```python
# Let LayoutLens analyze the page and create appropriate tests
result = tester.test_page(
    html_path="page.html",
    auto_generate_queries=True,  # This is the default
    viewports=["desktop", "mobile_portrait"]
)
```

## Configuration

Create a configuration file for custom settings:

```bash
layoutlens generate config --output config.yaml
```

Edit `config.yaml` to customize:
- LLM model and settings
- Screenshot options
- Viewport configurations  
- Output formats

Then use it:
```bash
layoutlens --config config.yaml test --page homepage.html
```

## Next Steps

- **[Configuration Guide](configuration.md)** - Customize LayoutLens behavior
- **[CLI Reference](cli-reference.md)** - Complete command-line documentation
- **[Examples](examples.md)** - More usage patterns and examples
- **[API Documentation](../api/core.md)** - Detailed API reference

## Getting Help

- Check the [Examples](examples.md) for common patterns
- Review [FAQ](faq.md) for common issues
- Ask questions in [GitHub Discussions](https://github.com/matmulai/layoutlens/discussions)
- Report bugs in [GitHub Issues](https://github.com/matmulai/layoutlens/issues)