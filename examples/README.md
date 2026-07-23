# LayoutLens Examples

This directory contains working examples demonstrating LayoutLens usage patterns.

## 📁 File Organization

### Core Examples
- **`basic_usage.py`** - Essential patterns for getting started with the LayoutLens API
- **`advanced_usage.py`** - Complex analysis scenarios and patterns
- **`simple_api_usage.py`** - Quick examples of common use cases
- **`layoutlens_config.yaml`** - Complete configuration reference
- **`sample_test_suite.yaml`** - Sample test configuration

## 🚀 Quick Start

### 1. Basic Usage
```bash
# Set your OpenAI API key
export OPENAI_API_KEY="your-key-here"

# Run basic examples
cd examples/
python basic_usage.py
```

### 2. Simple API Examples
```bash
# Quick API demonstrations
python simple_api_usage.py
```

### 3. Advanced Scenarios
```bash
# Complex analysis workflows
python advanced_usage.py
```

## 📋 Example Categories

### Basic Examples (`basic_usage.py`)
1. **Single Page Analysis** - Analyze HTML files or URLs with natural language queries
2. **Website Analysis** - Test live websites
3. **Design Comparison** - Compare two different layouts
4. **Batch Analysis** - Analyze multiple pages efficiently
5. **Built-in Checks** - Use specialized accessibility and mobile-friendly checks

### Simple API Examples (`simple_api_usage.py`)
1. **URL Analysis** - Basic website analysis
2. **Mobile Analysis** - Mobile-specific checks
3. **Accessibility Checks** - WCAG compliance validation
4. **Before/After Comparisons** - Design change analysis
5. **Batch Processing** - Multiple page analysis
6. **Context-Aware Analysis** - Analysis with specific context

### Advanced Examples (`advanced_usage.py`)
1. **Context-Rich Analysis** - Analysis with detailed context information
2. **Multi-Viewport Testing** - Test across different screen sizes
3. **Specialized Workflows** - Accessibility, mobile, and conversion optimization
4. **Performance Optimization** - Efficient large-scale testing
5. **Error Handling** - Robust error handling patterns

## 🔧 Configuration

The examples demonstrate various ways to configure LayoutLens:

```python
from layoutlens import LayoutLens

# Basic initialization
lens = LayoutLens()

# With custom API key
lens = LayoutLens(api_key="your-key")

# With custom model
lens = LayoutLens(model="gpt-4o")

# With custom output directory
lens = LayoutLens(output_dir="custom_output")
```

## 📊 API Methods Demonstrated

All examples use the actual LayoutLens API methods (all async):

### Core Analysis
- `await analyze(source, query, viewport="desktop", context=None, max_concurrent=5)` - Analyze one
  or more pages/screenshots; pass a list to `source` and/or `query` to fan out concurrently (returns
  a `BatchResult` when there's more than one combination)
- `await compare(sources, query, context=None)` - Compare multiple pages (URLs or already-captured
  screenshots; local HTML paths need `capture()` first — see below)
- `await capture(source, viewport="desktop")` - Render a URL/HTML file to a screenshot PNG

### Built-in Checks
- `check_accessibility(source)` - Accessibility compliance
- `check_mobile_friendly(source)` - Mobile usability
- `check_conversion_optimization(source)` - Conversion optimization

## ⚡ Running Examples

### Prerequisites
```bash
# Install LayoutLens
pip install layoutlens

# Install browser for screenshots
playwright install chromium

# Set required environment variable
export OPENAI_API_KEY="your-openai-api-key"
```

### Individual Examples
```bash
# Basic patterns
python examples/basic_usage.py

# Simple API usage
python examples/simple_api_usage.py

# Advanced scenarios
python examples/advanced_usage.py
```

### Example Analysis
```python
import asyncio
from layoutlens import LayoutLens

async def main():
    lens = LayoutLens()

    # Analyze a page
    result = await lens.analyze(
        source="https://example.com",
        query="Is this page user-friendly and accessible?"
    )

    print(f"Answer: {result.answer}")
    print(f"Confidence: {result.confidence:.1%}")

asyncio.run(main())
```

## 🛠️ Customization

### Adding New Examples

1. **Use Real Sources**: Reference actual URLs or files
2. **Proper Error Handling**: Include try/catch blocks
3. **Clear Documentation**: Add descriptive docstrings
4. **API Compliance**: Use only existing API methods

### Custom Analysis Context
```python
# Add context for more targeted analysis
context = {
    "user_type": "elderly_users",
    "purpose": "accessibility_audit",
    "business_context": "healthcare_website"
}

result = await lens.analyze(
    source="https://example.com",
    query="Is this suitable for elderly users?",
    context=context
)
```

## 📈 Expected Results

When running these examples, you should see:

- **AI-powered analysis** with natural language feedback
- **Confidence scores** indicating reliability
- **Detailed reasoning** explaining the assessment
- **Screenshots** automatically captured and stored
- **Multi-viewport support** for responsive testing

The examples demonstrate LayoutLens's ability to:
- ✅ Analyze layouts with natural language queries
- ✅ Compare different designs objectively
- ✅ Check accessibility and mobile-friendliness
- ✅ Process multiple pages efficiently
- ✅ Provide actionable feedback for UI improvements

## 🔗 Real-World Usage

These examples can be adapted for:
- **CI/CD Integration** - Automated UI testing in pipelines
- **Design Reviews** - Systematic design evaluation
- **Accessibility Audits** - WCAG compliance checking
- **A/B Testing** - Comparing design variations
- **Quality Assurance** - UI regression testing
