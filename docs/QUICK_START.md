# LayoutLens Quick Start Guide

Get started with AI-powered UI testing in 5 minutes.

## 🚀 Installation

```bash
pip install layoutlens
playwright install chromium  # For screenshot capture
```

## 🔑 Setup

```bash
export OPENAI_API_KEY="sk-your-openai-key"
```

*Get your API key from [OpenAI Platform](https://platform.openai.com/api-keys)*

Only needed for LLM-backed analysis. The deterministic axe-core accessibility
mode (below) needs no API key at all — `LayoutLens()` itself never requires
one at construction either; a missing key only raises when an LLM call is
actually made.

## ♿ Deterministic Accessibility Checks (No API Key Required)

LayoutLens vendors [axe-core](https://github.com/dequelabs/axe-core) and runs it
against a real rendered page for actual WCAG 2.1 A/AA violations:

```bash
layoutlens page.html --a11y axe
```

```python
import asyncio
from layoutlens import AxeAuditor

async def main():
    report = await AxeAuditor().audit("page.html")
    print(report.summary())
    print(report.ok)  # True if zero violations

asyncio.run(main())
```

`check_accessibility(source, mode="hybrid")` (the default) combines this with
LLM vision analysis: axe grounds the LLM's assessment and deterministically
forces a "no" verdict if it finds any violation. Pass `mode="axe"` for the
keyless deterministic-only check, or `mode="llm"` for the legacy vision-only
check.

## 💡 Basic Usage

LayoutLens's API is async — call it with `await` from an `async def`, or wrap
top-level calls in `asyncio.run(...)`.

### Analyze a Website

```python
import asyncio
from layoutlens import LayoutLens

async def main():
    lens = LayoutLens()

    # Test any live website
    result = await lens.analyze(
        "https://your-website.com",
        "Is the navigation easy to use?"
    )

    print(f"Answer: {result.answer}")
    print(f"Confidence: {result.confidence:.1%}")

asyncio.run(main())
```

### Analyze Screenshots

```python
# Test an existing screenshot image
result = await lens.analyze(
    "screenshot.png",
    "Are the buttons large enough for mobile users?"
)
```

### Compare Designs

```python
# Compare two live pages (compare() takes URLs or already-captured
# screenshots directly; for local HTML files, call capture() first)
result = await lens.compare([
    "https://old-design.com",
    "https://new-design.com"
], "Which design is more user-friendly?")
```

## 📱 Built-in Checks

### Mobile-Friendly Check
```python
result = await lens.check_mobile_friendly("https://your-site.com")
```

### Accessibility Check
```python
result = await lens.check_accessibility("https://your-site.com")  # mode="hybrid" by default
```

### Conversion Optimization
```python
result = await lens.check_conversion_optimization("https://your-site.com")
```

## 🤖 CI Integration

There is no bundled GitHub composite action — call the CLI directly in your
workflow:

```yaml
name: UI Quality Check

on: [pull_request]

jobs:
  ui-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install LayoutLens
        run: |
          pip install layoutlens
          playwright install chromium

      - name: Deterministic accessibility check (no API key needed)
        run: layoutlens ${{ env.PREVIEW_URL }} --a11y axe

      - name: AI quality check
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          layoutlens ${{ env.PREVIEW_URL }} "Is the layout professional and trustworthy?"
```

## 🎯 Common Use Cases

### E-commerce Testing
```python
queries = [
    "Is the 'Add to Cart' button prominent and trustworthy?",
    "Does the checkout process look simple?",
    "Are product images clear and appealing?"
]
```

### SaaS Dashboard Testing
```python
queries = [
    "Is the dashboard easy to navigate for new users?",
    "Are the data visualizations clear?",
    "Is the overall layout professional?"
]
```

### Blog/Content Testing
```python
queries = [
    "Is the article easy to read?",
    "Is the navigation helpful?",
    "Does the layout encourage engagement?"
]
```

## ⚡ Advanced Usage

### Batch Analysis
`analyze()` handles single or multiple sources/queries directly — pass lists
to fan out concurrently:
```python
urls = ["https://page1.com", "https://page2.com", "https://page3.com"]
queries = ["Is navigation consistent?", "Is mobile experience good?"]

result = await lens.analyze(source=urls, query=queries)  # returns a BatchResult
print(f"Average confidence: {result.average_confidence:.1%}")
```

### Cross-Browser Testing
```python
# Compare pre-captured screenshots from different browsers
result = await lens.compare(
    sources=["chrome.png", "firefox.png", "safari.png"],
    query="Are these layouts consistent across browsers?"
)
```

### Custom Context
```python
result = await lens.analyze(
    "https://app.com/dashboard",
    "Is this suitable for elderly users?",
    context={
        "user_type": "elderly",
        "accessibility": True,
    }
)
```

### YAML Test Suites
Every test case requires `expected_results` (breaking change in v1.7.0 — see
the main [README](https://github.com/gojiplus/layoutlens#8-yaml-test-suites)
for the full schema):
```python
import yaml
from layoutlens import LayoutLens, UITestSuite

with open("test_suite.yaml") as f:
    suite = UITestSuite.from_dict(yaml.safe_load(f))

lens = LayoutLens()
results = await lens.run_test_suite(suite)
```

## 🎨 Customization

### Custom Queries for Your Domain

**E-commerce:**
- "Does this product page increase purchase confidence?"
- "Is the pricing clear and competitive-looking?"
- "Are trust signals visible (security, reviews, guarantees)?"

**SaaS:**
- "Would new users understand how to get started?"
- "Are upgrade prompts balanced (not annoying)?"
- "Is the feature hierarchy clear?"

**Content:**
- "Is this article layout engaging and readable?"
- "Are social sharing options visible?"
- "Does the design encourage newsletter signup?"

## 🔧 Troubleshooting

### Common Issues

**"API key required" error:**
```bash
export OPENAI_API_KEY="sk-your-key"
# Or pass directly: LayoutLens(api_key="sk-your-key")
```
This only happens when an LLM call is actually made — `LayoutLens()`
construction and `mode="axe"` accessibility checks never require a key.

**Playwright install error:**
```bash
playwright install chromium
```

**Screenshot capture fails:**
- Check the URL is accessible
- Try with `wait_time` parameter for slow-loading pages

**"You uploaded an unsupported image" error from `compare()`:**
`compare()` expects URLs or already-captured screenshot paths. Passing a raw
local `.html` path skips screenshot rendering — call `await lens.capture(...)`
first and pass the resulting screenshot paths to `compare()`.

### Getting Help

- 📖 [Full Documentation](https://gojiplus.github.io/layoutlens/)
- 🐛 [Report Issues](https://github.com/gojiplus/layoutlens/issues)
- 💬 [Discussions](https://github.com/gojiplus/layoutlens/discussions)

## 🎯 Next Steps

1. **Try the examples** in `examples/` (e.g. `python examples/simple_api_usage.py`)
2. **Set up CI** for your repository
3. **Customize queries** for your specific use case
4. **Integrate with your deployment pipeline**

---

**Ready to improve your UI quality with AI?** Start with a simple analysis and expand from there! 🚀
