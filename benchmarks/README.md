# LayoutLens Benchmarks

This directory contains benchmark datasets used for testing and validating the LayoutLens framework.

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