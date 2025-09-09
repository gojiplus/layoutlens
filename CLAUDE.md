# CLAUDE.md - LayoutLens v1.0.0

This file provides guidance to Claude Code (claude.ai/code) when working with the LayoutLens codebase.

## Project Overview

LayoutLens is a production-ready AI-powered UI testing framework that enables natural language visual testing. It captures screenshots using Playwright and analyzes them with OpenAI's GPT-4o Vision API to validate layouts, accessibility, responsive design, and visual consistency.

**Key Achievement:** 95.2% accuracy on professional ground truth benchmark suite.

## Quick Start Commands

### Installation
```bash
pip install -e .
playwright install
```

### Basic Usage
```bash
# Set API key
export OPENAI_API_KEY="your_key_here"

# Test a single page
python -c "
from layoutlens import LayoutLens
tester = LayoutLens()
result = tester.test_page('benchmarks/ecommerce_product.html', 
                         queries=['Is the navigation properly aligned?'])
print(f'Success rate: {result.success_rate:.1%}')
"

# Run ground truth benchmark evaluation
python scripts/testing/ground_truth_evaluator.py --output-report results.json
```

### CLI Usage
```bash
layoutlens --help
```

## Release v1.0.0 Architecture

### Core Package Structure
- **`layoutlens/core.py`**: Main LayoutLens class with user-friendly API
- **`layoutlens/config.py`**: Configuration management (YAML + env vars)
- **`layoutlens/cli.py`**: Command-line interface
- **`scripts/testing/`**: Testing infrastructure (PageTester, ScreenshotManager, QueryGenerator)
- **`scripts/benchmark/`**: Benchmark generation tools

### Key Features Implemented
- ✅ **Multi-viewport screenshot capture** (desktop, mobile, tablet)
- ✅ **OpenAI GPT-4o Vision integration** for visual analysis
- ✅ **Ground truth benchmark suite** with objective test cases
- ✅ **Natural language query processing** 
- ✅ **Configuration system** with YAML and environment variables
- ✅ **CLI interface** for automation and CI/CD
- ✅ **Professional documentation** and examples

## Ground Truth Benchmark Suite

The package includes a comprehensive benchmark with objectively measurable test cases:

### Test Categories (95.2% Overall Accuracy)
- **Layout Alignment Issues**: 100.0% accuracy (6/6 tests)
  - Navigation centering (2% offset detection)
  - Logo positioning (wrong side detection)  
  - Button alignment (margin inconsistencies)

- **Responsive Design Problems**: 100.0% accuracy (4/4 tests)
  - Mobile viewport overflow
  - Touch target sizing (below 44px minimum)
  - Text readability (below 14px mobile standard)

- **Accessibility (WCAG) Violations**: 100.0% accuracy (6/6 tests)
  - Missing alt text
  - Form label associations
  - Keyboard navigation
  - Heading hierarchy
  - Table structure
  - Color-only information

- **Color Contrast Violations**: 80.0% accuracy (4/5 tests)
  - WCAG AA compliance (4.5:1 ratio requirements)
  - Calculated contrast ratios (1.07:1, 1.61:1, 1.92:1, etc.)

### Benchmark Files Location
- **`benchmarks/ground_truth_tests/`**: Test cases with embedded ground truth metadata
- **`benchmarks/ground_truth_tests/GROUND_TRUTH_ANSWERS.md`**: Expected answers documentation

## Testing and Development

### Running Tests
```bash
# Install test dependencies
pip install pytest

# Run core functionality tests  
pytest tests/unit/test_config.py tests/unit/test_core.py -v

# Run ground truth evaluation
python scripts/testing/ground_truth_evaluator.py
```

### Example Test Cases
```python
from layoutlens import LayoutLens

# Initialize with API key
tester = LayoutLens(api_key="your_key")

# Test single page
result = tester.test_page("page.html", queries=[
    "Is the navigation menu properly aligned?",
    "Are the button sizes appropriate for mobile?"
])

# Compare two pages
comparison = tester.compare_pages("before.html", "after.html")
print(comparison['answer'])
```

## Package Structure (Post-Cleanup)

```
layoutlens/
├── layoutlens/           # Core package
│   ├── core.py          # Main LayoutLens class  
│   ├── config.py        # Configuration system
│   └── cli.py           # Command line interface
├── scripts/             # Testing utilities
│   ├── testing/         # Page testing infrastructure
│   └── benchmark/       # Benchmark generation
├── benchmarks/          # HTML test files + ground truth
├── docs/               # Documentation
├── examples/           # Usage examples
└── tests/              # Test suite
```

## Performance Characteristics

- **Processing Time**: ~23 seconds average per test
- **Accuracy**: 95.2% on objective ground truth benchmark
- **Package Size**: ~50MB (cleaned from 300MB+ development version)
- **Dependencies**: OpenAI, Playwright, BeautifulSoup4, PyYAML, Pillow
- **Python Compatibility**: 3.8+

## Development Notes

### What Was Removed for v1.0.0 Release
- ❌ Legacy framework files (moved to clean v1.0 API)
- ❌ Development virtual environments (~200MB)
- ❌ Test output files and screenshots (~50MB)
- ❌ Build artifacts and caches (~5MB)
- ❌ Development-specific .md files

### What Was Fixed
- ✅ OpenAI Vision API integration in PageTester
- ✅ Screenshot capture using Playwright
- ✅ Ground truth evaluation system
- ✅ Package dependencies and structure
- ✅ Configuration and CLI systems

This codebase is release-ready with professional-grade accuracy measurement and comprehensive documentation.