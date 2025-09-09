# Examples and Usage Patterns

This guide provides practical examples and common usage patterns for LayoutLens in various scenarios.

## Basic Examples

### Single Page Testing

Test a single HTML page with natural language queries:

```python
from layoutlens import LayoutLens

# Initialize tester
tester = LayoutLens(api_key="your-api-key")

# Test with custom queries
result = tester.test_page(
    html_path="homepage.html",
    queries=[
        "Is the navigation menu clearly visible?",
        "Is the main content area properly centered?",
        "Are the call-to-action buttons prominent?"
    ],
    viewports=["desktop", "mobile_portrait"]
)

# Check results
print(f"Success rate: {result.success_rate:.2%}")
print(f"Tests passed: {result.passed_tests}/{result.total_tests}")

# Examine individual results
for test_result in result.test_results:
    print(f"Query: {test_result.query}")
    print(f"Answer: {test_result.answer}")
    print(f"Passed: {'✓' if test_result.answer.lower().startswith('yes') else '✗'}")
    print("---")
```

### Automatic Query Generation

Let LayoutLens analyze your HTML and generate appropriate test queries:

```python
from layoutlens import LayoutLens

tester = LayoutLens()

# Auto-generate queries based on HTML analysis
result = tester.test_page(
    html_path="ecommerce-product.html",
    auto_generate_queries=True,  # This is the default
    viewports=["desktop", "tablet_portrait", "mobile_portrait"]
)

# Review generated queries and results
for test_result in result.test_results:
    print(f"Generated Query: {test_result.query}")
    print(f"Category: {test_result.category}")
    print(f"Result: {test_result.answer}")
    print()
```

### Page Comparison

Compare two versions of a page to detect visual differences:

```python
from layoutlens import LayoutLens

tester = LayoutLens()

# Compare before and after versions
comparison = tester.compare_pages(
    page_a_path="designs/v1/homepage.html",
    page_b_path="designs/v2/homepage.html",
    viewport="desktop",
    query="Are the layouts visually consistent? Are there any significant changes?"
)

print(f"Comparison: {comparison['answer']}")
print(f"Screenshots saved: {comparison['screenshot_a']}, {comparison['screenshot_b']}")
```

## Test Suites

### YAML Test Suite

Create organized test suites with YAML configuration:

```yaml
# ui-tests.yaml
name: "E-commerce Site UI Tests"
description: "Comprehensive UI testing for online store"
version: "1.0"

defaults:
  viewports: ["desktop", "mobile_portrait"]
  auto_generate_queries: true

test_cases:
  - name: "Homepage Layout"
    html_path: "pages/homepage.html"
    queries:
      - "Is the hero section visually striking?"
      - "Is the product grid properly aligned?"
      - "Is the search bar easily discoverable?"
    tags: ["homepage", "layout"]
    
  - name: "Product Page Functionality"
    html_path: "pages/product.html"
    queries:
      - "Are product images prominently displayed?"
      - "Is the 'Add to Cart' button clearly visible?"
      - "Is pricing information clear and prominent?"
    tags: ["product", "conversion"]
    
  - name: "Mobile Responsiveness"
    html_path: "pages/checkout.html"
    viewports: ["mobile_portrait", "mobile_landscape"]
    queries:
      - "Is the checkout form easy to use on mobile?"
      - "Are form fields appropriately sized for touch input?"
      - "Is the checkout button easily accessible?"
    tags: ["mobile", "checkout", "responsive"]
```

Run the test suite:

```python
from layoutlens import LayoutLens

tester = LayoutLens()

# Run complete test suite
results = tester.run_test_suite("ui-tests.yaml")

# Print summary
print(f"Suite: {results.name}")
print(f"Total tests: {results.total_tests}")
print(f"Passed: {results.passed_tests}")
print(f"Success rate: {results.success_rate:.2%}")

# Examine failed tests
for test_case in results.test_cases:
    if test_case.failed_tests > 0:
        print(f"Failed test case: {test_case.name}")
        for result in test_case.test_results:
            if not result.passed:
                print(f"  - {result.query}: {result.answer}")
```

### Programmatic Test Suite

Create test suites programmatically:

```python
from layoutlens import LayoutLens, TestSuite, TestCase

# Create test suite
suite = TestSuite(
    name="Accessibility Test Suite",
    description="Testing UI accessibility compliance"
)

# Add test cases
suite.add_test_case(TestCase(
    name="Color Contrast",
    html_path="pages/article.html",
    queries=[
        "Is the text readable with sufficient color contrast?",
        "Are links visually distinguishable from regular text?",
        "Is important information not conveyed by color alone?"
    ],
    tags=["a11y", "color"]
))

suite.add_test_case(TestCase(
    name="Keyboard Navigation",
    html_path="pages/navigation.html",
    queries=[
        "Are all interactive elements keyboard accessible?",
        "Is there a clear focus indicator for keyboard users?",
        "Is the tab order logical and intuitive?"
    ],
    tags=["a11y", "keyboard"]
))

# Run the suite
tester = LayoutLens()
results = tester.run_test_suite(suite)
```

## Advanced Usage

### Multi-Viewport Testing

Test responsive design across multiple device sizes:

```python
from layoutlens import LayoutLens
from layoutlens.config import ViewportConfig

# Define custom viewports
custom_viewports = [
    ViewportConfig(name="desktop_hd", width=1920, height=1080),
    ViewportConfig(name="laptop", width=1366, height=768),
    ViewportConfig(name="tablet", width=768, height=1024),
    ViewportConfig(name="mobile_large", width=414, height=896),
    ViewportConfig(name="mobile_small", width=375, height=667)
]

tester = LayoutLens()

result = tester.test_page(
    html_path="responsive-landing.html",
    viewports=custom_viewports,
    queries=[
        "Does the layout adapt appropriately to different screen sizes?",
        "Are text and buttons appropriately sized for the viewport?",
        "Is the navigation usable at this screen size?",
        "Are images properly scaled and positioned?"
    ]
)

# Analyze results by viewport
viewport_results = {}
for test_result in result.test_results:
    viewport = test_result.viewport
    if viewport not in viewport_results:
        viewport_results[viewport] = []
    viewport_results[viewport].append(test_result)

for viewport, tests in viewport_results.items():
    passed = sum(1 for test in tests if test.passed)
    total = len(tests)
    print(f"{viewport}: {passed}/{total} tests passed ({passed/total:.1%})")
```

### Batch Processing

Test multiple pages efficiently:

```python
import os
from pathlib import Path
from layoutlens import LayoutLens

def test_website_pages(pages_directory, output_directory="results"):
    """Test all HTML pages in a directory."""
    tester = LayoutLens()
    html_files = list(Path(pages_directory).glob("**/*.html"))
    
    print(f"Found {len(html_files)} HTML files to test")
    
    results = []
    for i, html_file in enumerate(html_files):
        print(f"[{i+1}/{len(html_files)}] Testing {html_file.name}")
        
        try:
            result = tester.test_page(
                html_path=str(html_file),
                auto_generate_queries=True,
                viewports=["desktop", "mobile_portrait"]
            )
            results.append({
                "file": html_file.name,
                "success_rate": result.success_rate,
                "total_tests": result.total_tests,
                "passed_tests": result.passed_tests
            })
            
        except Exception as e:
            print(f"  Error testing {html_file.name}: {e}")
            results.append({
                "file": html_file.name,
                "error": str(e)
            })
    
    # Save summary report
    summary_file = Path(output_directory) / "batch_test_summary.json"
    summary_file.parent.mkdir(exist_ok=True)
    
    import json
    with open(summary_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"Batch testing complete. Summary saved to {summary_file}")
    return results

# Usage
results = test_website_pages("./website/pages", "./test-results")
```

### Configuration-Based Testing

Use configuration files for consistent testing:

```python
from layoutlens import LayoutLens, Config

# Load configuration from file
config = Config.from_file("ui-testing-config.yaml")

# Override specific settings
config.llm.model = "gpt-4o"  # Use higher quality model
config.testing.parallel = True
config.testing.max_workers = 4

# Create tester with configuration
tester = LayoutLens(config=config)

# All tests will use the configuration settings
result = tester.test_page("complex-dashboard.html")
```

## Specific Use Cases

### E-commerce Testing

Test online store interfaces:

```python
from layoutlens import LayoutLens

def test_ecommerce_site():
    tester = LayoutLens()
    
    # Product listing page
    catalog_result = tester.test_page(
        "ecommerce/catalog.html",
        queries=[
            "Are product thumbnails clearly visible and appealing?",
            "Is the product grid layout organized and scannable?",
            "Are prices prominently displayed?",
            "Is the filtering/sorting interface intuitive?",
            "Are 'Add to Cart' buttons clearly visible?"
        ],
        viewports=["desktop", "tablet_portrait", "mobile_portrait"]
    )
    
    # Individual product page
    product_result = tester.test_page(
        "ecommerce/product-detail.html",
        queries=[
            "Are product images large and detailed enough?",
            "Is product information clearly organized?",
            "Is the 'Add to Cart' button prominent and trustworthy?",
            "Are shipping and return policies easily accessible?",
            "Do reviews and ratings appear credible?"
        ]
    )
    
    # Checkout process
    checkout_result = tester.test_page(
        "ecommerce/checkout.html",
        queries=[
            "Is the checkout form clear and straightforward?",
            "Are security indicators visible (SSL, payment badges)?",
            "Is the order summary easy to understand?",
            "Are error messages helpful and clear?",
            "Does the page inspire confidence for completing purchase?"
        ]
    )
    
    return {
        "catalog": catalog_result,
        "product": product_result, 
        "checkout": checkout_result
    }

results = test_ecommerce_site()
for page, result in results.items():
    print(f"{page.title()}: {result.success_rate:.1%} success rate")
```

### Accessibility Testing

Focus on accessibility compliance:

```python
from layoutlens import LayoutLens

def test_accessibility(html_file):
    tester = LayoutLens()
    
    result = tester.test_page(
        html_file,
        queries=[
            # Color and Contrast
            "Is text readable with sufficient color contrast?",
            "Is important information conveyed without relying solely on color?",
            
            # Navigation and Focus
            "Are interactive elements clearly identifiable?",
            "Is there a logical reading and navigation order?",
            "Are focus indicators visible for keyboard navigation?",
            
            # Content Structure
            "Is the page structure clear with proper headings?",
            "Are form labels clearly associated with their inputs?",
            "Is alternative text available for images?",
            
            # Mobile Accessibility
            "Are touch targets appropriately sized (44px minimum)?",
            "Is the page usable when zoomed to 200%?",
            "Is content accessible without horizontal scrolling?"
        ]
    )
    
    # Categorize results
    accessibility_score = {}
    for test_result in result.test_results:
        category = "general"
        if "color" in test_result.query.lower():
            category = "color_contrast"
        elif "focus" in test_result.query.lower() or "keyboard" in test_result.query.lower():
            category = "keyboard_navigation"
        elif "heading" in test_result.query.lower() or "structure" in test_result.query.lower():
            category = "content_structure"
        elif "touch" in test_result.query.lower() or "zoom" in test_result.query.lower():
            category = "mobile_accessibility"
        
        if category not in accessibility_score:
            accessibility_score[category] = {"passed": 0, "total": 0}
        
        accessibility_score[category]["total"] += 1
        if test_result.passed:
            accessibility_score[category]["passed"] += 1
    
    return accessibility_score

# Usage
accessibility_results = test_accessibility("website/home.html")
for category, scores in accessibility_results.items():
    rate = scores["passed"] / scores["total"]
    print(f"{category.replace('_', ' ').title()}: {rate:.1%}")
```

### Design System Validation

Test component library consistency:

```python
from layoutlens import LayoutLens
import glob

def validate_design_system(components_dir="components"):
    """Validate design system components for consistency."""
    tester = LayoutLens()
    
    component_files = glob.glob(f"{components_dir}/**/*.html", recursive=True)
    consistency_results = {}
    
    # Test each component
    for component_file in component_files:
        component_name = Path(component_file).stem
        
        result = tester.test_page(
            component_file,
            queries=[
                "Does this component follow the established visual design patterns?",
                "Are colors consistent with the design system palette?",
                "Are typography styles (fonts, sizes, spacing) consistent?",
                "Are interactive states (hover, focus) properly styled?",
                "Does the component scale appropriately across viewports?"
            ]
        )
        
        consistency_results[component_name] = result
    
    # Cross-component comparison
    button_files = [f for f in component_files if "button" in f.lower()]
    if len(button_files) > 1:
        for i, button_a in enumerate(button_files):
            for button_b in button_files[i+1:]:
                comparison = tester.compare_pages(
                    button_a, button_b,
                    query="Do these button components follow the same visual design patterns?"
                )
                print(f"Button consistency check: {Path(button_a).stem} vs {Path(button_b).stem}")
                print(f"Result: {comparison['answer']}")
    
    return consistency_results

# Usage
design_system_results = validate_design_system("./design-system/components")
```

### Performance-Aware Testing

Test with performance considerations:

```python
import time
from layoutlens import LayoutLens

def performance_aware_testing(pages, max_concurrent=2):
    """Test pages with performance monitoring."""
    tester = LayoutLens()
    
    results = []
    start_time = time.time()
    
    for i, page in enumerate(pages):
        page_start = time.time()
        
        try:
            result = tester.test_page(
                page,
                queries=["Is the page layout clear and functional?"],
                viewports=["desktop"]  # Single viewport for speed
            )
            
            page_time = time.time() - page_start
            
            results.append({
                "page": page,
                "success_rate": result.success_rate,
                "test_time": page_time,
                "screenshot_count": len(result.screenshots)
            })
            
            print(f"[{i+1}/{len(pages)}] {page}: {result.success_rate:.1%} ({page_time:.1f}s)")
            
            # Rate limiting
            if i > 0 and i % max_concurrent == 0:
                time.sleep(1)  # Brief pause between batches
                
        except Exception as e:
            print(f"Error testing {page}: {e}")
    
    total_time = time.time() - start_time
    print(f"\nTotal testing time: {total_time:.1f}s")
    print(f"Average per page: {total_time/len(pages):.1f}s")
    
    return results

# Usage
pages = ["home.html", "about.html", "contact.html", "products.html"]
perf_results = performance_aware_testing(pages)
```

## Integration Examples

### CI/CD Integration

GitHub Actions workflow:

```yaml
# .github/workflows/ui-tests.yml
name: UI Tests

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  ui-tests:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
        
    - name: Install dependencies
      run: |
        pip install layoutlens
        playwright install chromium
        
    - name: Run UI tests
      env:
        OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      run: |
        layoutlens test --suite .github/ui-tests.yaml \
          --format junit \
          --output-dir test-results \
          --fail-fast
          
    - name: Publish test results
      uses: dorny/test-reporter@v1
      if: always()
      with:
        name: UI Test Results
        path: test-results/*.xml
        reporter: java-junit
```

### Pytest Integration

Use LayoutLens within pytest framework:

```python
# test_ui.py
import pytest
from layoutlens import LayoutLens

@pytest.fixture(scope="session")
def ui_tester():
    """Shared LayoutLens instance for all tests."""
    return LayoutLens()

class TestHomepage:
    def test_homepage_desktop(self, ui_tester):
        """Test homepage on desktop viewport."""
        result = ui_tester.test_page(
            "pages/homepage.html",
            queries=["Is the navigation clearly visible?"],
            viewports=["desktop"]
        )
        assert result.success_rate >= 0.8, "Homepage desktop tests failed"
    
    def test_homepage_mobile(self, ui_tester):
        """Test homepage on mobile viewport.""" 
        result = ui_tester.test_page(
            "pages/homepage.html",
            queries=["Is the mobile menu accessible?"],
            viewports=["mobile_portrait"]
        )
        assert result.success_rate >= 0.8, "Homepage mobile tests failed"

class TestComparison:
    def test_design_consistency(self, ui_tester):
        """Test that design variations are consistent."""
        comparison = ui_tester.compare_pages(
            "designs/v1.html",
            "designs/v2.html",
            query="Are these designs visually consistent?"
        )
        
        # Check if LLM indicates consistency
        assert "consistent" in comparison["answer"].lower(), \
            f"Design inconsistency detected: {comparison['answer']}"

# Run with: pytest test_ui.py -v
```

## Best Practices

### Efficient Query Design

Write effective test queries:

```python
# Good: Specific, actionable queries
good_queries = [
    "Is the primary navigation menu visible and accessible at the top of the page?",
    "Are product images displayed with adequate size and quality?",
    "Is the 'Add to Cart' button prominently positioned and clearly labeled?",
    "Does the page layout maintain readability on mobile devices?"
]

# Avoid: Vague or overly broad queries
avoid_queries = [
    "Does this look good?",  # Too subjective
    "Is everything working?",  # Too broad
    "Are there any problems?",  # Negative framing
]

# Best practice: Use specific, measurable criteria
result = tester.test_page(
    "product.html",
    queries=good_queries,
    viewports=["desktop", "mobile_portrait"]
)
```

### Error Handling and Resilience

Build robust testing workflows:

```python
from layoutlens import LayoutLens
import logging

def robust_ui_testing(pages, max_retries=2):
    """Test pages with error handling and retries."""
    tester = LayoutLens()
    results = {"passed": [], "failed": [], "errors": []}
    
    for page in pages:
        retries = 0
        while retries <= max_retries:
            try:
                result = tester.test_page(
                    page,
                    queries=["Is the page layout functional and clear?"]
                )
                
                if result.success_rate >= 0.7:  # Success threshold
                    results["passed"].append({"page": page, "result": result})
                    break
                else:
                    results["failed"].append({"page": page, "result": result})
                    break
                    
            except Exception as e:
                retries += 1
                if retries > max_retries:
                    logging.error(f"Failed to test {page} after {max_retries} retries: {e}")
                    results["errors"].append({"page": page, "error": str(e)})
                else:
                    logging.warning(f"Retrying {page} (attempt {retries}): {e}")
                    time.sleep(2)  # Brief delay before retry
    
    return results

# Usage
test_results = robust_ui_testing(["home.html", "about.html", "contact.html"])
print(f"Passed: {len(test_results['passed'])}")
print(f"Failed: {len(test_results['failed'])}")
print(f"Errors: {len(test_results['errors'])}")
```

## Next Steps

- Explore the [CLI Reference](cli-reference.md) for command-line usage
- Check out [Configuration](configuration.md) for advanced settings
- Review the [FAQ](faq.md) for common questions and solutions
- See the [API Documentation](../api/) for detailed technical reference