# LayoutLens Quick Start Guide

Get started with AI-powered UI testing in 5 minutes.

## 🚀 Installation

```bash
pip install layoutlens
playwright install  # For URL capture
```

## 🔑 Setup

```bash
export OPENAI_API_KEY="sk-your-openai-key"
```

*Get your API key from [OpenAI Platform](https://platform.openai.com/api-keys)*

## 💡 Basic Usage

### Analyze a Website

```python
from layoutlens import LayoutLens

lens = LayoutLens()

# Test any live website
result = lens.analyze(
    "https://your-website.com",
    "Is the navigation easy to use?"
)

print(f"Answer: {result.answer}")
print(f"Confidence: {result.confidence:.1%}")
```

### Analyze Screenshots

```python
# Test uploaded images
result = lens.analyze(
    "screenshot.png",
    "Are the buttons large enough for mobile users?"
)
```

### Compare Designs

```python
# Compare before/after
result = lens.compare([
    "https://old-design.com",
    "https://new-design.com"
], "Which design is more user-friendly?")
```

## 📱 Built-in Checks

### Mobile-Friendly Check
```python
result = lens.check_mobile_friendly("https://your-site.com")
```

### Accessibility Check  
```python
result = lens.check_accessibility("https://your-site.com")
```

### Conversion Optimization
```python
result = lens.check_conversion_optimization("https://your-site.com")
```

## 🤖 GitHub Actions Integration

### 1. Add to Your Workflow

Create `.github/workflows/ui-quality.yml`:

```yaml
name: UI Quality Check

on: [pull_request]

jobs:
  ui-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Test UI Quality
        uses: your-org/layoutlens/.github/actions/layoutlens@v1
        with:
          url: ${{ env.PREVIEW_URL }}
          openai_api_key: ${{ secrets.OPENAI_API_KEY }}
          queries: |
            - "Is the layout professional and trustworthy?"
            - "Are there any obvious usability issues?"
            - "Does this work well on mobile?"
```

### 2. Add API Key to Secrets

1. Go to your repository Settings → Secrets
2. Add `OPENAI_API_KEY` with your OpenAI API key

### 3. Test with a Pull Request

The action will automatically:
- ✅ Capture screenshots from your preview URL
- 🤖 Analyze with AI using your queries  
- 💬 Comment on the PR with results
- ❌ Fail the check if quality is below threshold

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
```python
# Test multiple pages with multiple questions
urls = ["page1.com", "page2.com", "page3.com"]
queries = ["Is navigation consistent?", "Is mobile experience good?"]

result = lens.analyze_batch(urls, queries)
print(f"Average score: {result.average_confidence:.1%}")
```

### Cross-Browser Testing
```python
from layoutlens.vision import LayoutComparator

comparator = LayoutComparator(lens.analyzer)

# Screenshots from different browsers
result = comparator.check_cross_browser_consistency(
    ["chrome.png", "firefox.png", "safari.png"],
    ["Chrome", "Firefox", "Safari"]
)
```

### Custom Context
```python
result = lens.analyze(
    "https://app.com/dashboard",
    "Is this suitable for elderly users?",
    context={
        "user_type": "elderly",
        "accessibility": True,
        "viewport": "desktop"
    }
)
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

**"No API key" error:**
```bash
export OPENAI_API_KEY="sk-your-key"
# Or pass directly: LayoutLens(api_key="sk-your-key")
```

**Playwright install error:**
```bash
playwright install chromium
```

**Screenshot capture fails:**
- Check URL is accessible
- Try with `wait_time` parameter for slow loading pages

### Getting Help

- 📖 [Full Documentation](./README.md)
- 🐛 [Report Issues](https://github.com/your-org/layoutlens/issues)
- 💬 [Discussions](https://github.com/your-org/layoutlens/discussions)

## 🎯 Next Steps

1. **Try the examples** in `examples/simple_api_usage.py`
2. **Set up GitHub Actions** for your repository
3. **Customize queries** for your specific use case
4. **Integrate with your deployment pipeline**

---

**Ready to improve your UI quality with AI?** Start with a simple analysis and expand from there! 🚀