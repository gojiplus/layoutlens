# LayoutLens: AI-Powered Visual UI Testing

[![PyPI version](https://badge.fury.io/py/layoutlens.svg)](https://badge.fury.io/py/layoutlens)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Documentation](https://readthedocs.org/projects/layoutlens/badge/?version=latest)](https://layoutlens.readthedocs.io/)

## The Problem

Traditional UI testing is painful:
- **Brittle selectors** break with every design change
- **Pixel-perfect comparisons** fail on minor, acceptable variations
- **Writing test assertions** requires deep technical knowledge
- **Cross-browser testing** multiplies complexity
- **Generic analysis lacks domain expertise** - accessibility, conversion optimization, mobile UX
- **Accessibility checks** need specialized tools and expertise

## The Solution

LayoutLens lets you test UIs the way humans see them - using natural language and domain expert knowledge:

```python
# Basic analysis
result = await lens.analyze("https://example.com", "Is the navigation user-friendly?")

# Expert-powered analysis
result = await lens.audit_accessibility("https://example.com", compliance_level="AA")
# Returns: "WCAG AA compliant with 4.7:1 contrast ratio. Focus indicators visible..."
```

Instead of writing complex selectors and assertions, just ask questions like:
- "Is this page mobile-friendly?"
- "Are all buttons accessible?"
- "Does the layout look professional?"

Get expert-level insights from built-in domain knowledge in **accessibility**, **conversion optimization**, **mobile UX**, and more.

**✅ 95.2% accuracy** on real-world UI testing benchmarks

## Quick Start

### Installation
```bash
pip install layoutlens
playwright install chromium  # For screenshot capture
```

### Basic Usage
```python
from layoutlens import LayoutLens

# Initialize (uses OPENAI_API_KEY env var)
lens = LayoutLens()

# Test any website or local HTML
result = await lens.analyze("https://your-site.com", "Is the header properly aligned?")
print(f"Answer: {result.answer}")
print(f"Confidence: {result.confidence:.1%}")
```

That's it! No selectors, no complex setup, just natural language questions.

## Key Functions

### 1. Analyze Pages
Test single pages with custom questions:
```python
# Test local HTML files
result = await lens.analyze("checkout.html", "Is the payment form user-friendly?")

# Test with expert context
from layoutlens.prompts import Instructions, UserContext

instructions = Instructions(
    expert_persona="conversion_expert",
    user_context=UserContext(
        business_goals=["reduce_cart_abandonment"],
        target_audience="mobile_shoppers"
    )
)

result = await lens.analyze(
    "checkout.html",
    "How can we optimize this checkout flow?",
    instructions=instructions
)
```

### 2. Compare Layouts
Perfect for A/B testing and redesign validation:
```python
result = await lens.compare(
    ["old-design.html", "new-design.html"],
    "Which design is more accessible?"
)
print(f"Winner: {result.answer}")
```

### 3. Expert-Powered Analysis
Domain expert knowledge with one line of code:
```python
# Professional accessibility audit (WCAG expert)
result = await lens.audit_accessibility("product-page.html", compliance_level="AA")

# Conversion rate optimization (CRO expert)
result = await lens.optimize_conversions("landing.html",
    business_goals=["increase_signups"], industry="saas")

# Mobile UX analysis (Mobile expert)
result = await lens.analyze_mobile_ux("app.html", performance_focus=True)

# E-commerce audit (Retail expert)
result = await lens.audit_ecommerce("checkout.html", page_type="checkout")

# Legacy methods still work
result = await lens.check_accessibility("product-page.html")  # Backward compatible
```

### 4. Batch Testing
Test multiple pages efficiently:
```python
results = await lens.analyze(
    sources=["home.html", "about.html", "contact.html"],
    queries=["Is it accessible?", "Is it mobile-friendly?"]
)
# Processes 6 tests in parallel
```

### 5. High-Performance Async (3-5x faster)
```python
# Async for maximum throughput
result = await lens.analyze(
    sources=["page1.html", "page2.html", "page3.html"],
    queries=["Is it accessible?"],
    max_concurrent=5
)
```

### 6. Structured JSON Output
All results provide clean, typed JSON for automation:
```python
result = await lens.analyze("page.html", "Is it accessible?")

# Export to clean JSON
json_data = result.to_json()  # Returns typed JSON string
print(json_data)
# {
#   "source": "page.html",
#   "query": "Is it accessible?",
#   "answer": "Yes, the page follows accessibility standards...",
#   "confidence": 0.85,
#   "reasoning": "The page has proper heading structure...",
#   "screenshot_path": "/path/to/screenshot.png",
#   "viewport": "desktop",
#   "timestamp": "2024-01-15 10:30:00",
#   "execution_time": 2.3,
#   "metadata": {}
# }

# Type-safe structured access
from layoutlens.types import AnalysisResultJSON
import json
data: AnalysisResultJSON = json.loads(result.to_json())
confidence = data["confidence"]  # Fully typed: float
```

### 7. Domain Experts & Rich Context
Choose from 6 built-in domain experts with specialized knowledge:
```python
# Available experts: accessibility_expert, conversion_expert, mobile_expert,
# ecommerce_expert, healthcare_expert, finance_expert

# Use any expert with custom analysis
result = await lens.analyze_with_expert(
    source="healthcare-portal.html",
    query="How can we improve patient experience?",
    expert_persona="healthcare_expert",
    focus_areas=["patient_privacy", "health_literacy"],
    user_context={
        "target_audience": "elderly_patients",
        "accessibility_needs": ["large_text", "simple_navigation"],
        "industry": "healthcare"
    }
)

# Expert comparison analysis
result = await lens.compare_with_expert(
    sources=["old-design.html", "new-design.html"],
    query="Which design converts better?",
    expert_persona="conversion_expert",
    focus_areas=["cta_prominence", "trust_signals"]
)
```

## CLI Usage

```bash
# Analyze a single page
layoutlens https://example.com "Is this accessible?"

# Analyze local files
layoutlens page.html "Is the design professional?"

# Compare two designs
layoutlens page1.html page2.html --compare

# Analyze with different viewport
layoutlens site.com "Is it mobile-friendly?" --viewport mobile

# JSON output for automation
layoutlens page.html "Is it accessible?" --output json
```

## CI/CD Integration

### GitHub Actions
```yaml
- name: Visual UI Test
  run: |
    pip install layoutlens
    playwright install chromium
    layoutlens ${{ env.PREVIEW_URL }} "Is it accessible and mobile-friendly?"
```

### Python Testing
```python
import pytest
from layoutlens import LayoutLens

@pytest.mark.asyncio
async def test_homepage_quality():
    lens = LayoutLens()
    result = await lens.analyze("homepage.html", "Is this production-ready?")
    assert result.confidence > 0.8
    assert "yes" in result.answer.lower()
```

## Benchmark & Evaluation Workflow

LayoutLens includes a comprehensive benchmarking system to validate AI performance:

### 1. Generate Benchmark Results
```bash
# Run LayoutLens against test data
python benchmarks/run_benchmark.py --api-key sk-your-key

# With custom settings
python benchmarks/run_benchmark.py \
  --api-key sk-your-key \
  --output benchmarks/my_results \
  --no-batch \
  --filename custom_results.json
```

### 2. Evaluate Performance
```bash
# Evaluate results against ground truth
python benchmarks/evaluation/evaluator.py \
  --answer-keys benchmarks/answer_keys \
  --results benchmarks/layoutlens_output \
  --output evaluation_report.json
```

### 3. Structured Benchmark Results
The benchmark runner outputs clean JSON for analysis:
```python
# Example benchmark result structure
{
  "benchmark_info": {
    "total_tests": 150,
    "successful_tests": 143,
    "failed_tests": 7,
    "success_rate": 0.953,
    "batch_processing_used": true,
    "model_used": "gpt-4o-mini"
  },
  "results": [
    {
      "html_file": "good_contrast.html",
      "query": "Is this page accessible?",
      "answer": "Yes, the page has good color contrast...",
      "confidence": 0.89,
      "reasoning": "WCAG guidelines are followed...",
      "success": true,
      "error": null,
      "metadata": {"category": "accessibility"}
    }
  ]
}
```

### 4. Custom Benchmarks
Create your own test data and answer keys:
```python
# Use the async API for custom benchmark workflows
from layoutlens import LayoutLens

async def run_custom_benchmark():
    lens = LayoutLens()

    test_cases = [
        {"source": "page1.html", "query": "Is it accessible?"},
        {"source": "page2.html", "query": "Is it mobile-friendly?"}
    ]

    results = []
    for case in test_cases:
        result = await lens.analyze(case["source"], case["query"])
        results.append({
            "test": case,
            "result": result.to_json(),  # Clean JSON output
            "passed": result.confidence > 0.7
        })

    return results
```

## Configuration

Simple configuration options:
```python
# Via environment
export OPENAI_API_KEY="sk-..."

# Via code
lens = LayoutLens(
    api_key="sk-...",
    model="gpt-4o-mini",  # or "gpt-4o" for higher accuracy
    cache_enabled=True,   # Reduce API costs
    cache_type="memory",  # "memory" or "file"
)
```

## Resources

- 📖 **[Full Documentation](https://layoutlens.readthedocs.io/)** - Comprehensive guides and API reference
- 🎯 **[Examples](https://github.com/gojiplus/layoutlens/tree/main/examples)** - Real-world usage patterns
- 🐛 **[Issues](https://github.com/gojiplus/layoutlens/issues)** - Report bugs or request features
- 💬 **[Discussions](https://github.com/gojiplus/layoutlens/discussions)** - Get help and share ideas

## Why LayoutLens?

- **Natural Language** - Write tests like you'd describe the UI to a colleague
- **Domain Expert Knowledge** - Built-in expertise in accessibility, CRO, mobile UX, and more
- **Rich Context Support** - Business goals, user personas, compliance standards, and technical constraints
- **Zero Selectors** - No more fragile XPath or CSS selectors
- **Visual Understanding** - AI sees what users see, not just code
- **Async-by-Default** - Concurrent processing for optimal performance
- **Simple API** - One analyze method handles single pages, batches, and comparisons
- **Structured JSON Output** - TypedDict schemas for full type safety in automation
- **Comprehensive Benchmarking** - Built-in evaluation system with 95.2% accuracy
- **Production Ready** - Used by teams for real-world applications

---

*Making UI testing as simple as asking "Does this look right?"*
