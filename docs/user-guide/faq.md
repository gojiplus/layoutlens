# Frequently Asked Questions

## General Questions

### What is LayoutLens?

LayoutLens is an AI-powered UI testing framework that allows you to write visual tests using natural language. Instead of writing complex assertions about pixel positions or element properties, you can ask questions like "Is the navigation menu clearly visible?" or "Does the layout look good on mobile?" and get AI-powered answers.

### How does LayoutLens work?

LayoutLens works by:
1. **Taking screenshots** of your HTML pages using Playwright
2. **Analyzing the DOM** to understand page structure and generate relevant test queries
3. **Using AI vision models** (currently OpenAI's GPT-4 Vision) to analyze screenshots and answer natural language questions
4. **Aggregating results** into comprehensive test reports

### What types of testing can LayoutLens do?

LayoutLens excels at:
- **Visual regression testing** - Comparing layouts across versions
- **Responsive design validation** - Testing across multiple viewports
- **Accessibility assessment** - Checking color contrast, readability, and usability
- **Cross-page consistency** - Ensuring design system compliance
- **User experience evaluation** - Assessing clarity and usability

## Getting Started

### Do I need an OpenAI API key?

Yes, LayoutLens currently requires an OpenAI API key to power the AI vision analysis. You can:
- Get a key from [OpenAI's platform](https://platform.openai.com/api-keys)
- Set usage limits to control costs
- Use environment variables to manage the key securely

### How much does it cost to use LayoutLens?

The cost depends on your OpenAI API usage:
- **gpt-4o-mini**: ~$0.01-0.02 per test query (recommended for most use cases)
- **gpt-4o**: ~$0.05-0.10 per test query (higher accuracy for complex scenarios)

For typical usage:
- Single page with 5 queries: ~$0.05-0.50
- Complete website test (20 pages): ~$1-10
- Regular CI/CD testing: ~$10-50/month

### Can I use LayoutLens without AI/OpenAI?

Currently, the AI vision analysis is core to LayoutLens functionality. However:
- You can use LayoutLens for **screenshot generation only** by setting `--skip-model` in CLI
- The framework captures valuable metadata and DOM analysis even without AI
- Future versions may support additional AI providers or local models

### What browsers does LayoutLens support?

LayoutLens uses Playwright and primarily supports:
- **Chromium** (default, recommended)
- **Firefox** (supported)
- **WebKit** (Safari engine, supported)

Chromium provides the most consistent results and is recommended for most testing scenarios.

## Technical Questions

### What file formats does LayoutLens accept?

LayoutLens works with:
- **HTML files** (.html, .htm) - Primary input format
- **URLs** - Can test live websites (future feature)
- **Static sites** - Works with any static HTML content
- **Dynamic content** - Screenshots capture rendered state

### Can LayoutLens test dynamic/JavaScript applications?

Yes! LayoutLens uses Playwright which:
- Executes JavaScript and renders dynamic content
- Waits for page load completion
- Captures the final rendered state
- Supports single-page applications (SPAs)

Configure wait times for complex applications:
```python
tester = LayoutLens()
result = tester.test_page(
    "spa-app.html",
    wait_for_load=5,  # Wait 5 seconds for JS to complete
    queries=["Is the dynamic content loaded correctly?"]
)
```

### How accurate are the AI results?

AI accuracy depends on several factors:
- **Query clarity**: Specific questions get better answers
- **Model used**: gpt-4o is more accurate than gpt-4o-mini
- **Visual complexity**: Simple layouts are analyzed more reliably
- **Context**: Better results with clear, well-designed interfaces

Typical accuracy rates:
- **Clear, specific queries**: 85-95% accuracy
- **Subjective assessments**: 70-85% accuracy
- **Complex layouts**: 75-90% accuracy

### Can I use LayoutLens in CI/CD pipelines?

Absolutely! LayoutLens is designed for CI/CD integration:

```yaml
# GitHub Actions example
- name: Run UI Tests
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
  run: |
    layoutlens test --suite ui-tests.yaml --fail-fast --format junit
```

Best practices for CI/CD:
- Use `gpt-4o-mini` for speed and cost efficiency
- Set appropriate timeouts
- Use `--fail-fast` to stop on first failure
- Generate JUnit XML for integration with CI systems

### How do I handle flaky tests?

Reduce test flakiness by:

1. **Using consistent queries**:
```python
# Good: Specific, measurable
"Is the navigation menu positioned at the top of the page?"

# Avoid: Subjective or vague
"Does this look good?"
```

2. **Setting appropriate wait times**:
```python
config.screenshots.wait_for_load = 3  # Wait for dynamic content
```

3. **Using retry mechanisms**:
```python
config.testing.retry_failed = 2  # Retry failed tests
```

4. **Controlling AI temperature**:
```python
config.llm.temperature = 0.1  # Lower = more consistent
```

## Usage and Configuration

### How do I test responsive design?

Test across multiple viewports:

```python
from layoutlens import LayoutLens

tester = LayoutLens()
result = tester.test_page(
    "responsive-page.html",
    viewports=["desktop", "tablet_portrait", "mobile_portrait", "mobile_landscape"],
    queries=[
        "Does the layout adapt appropriately to the screen size?",
        "Are buttons and text appropriately sized for touch interaction?",
        "Is all content accessible without horizontal scrolling?"
    ]
)

# Analyze results by viewport
for test_result in result.test_results:
    print(f"{test_result.viewport}: {test_result.query}")
    print(f"Result: {test_result.answer}")
    print("---")
```

### How do I write good test queries?

**Effective queries are**:
- **Specific**: "Is the search button visible in the top navigation?" vs "Is everything visible?"
- **Actionable**: Focus on user-facing functionality
- **Measurable**: Ask about concrete visual elements
- **Context-aware**: Reference specific page areas or components

**Examples of good queries**:
```python
good_queries = [
    "Is the main navigation menu clearly visible at the top of the page?",
    "Are product images displayed at adequate size for viewing details?",
    "Is the 'Add to Cart' button prominently positioned and easily clickable?",
    "Does the page layout maintain readability when viewed on mobile devices?",
    "Are form labels clearly associated with their input fields?",
    "Is the color contrast sufficient for text readability?"
]
```

### How do I organize large test suites?

Use hierarchical organization:

```yaml
# ui-tests.yaml
name: "Complete Site Test Suite"
description: "Comprehensive UI testing"

# Organize by page type
test_cases:
  # Homepage tests
  - name: "Homepage Desktop"
    html_path: "pages/homepage.html"
    viewports: ["desktop"]
    tags: ["homepage", "desktop"]
    
  - name: "Homepage Mobile"
    html_path: "pages/homepage.html" 
    viewports: ["mobile_portrait"]
    tags: ["homepage", "mobile"]
    
  # Product page tests
  - name: "Product Page Layout"
    html_path: "pages/product.html"
    tags: ["product", "layout"]
    
  # Checkout flow tests
  - name: "Checkout Process"
    html_path: "pages/checkout.html"
    tags: ["checkout", "conversion"]
```

Run specific test groups:
```bash
# Run only mobile tests
layoutlens test --suite ui-tests.yaml --tags mobile

# Run only homepage tests
layoutlens test --suite ui-tests.yaml --tags homepage
```

### Can I customize the AI model or provider?

Currently, LayoutLens supports OpenAI models:
- **gpt-4o-mini** (default): Fast, cost-effective, good accuracy
- **gpt-4o**: Higher accuracy, more expensive, slower
- **gpt-4-turbo**: Alternative option with different performance characteristics

```python
# Configure different models
from layoutlens import Config, LayoutLens

config = Config()
config.llm.model = "gpt-4o"  # Use higher accuracy model
config.llm.temperature = 0.05  # More consistent results

tester = LayoutLens(config=config)
```

Future versions may support:
- Additional OpenAI models
- Anthropic Claude
- Local/self-hosted models
- Custom model endpoints

## Troubleshooting

### LayoutLens is running slowly. How can I speed it up?

Speed optimization strategies:

1. **Use faster AI models**:
```python
config.llm.model = "gpt-4o-mini"  # Fastest option
```

2. **Enable parallel processing**:
```python
config.testing.parallel = True
config.testing.max_workers = 4
```

3. **Reduce screenshot resolution**:
```python
config.screenshots.device_scale_factor = 1  # Lower resolution
config.screenshots.quality = 80  # For JPEG format
```

4. **Limit viewports and queries**:
```python
# Test fewer viewports
result = tester.test_page("page.html", viewports=["desktop"])

# Use fewer, more targeted queries
queries = ["Is the main content clearly visible?"]  # Instead of 10+ queries
```

5. **Use batch processing**:
```python
# Process pages in efficient batches
pages = ["page1.html", "page2.html", "page3.html"]
results = tester.test_multiple_pages(pages, parallel=True)
```

### I'm getting API errors. What should I check?

Common API issues and solutions:

1. **Rate limiting**:
```bash
# Check your OpenAI usage dashboard
# Implement delays between requests
LAYOUTLENS_LLM_TIMEOUT=60 layoutlens test --page page.html
```

2. **API key issues**:
```bash
# Verify API key is set correctly
echo $OPENAI_API_KEY

# Test API key directly
python -c "
import openai
client = openai.OpenAI(api_key='your-key-here')
print(client.models.list())
"
```

3. **Network connectivity**:
```bash
# Test connection to OpenAI
curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models

# Check proxy settings if behind corporate firewall
```

4. **Quota exceeded**:
- Check your OpenAI billing dashboard
- Set usage limits in OpenAI dashboard
- Implement retry logic with exponential backoff

### Screenshots aren't capturing correctly. What's wrong?

Screenshot troubleshooting:

1. **Browser installation**:
```bash
playwright install chromium --force
playwright --version
```

2. **Page loading issues**:
```python
# Increase wait time for complex pages
config.screenshots.wait_for_load = 10
config.screenshots.timeout = 60000  # 60 seconds
```

3. **File path issues**:
```python
# Use absolute paths
import os
html_path = os.path.abspath("pages/homepage.html")
result = tester.test_page(html_path)
```

4. **Permissions or access issues**:
```bash
# Check file permissions
ls -la pages/homepage.html

# Ensure Playwright can access the file
file://$(pwd)/pages/homepage.html
```

### The AI is giving inconsistent results. How can I make it more reliable?

Improve AI consistency:

1. **Lower temperature setting**:
```python
config.llm.temperature = 0.0  # Most consistent
```

2. **Use more specific queries**:
```python
# Specific and measurable
"Is the search button located in the top-right corner of the navigation bar?"

# Instead of subjective
"Does the search look good?"
```

3. **Provide more context**:
```python
queries = [
    "Looking at this e-commerce product page, is the 'Add to Cart' button prominently positioned and clearly labeled?",
    "In the context of mobile usability, are the form fields appropriately sized for touch input?"
]
```

4. **Use higher quality models for critical tests**:
```python
config.llm.model = "gpt-4o"  # Higher accuracy for important tests
```

5. **Implement retry logic**:
```python
config.testing.retry_failed = 2  # Retry inconsistent results
```

## Best Practices

### What are the recommended settings for different environments?

**Development Environment**:
```yaml
llm:
  model: "gpt-4o-mini"
  temperature: 0.1
testing:
  parallel: false  # Easier debugging
  retry_failed: 0
output:
  verbose: true
  save_screenshots: true
logging:
  level: "DEBUG"
```

**CI/CD Environment**:
```yaml
llm:
  model: "gpt-4o-mini"
  temperature: 0.0
testing:
  parallel: true
  max_workers: 2
  fail_fast: true
  retry_failed: 0
output:
  formats: ["junit"]
  verbose: false
  save_screenshots: false
```

**Production Monitoring**:
```yaml
llm:
  model: "gpt-4o"
  temperature: 0.05
testing:
  parallel: true
  retry_failed: 2
output:
  formats: ["json", "html"]
  save_screenshots: true
logging:
  level: "INFO"
  file: "./logs/layoutlens.log"
```

### How do I integrate LayoutLens with existing testing frameworks?

**With pytest**:
```python
import pytest
from layoutlens import LayoutLens

@pytest.fixture(scope="session")
def ui_tester():
    return LayoutLens()

def test_homepage_ui(ui_tester):
    result = ui_tester.test_page("homepage.html")
    assert result.success_rate >= 0.8
```

**With Jest/JavaScript** (via CLI):
```javascript
const { execSync } = require('child_process');

test('UI tests pass', () => {
  const result = execSync('layoutlens test --suite ui-tests.yaml --format json');
  const testResults = JSON.parse(result.toString());
  expect(testResults.success_rate).toBeGreaterThanOrEqual(0.8);
});
```

**With Selenium/existing UI tests**:
```python
from selenium import webdriver
from layoutlens import LayoutLens

# Generate HTML from Selenium test
driver = webdriver.Chrome()
driver.get("https://mysite.com")

# Save current page state
with open("current_page.html", "w") as f:
    f.write(driver.page_source)

# Test with LayoutLens
tester = LayoutLens()
result = tester.test_page("current_page.html")

driver.quit()
```

## Support and Community

### Where can I get help?

1. **Documentation**: Check the [User Guide](../user-guide/) and [API Documentation](../api/)
2. **GitHub Issues**: [Report bugs and request features](https://github.com/matmulai/layoutlens/issues)
3. **GitHub Discussions**: [Ask questions and share experiences](https://github.com/matmulai/layoutlens/discussions)
4. **Examples**: Review the [examples directory](../../examples/) for working code

### How can I contribute to LayoutLens?

We welcome contributions! See the [Contributing Guide](../developer-guide/contributing.md) for:
- Code contributions and bug fixes
- Documentation improvements
- New feature suggestions
- Community support

### Is there a roadmap for future features?

Planned features include:
- Additional AI providers (Anthropic Claude, local models)
- URL testing (live websites)
- Advanced accessibility testing
- Performance integration
- Visual diff reporting
- Plugin system for custom analyzers

Check the [GitHub Issues](https://github.com/matmulai/layoutlens/issues) for the latest roadmap and feature requests.

### Can I use LayoutLens commercially?

Yes! LayoutLens is released under the MIT License, which allows commercial use. Just remember:
- You're responsible for OpenAI API costs
- Ensure compliance with OpenAI's terms of service
- Consider data privacy implications when testing sensitive content

---

**Still have questions?** 

Open a discussion on [GitHub Discussions](https://github.com/matmulai/layoutlens/discussions) or check the [issue tracker](https://github.com/matmulai/layoutlens/issues) for similar questions.