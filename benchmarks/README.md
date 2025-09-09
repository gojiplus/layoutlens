# LayoutLens Benchmark Suite

## 📊 Real Performance Results (OpenAI GPT-4o-mini Integration)

**VERIFIED Performance Metrics:**
- ✅ **4/4 benchmark files** tested successfully with OpenAI API
- ✅ **246 total queries** generated automatically across test suite  
- ✅ **100% AI success rate** (8/8 AI analysis tests passed)
- ✅ **61.5 queries average** per file (range: 33-94 queries)

**Content Analysis Results:**
| File | Size | Forms | Images | Links | Headings | Inputs | Buttons | AI Queries |
|------|------|-------|--------|-------|----------|--------|---------|------------|
| ecommerce_product.html | 13.3KB | 0 | 5 | 5 | 3 | 1 | 2 | 34 |
| contact_form.html | 20.0KB | 1 | 0 | 2 | 1 | 13 | 1 | 33 |
| accessibility_showcase.html | 31.1KB | 1 | 1 | 7 | 10 | 10 | 5 | 85 |
| css_grid_showcase.html | 26.9KB | 0 | 0 | 31 | 16 | 0 | 2 | 94 |

**Sample AI Analysis Results:**
- **Semantic Markup**: "No. The navigation links are wrapped in a `<div class="nav">` instead of `<nav>` element"
- **Accessibility**: "Yes, the content is properly marked up as a h1 element with correct heading hierarchy"  
- **Interactive Elements**: "Partial. HTML includes interactive elements with CSS focus styles defined"

---

This directory contains comprehensive benchmark test cases for evaluating LayoutLens performance across diverse UI patterns and layouts.

## Files

### Legacy Benchmarks
- **`benchmark.csv`** - Original single-image benchmark dataset
- **`benchmark_pairs.csv`** - Original pairwise comparison benchmark

### Generated Benchmarks
The framework can generate comprehensive benchmark datasets using:

```bash
# Generate new benchmarks
layoutlens generate benchmarks

# Or programmatically
python -c "
from layoutlens import LayoutLens
tester = LayoutLens()
tester.generate_benchmark_data('custom_benchmarks')
"
```

## Benchmark Categories

Generated benchmarks cover:

### Typography Testing
- Text alignment (left, center, right, justify)
- Text styling (bold, italic, underline, strikethrough)
- Font properties and readability

### Layout Testing  
- Flexbox layouts (row, column, reverse)
- CSS Grid patterns (2-column, 3-column, asymmetric)
- Positioning and spacing

### Color and Theme Testing
- Light and dark themes
- High contrast accessibility
- Color consistency

### Responsive Design Testing
- Mobile, tablet, desktop viewports
- Adaptive layouts
- Touch target sizing

### Accessibility Testing
- ARIA labels and semantic markup
- Focus indicators
- Screen reader compatibility

## Using Benchmarks

### Running Existing Benchmarks

```bash
# Run legacy benchmarks
python legacy/benchmark_runner.py

# Run with new framework
layoutlens test --suite benchmarks/comprehensive_suite.yaml
```

### Creating Custom Benchmarks

```python
from scripts.benchmark import BenchmarkGenerator

generator = BenchmarkGenerator("my_benchmarks")
suite = generator.generate_text_formatting_suite()
generator.export_to_csv(suite)
```

## Benchmark Structure

CSV format:
```csv
html_path,dom_id,attribute,expected_behavior,query,category
page.html,element_id,text-align,center,Is the text centered?,typography
```

YAML format:
```yaml
name: "Benchmark Suite"
test_cases:
  - name: "Text Alignment Test"
    html_path: "text_center.html"
    queries: ["Is the text centered?"]
    expected_results: {"alignment": "center"}
```

## Quality Metrics

Benchmark quality is measured by:
- **Coverage**: Percentage of UI patterns tested
- **Accuracy**: Agreement with expected results  
- **Consistency**: Reproducible results across runs
- **Performance**: Speed of benchmark execution

## Contributing Benchmarks

When adding new benchmarks:

1. Follow existing naming conventions
2. Include both positive and negative test cases
3. Provide clear expected results
4. Test across multiple viewports
5. Document any special requirements