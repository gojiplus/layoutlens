### LayoutLens: AI-Enabled UI Test System

Write visual UI tests using natural language to

1. Compare current layouts to previous versions for consistency.
2. Validate layout relationships (e.g., "is the right box bigger than the left").
3. Check positioning (e.g., "is the menu at the top of the page but below the header").
4. Assess text formatting (e.g., "is the text justified").
5. Provide insights into UI design to ensure compliance with design specifications.

The system capture screenshots of the current UI state, compares to reference images for layout and styling consistency, identify differences in size, position, color, and text alignment, etc.

## Benchmarking and framework

The repository now includes a small framework for running natural-language tests:

- `legacy/framework.py` provides the original `LayoutLens` class that wraps OpenAI's vision models.
- `legacy/screenshot.py` converts HTML snippets into screenshots using Playwright.
- `legacy/benchmark_runner.py` renders the examples from `benchmarks/benchmark.csv` and `benchmarks/benchmark_pairs.csv` and optionally queries the LLM.
- `benchmarks/benchmark_pairs.csv` adds a simple dataset for cross-layout comparison (e.g., "do these layouts look the same?").
- `layoutlens/` provides the enhanced framework with modern API, CLI interface, and comprehensive testing capabilities.

### Running the benchmark

Install Playwright and the Chromium browser once:

```bash
pip install playwright
playwright install chromium
```

Generate screenshots only:

```bash
python legacy/benchmark_runner.py --skip-model
```

Run with an OpenAI key to get model answers:

```bash
OPENAI_API_KEY=... python legacy/benchmark_runner.py
```
