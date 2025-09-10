# LayoutLens Examples

This directory contains working examples demonstrating LayoutLens usage patterns.

## 📁 File Organization

### Core Examples
- **`basic_usage.py`** - Essential patterns for getting started
- **`advanced_usage.py`** - Complex testing scenarios and patterns  
- **`layoutlens_config.yaml`** - Complete configuration reference
- **`sample_test_suite.yaml`** - Working test suite using clean benchmark files

## 🚀 Quick Start

### 1. Basic Usage
```bash
# Set your OpenAI API key
export OPENAI_API_KEY="your-key-here"

# Run basic examples
cd examples/
python basic_usage.py
```

### 2. Test Suite Execution
```bash
# Run the sample test suite
python -c "
from layoutlens import LayoutLens
tester = LayoutLens()
results = tester.run_test_suite('examples/sample_test_suite.yaml')
print(f'Suite completed: {len(results)} test cases')
"
```


## 📋 Example Categories

### Basic Examples (`basic_usage.py`)
1. **Single Page Testing** - Test HTML files with custom queries
2. **Page Comparison** - Compare two pages visually  
3. **Auto-Generated Queries** - Let LayoutLens generate appropriate test queries
4. **Test Suite Creation** - Programmatically create and run test suites

### Advanced Examples (`advanced_usage.py`)  
1. **Custom Configuration** - Advanced configuration options
2. **Multi-Page Workflows** - Test related pages together
3. **Accessibility Focus** - Accessibility-specific testing patterns
4. **Responsive Design Validation** - Multi-viewport testing strategies
5. **Performance Testing** - Performance-aware visual testing
6. **Brand Consistency** - Brand guideline compliance testing


## 🔧 Configuration

The `layoutlens_config.yaml` file demonstrates all available configuration options:

- **LLM Settings** - Model selection, API configuration, temperature
- **Screenshot Options** - Format, quality, viewport settings
- **Test Execution** - Parallel execution, focus areas, error handling  
- **Output Configuration** - Directory structure, format options
- **Viewport Definitions** - Mobile, tablet, desktop configurations
- **Custom Query Libraries** - Pre-defined query sets by category

## 📊 Real Test Data

All examples use **real benchmark HTML files** from the clean `benchmarks/` structure:

- `benchmarks/test_data/layout_alignment/nav_centered.html` - Perfect navigation centering
- `benchmarks/test_data/accessibility/wcag_compliant.html` - WCAG AA compliance
- `benchmarks/test_data/ui_components/form_well_designed.html` - Professional form design
- `benchmarks/test_data/responsive_design/mobile_friendly.html` - Mobile-first responsive design

## ⚡ Running Examples

### Prerequisites
```bash
# Install LayoutLens in development mode
pip install -e .
playwright install chromium

# Set required environment variable
export OPENAI_API_KEY="your-openai-api-key"
```

### Individual Examples
```bash
# Basic patterns
python examples/basic_usage.py

# Advanced scenarios  
python examples/advanced_usage.py

# CI/CD integration
python examples/ci_cd_integration_simple.py
```

### Test Suite Example
```bash
# Using the sample test suite
python -c "
from layoutlens import LayoutLens
tester = LayoutLens()

# Load and run the sample suite
results = tester.run_test_suite('examples/sample_test_suite.yaml')

# Display results
if results:
    total_tests = sum(r.total_tests for r in results)
    total_passed = sum(r.passed_tests for r in results)
    success_rate = total_passed / total_tests
    print(f'Test suite completed: {success_rate:.1%} success rate')
else:
    print('Test suite execution failed')
"
```

## 🛠️ Customization

### Adding New Examples

1. **Use Real Files**: Reference actual files from `benchmarks/` directory
2. **Working Imports**: Only import modules that exist in the current codebase
3. **Error Handling**: Include proper error handling and status reporting
4. **Documentation**: Add clear docstrings and comments

### Configuration Customization

The examples use the default configuration, but you can customize:

```python
from layoutlens import LayoutLens, Config

# Load custom configuration
tester = LayoutLens(config="examples/layoutlens_config.yaml")

# Or create configuration programmatically
config = Config()
config.llm.model = "gpt-4o"  # Use more powerful model
tester = LayoutLens(config=config)
```

## 📈 Expected Results

When running these examples with the provided benchmark files, you should see:

- **High success rates** on well-formed HTML files
- **Detailed AI analysis** with specific feedback
- **Multi-viewport screenshots** captured successfully
- **Performance metrics** showing processing time and confidence scores

The examples demonstrate LayoutLens's ability to:
- ✅ Detect layout alignment issues
- ✅ Validate accessibility compliance
- ✅ Analyze responsive design effectiveness  
- ✅ Generate relevant test queries automatically
- ✅ Provide actionable feedback for UI improvements