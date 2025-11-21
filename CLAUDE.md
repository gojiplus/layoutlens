# CLAUDE.md - LayoutLens v1.0.2

This file provides guidance to Claude Code (claude.ai/code) when working with the LayoutLens codebase.

## Project Overview

LayoutLens is a production-ready AI-powered UI testing framework that enables natural language visual testing. It captures screenshots using Playwright and analyzes them with OpenAI's GPT-4o Vision API to validate layouts, accessibility, responsive design, and visual consistency.

**Current Version:** v1.0.2 (includes critical security fix for API key logging)

## Quick Start Commands

### Installation
```bash
pip install layoutlens>=1.0.2
playwright install chromium
```

### Basic Usage
```bash
# Set API key
export OPENAI_API_KEY="your_key_here"

# Basic analysis
python -c "
from layoutlens import LayoutLens
lens = LayoutLens()
result = lens.analyze('https://example.com', 'Is the navigation user-friendly?')
print(f'Answer: {result.answer}')
print(f'Confidence: {result.confidence:.1%}')
"
```

### CLI Usage (Current Implementation)
```bash
# Show system info and check setup
layoutlens info

# Analyze a single page
layoutlens test --page https://example.com --queries "Is this page accessible?,Is the design professional?"

# Compare two pages
layoutlens compare page1.html page2.html --query "Which design is better?"

# Generate configuration file
layoutlens generate config --output my_config.yaml

# Validate configuration
layoutlens validate --config my_config.yaml
```

## Current API Structure (v1.0.2)

### Core LayoutLens Class
```python
from layoutlens import LayoutLens

# Initialize
lens = LayoutLens(
    api_key="your-key",        # Optional if OPENAI_API_KEY env var set
    model="gpt-4o-mini",       # Model to use
    output_dir="custom_dir"    # Output directory for screenshots
)
```

### Main API Methods
```python
# Single page analysis
result = lens.analyze(
    source="https://example.com",  # URL or file path
    query="Is this page user-friendly?",
    viewport="desktop",            # "desktop", "mobile_portrait", "tablet_landscape"
    context={"user_type": "elderly"}  # Optional context
)

# Compare multiple sources
result = lens.compare(
    sources=["page1.html", "page2.html"],
    query="Which layout is better?",
    context={"focus": "accessibility"}
)

# Batch analysis
results = lens.analyze_batch(
    sources=["page1.html", "page2.html"],
    queries=["Is it accessible?", "Is it mobile-friendly?"],
    viewport="desktop"
)

# Built-in checks
result = lens.check_accessibility("https://example.com")
result = lens.check_mobile_friendly("https://example.com")  
result = lens.check_conversion_optimization("https://example.com")
```

### Result Objects
All analysis methods return objects with these properties:
```python
result.answer      # String: Natural language answer
result.confidence  # Float: Confidence score (0.0-1.0)
result.reasoning   # String: Detailed explanation
result.metadata    # Dict: Additional information
```

## Package Structure (Current)

```
layoutlens/
├── __init__.py           # Main exports
├── api/
│   ├── __init__.py
│   └── core.py          # LayoutLens class
├── vision/
│   ├── __init__.py
│   ├── analyzer.py      # VisionAnalyzer class
│   ├── capture.py       # URLCapture class
│   └── comparator.py    # LayoutComparator class
├── integrations/
│   ├── __init__.py
│   └── github.py        # GitHub Actions integration
├── config.py            # Configuration management
└── cli.py              # Command-line interface
```

## CLI Commands (Working Implementation)

### test command
```bash
# Analyze single page with custom queries
layoutlens test --page https://example.com --queries "Is it accessible?,Is it responsive?"

# Analyze with specific viewport
layoutlens test --page mypage.html --queries "How's the mobile layout?" --viewports mobile_portrait
```

### compare command  
```bash
# Compare two pages
layoutlens compare before.html after.html --query "Which design is more user-friendly?"
```

### info command
```bash
# Check system setup and dependencies
layoutlens info
```

### generate command
```bash
# Generate default configuration
layoutlens generate config

# Generate test suite template  
layoutlens generate suite
```

### validate command
```bash
# Validate configuration file
layoutlens validate --config layoutlens.yaml
```

## Examples and Testing

### Running Examples
```bash
# Basic usage patterns
python examples/basic_usage.py

# Advanced scenarios
python examples/advanced_usage.py

# Simple API demonstrations
python examples/simple_api_usage.py
```

### Benchmark Evaluation  
```bash
# The package includes a benchmark system
python benchmarks/evaluation/evaluator.py
```

## Configuration

### Environment Variables
- `OPENAI_API_KEY` - Required for OpenAI Vision API access

### Custom Configuration
```python
# Pass parameters during initialization
lens = LayoutLens(
    model="gpt-4o",           # Use more powerful model
    output_dir="screenshots"   # Custom output directory
)
```

## Security Notes (v1.0.2)

- ✅ **API key logging fixed** - CLI no longer exposes API keys in logs
- ✅ **Secure by default** - No sensitive information logged
- ⚠️ **Always use v1.0.2+** - Previous versions had security vulnerabilities

## Limitations and Notes

### Current Limitations
- **Test suites**: CLI test suite functionality not yet implemented (use individual page analysis)
- **Parallel processing**: Not yet available in CLI (use Python API for batch operations)
- **Advanced configuration**: Limited CLI configuration options

### Architecture Notes
- **Screenshot capture**: Uses Playwright for reliable browser automation
- **AI Analysis**: OpenAI GPT-4o Vision API for visual understanding
- **Output format**: Natural language responses with confidence scores
- **File support**: URLs, local HTML files, and image files

## Development Notes

### What Works (v1.0.2)
- ✅ Core analysis API (`analyze`, `compare`, `analyze_batch`)
- ✅ Built-in checks (accessibility, mobile-friendly, conversion)
- ✅ CLI basic commands (test, compare, info, generate, validate)
- ✅ Screenshot capture and analysis
- ✅ Multiple viewport support
- ✅ Context-aware analysis
- ✅ Examples and documentation

### What's Not Implemented
- ❌ CLI test suite execution
- ❌ Advanced parallel processing in CLI
- ❌ Some legacy methods referenced in old docs

## Performance Characteristics

- **Processing Time**: ~15-30 seconds per analysis
- **Accuracy**: High confidence on well-formed pages
- **Dependencies**: OpenAI, Playwright, BeautifulSoup4, PyYAML, Pillow
- **Python Compatibility**: 3.10+

This codebase is production-ready with the core analysis functionality fully implemented and tested.