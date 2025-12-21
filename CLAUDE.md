# CLAUDE.md - LayoutLens v1.4.0

This file provides guidance to Claude Code (claude.ai/code) when working with the LayoutLens codebase.

## Project Overview

 LayoutLens is a production-ready AI-powered UI testing framework that enables natural language visual testing. It captures screenshots using Playwright and analyzes them with OpenAI's GPT-4o Vision API to validate layouts, accessibility, responsive design, and visual consistency.

**Current Version:** v1.4.0 (includes CLI refactor, async-by-default processing, and comprehensive documentation)

## Quick Start Commands

### Installation
```bash
pip install layoutlens>=1.4.0
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

### CLI Usage (v1.4.0 - Async-by-Default)
```bash
# Show system info and check setup
layoutlens info

# Analyze a single page with concurrent processing
layoutlens test --page https://example.com --queries "Is this page accessible?,Is the design professional?"

# Test with multiple viewports concurrently
layoutlens test --page mysite.com --queries "Good mobile UX?" --viewports "mobile_portrait,desktop"

# Compare two pages with async processing
layoutlens compare page1.html page2.html --query "Which design is better?"

# Batch process multiple sources efficiently
layoutlens batch --sources "site1.com,site2.com" --queries "Is it accessible?"

# Start interactive session with Rich formatting
layoutlens interactive

# Generate configuration file
layoutlens generate config --output my_config.yaml

# Validate configuration
layoutlens validate --config my_config.yaml
```

## Current API Structure (v1.4.0)

### Core LayoutLens Class
```python
from layoutlens import LayoutLens

# Initialize with LiteLLM unified provider support
lens = LayoutLens(
    api_key="your-key",        # Optional if OPENAI_API_KEY env var set
    model="gpt-4o-mini",       # Model to use (LiteLLM naming)
    provider="openai",         # "openai", "anthropic", "google", "gemini", "litellm"
    output_dir="custom_dir",   # Output directory for screenshots
    cache_enabled=True,        # Enable result caching for performance
    cache_type="memory"        # "memory" or "file"
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

# Batch analysis (sync)
results = lens.analyze_batch(
    sources=["page1.html", "page2.html"],
    queries=["Is it accessible?", "Is it mobile-friendly?"],
    viewport="desktop"
)

# Async batch analysis for better performance
results = await lens.analyze_batch_async(
    sources=["page1.html", "page2.html"],
    queries=["Is it accessible?", "Is it mobile-friendly?"],
    max_concurrent=5
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

## Package Structure (v1.4.0)

```
layoutlens/
├── __init__.py           # Main exports
├── api/
│   ├── __init__.py
│   ├── core.py          # LayoutLens class with async support
│   └── test_suite.py    # Test suite execution
├── vision/
│   ├── __init__.py
│   ├── analyzer.py      # VisionAnalyzer class
│   ├── capture.py       # URLCapture class
│   └── comparator.py    # LayoutComparator class
├── providers/
│   ├── __init__.py
│   ├── openai.py        # OpenAI provider
│   ├── openrouter.py    # OpenRouter provider
│   ├── anthropic.py     # Anthropic provider
│   └── google.py        # Google provider
├── integrations/
│   ├── __init__.py
│   └── github.py        # GitHub Actions integration
├── cli.py               # Main CLI entry point
├── cli_commands.py      # Unified async command implementations
├── cli_interactive.py   # Interactive mode with Rich formatting
├── config.py            # Configuration management
├── cache.py             # Result caching system
├── logger.py            # Structured logging
└── exceptions.py        # Custom exception classes
```

## CLI Commands (v1.4.0 - Async-by-Default)

### test command
```bash
# Analyze single page with custom queries (concurrent processing)
layoutlens test --page https://example.com --queries "Is it accessible?,Is it responsive?"

# Analyze with multiple viewports concurrently
layoutlens test --page mypage.html --queries "How's the mobile layout?" --viewports "mobile_portrait,desktop"

# Run test suite with async processing
layoutlens test --suite test_suite.yaml --max-concurrent 5
```

### compare command
```bash
# Compare two pages with async processing
layoutlens compare before.html after.html --query "Which design is more user-friendly?"
```

### batch command
```bash
# Process multiple sources efficiently
layoutlens batch --sources "site1.com,site2.com,site3.com" --queries "Is it accessible?"

# Load sources from file
layoutlens batch --sources-file urls.txt --queries "Good UX?,Mobile friendly?"
```

### interactive command
```bash
# Start interactive session with Rich terminal formatting
layoutlens interactive
```

### info command
```bash
# Check system setup, dependencies, and API keys
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

# Validate test suite file
layoutlens validate --suite test_suite.yaml
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
    provider="openai",        # Choose AI provider
    output_dir="screenshots",  # Custom output directory
    cache_enabled=True,       # Enable caching for performance
    cache_type="file",        # Use file-based caching
    cache_ttl=7200           # Cache for 2 hours
)

# LiteLLM unified provider examples
lens = LayoutLens(provider="anthropic", model="anthropic/claude-3-5-sonnet")
lens = LayoutLens(provider="google", model="google/gemini-1.5-pro")
lens = LayoutLens(provider="litellm", model="gpt-4o")  # Direct LiteLLM access
```

## Security Notes (v1.4.0)

- ✅ **API key logging fixed** - CLI no longer exposes API keys in logs
- ✅ **Secure by default** - No sensitive information logged
- ✅ **Comprehensive error handling** - Custom exception hierarchy with proper logging
- ✅ **Input validation** - All user inputs validated before processing
- ⚠️ **Always use v1.4.0+** - Previous versions had security vulnerabilities

## New Features in v1.4.0

### CLI Improvements
- ✅ **Async-by-default processing** - All commands use concurrent execution for optimal performance
- ✅ **Test suite support** - Full YAML-based test suite execution with async processing
- ✅ **Interactive mode** - Real-time analysis with Rich terminal formatting
- ✅ **Batch processing** - Efficient concurrent analysis of multiple sources
- ✅ **Unified command structure** - Single entry point with consistent async processing

### Architecture Improvements
- ✅ **LiteLLM unified provider** - Support for OpenAI, Anthropic, and Google via LiteLLM
- ✅ **Result caching** - Memory and file-based caching for improved performance
- ✅ **Structured logging** - Comprehensive logging with performance metrics
- ✅ **Custom exceptions** - Detailed error handling with proper context
- ✅ **Google-style docstrings** - Comprehensive documentation throughout codebase

### Architecture Notes
- **Screenshot capture**: Uses Playwright for reliable browser automation
- **AI Analysis**: Unified access to multiple providers via LiteLLM
- **Output format**: Natural language responses with confidence scores
- **File support**: URLs, local HTML files, and image files
- **Async processing**: Concurrent execution for optimal performance

## Development Notes

### What Works (v1.4.0)
- ✅ Core analysis API (`analyze`, `compare`, `analyze_batch`, `analyze_batch_async`)
- ✅ Built-in checks (accessibility, mobile-friendly, conversion)
- ✅ Full CLI command suite (test, compare, batch, interactive, info, generate, validate)
- ✅ Test suite execution with YAML configuration
- ✅ Interactive mode with Rich terminal formatting
- ✅ Async-by-default processing with concurrent execution
- ✅ LiteLLM unified provider support
- ✅ Result caching system
- ✅ Screenshot capture and analysis
- ✅ Multiple viewport support
- ✅ Context-aware analysis
- ✅ Comprehensive error handling
- ✅ Examples and documentation
- ✅ Structured logging and performance metrics

### Development Standards
- ✅ **Google-style docstrings** throughout codebase
- ✅ **Comprehensive CLI tests** with 95%+ coverage
- ✅ **Async-first architecture** for optimal performance
- ✅ **Type hints** and proper error handling
- ✅ **Clean CLI separation** - thin entry point with modular commands

## Performance Characteristics

- **Processing Time**: ~10-20 seconds per analysis (improved with caching)
- **Concurrent Processing**: 3-5 analyses simultaneously by default
- **Caching**: Memory and file-based caching for repeated analyses
- **Accuracy**: High confidence on well-formed pages
- **Dependencies**: OpenAI, Playwright, BeautifulSoup4, PyYAML, Pillow, Rich (optional)
- **Python Compatibility**: 3.11+

## Development Guidelines

### Code Quality
- **Use async-by-default** for all new CLI commands
- **Include comprehensive docstrings** (Google style)
- **Add proper error handling** with custom exceptions
- **Test CLI functionality** with pytest
- **Follow performance patterns** with caching and concurrency

### Testing Commands
```bash
# Run linting and formatting
uv run ruff check --fix
uv run ruff format

# Run tests with coverage
uv run pytest tests/ -v --cov=layoutlens

# Run CLI-specific tests
uv run pytest tests/test_cli.py -v
```

This codebase is production-ready with async-by-default CLI, comprehensive error handling, and performance optimizations fully implemented and tested.
