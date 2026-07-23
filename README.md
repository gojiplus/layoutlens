# LayoutLens: AI-Powered Visual UI Testing

[![PyPI version](https://img.shields.io/pypi/v/layoutlens.svg)](https://pypi.org/project/layoutlens/)
[![Downloads](https://static.pepy.tech/badge/layoutlens)](https://pepy.tech/project/layoutlens)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Documentation](https://img.shields.io/badge/docs-github.io-blue)](https://gojiplus.github.io/layoutlens/)

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

**81.1% accuracy** (60/74 labeled queries, `gpt-4o-mini`, measured 2026-07-21) on the bundled benchmark suite — see [`benchmarks/results/2026-07-21_gpt-4o-mini.json`](benchmarks/results/2026-07-21_gpt-4o-mini.json)

## Quick Start

### Installation
```bash
pip install layoutlens
playwright install chromium  # For screenshot capture
```

### Basic Usage
LayoutLens's API is async — run it with `asyncio.run(...)`, or `await` it
directly if you're already inside an `async def` (e.g. pytest-asyncio,
FastAPI, a notebook cell). Every snippet below assumes one of those two
contexts; only the first one spells out the `asyncio.run(...)` wrapper.
```python
import asyncio
from layoutlens import LayoutLens

async def main():
    # Initialize (uses OPENAI_API_KEY env var)
    lens = LayoutLens()

    # Test any website or local HTML
    result = await lens.analyze("https://your-site.com", "Is the header properly aligned?")
    print(f"Answer: {result.answer}")
    print(f"Confidence: {result.confidence:.1%}")

asyncio.run(main())
```

That's it! No selectors, no complex setup, just natural language questions.

## Deterministic Accessibility Checks (axe-core) — No API Key Required

LayoutLens vendors [axe-core](https://github.com/dequelabs/axe-core) 4.10.3 and runs it against a real
Playwright-rendered page to catch actual WCAG 2.1 A/AA violations — not an LLM guess. This mode is fully
keyless: no `OPENAI_API_KEY`, no network call to an AI provider, just deterministic, reproducible results.

### CLI
```bash
# Deterministic axe-core scan only — no API key needed
layoutlens page.html --a11y axe

# Hybrid: axe-core + LLM vision, axe overrides the verdict on violations (needs an API key)
layoutlens https://example.com --a11y hybrid

# Legacy vision-only accessibility check (needs an API key)
layoutlens page.html --a11y llm
```
`--a11y` requires one of `hybrid`/`axe`/`llm` and is mutually exclusive with `--query` — accessibility mode
always uses the built-in WCAG checks instead of a free-form question.

### Python
```python
from layoutlens import LayoutLens, AxeAuditor

# Raw axe-core report — no LayoutLens instance or API key needed at all
report = await AxeAuditor().audit("page.html")
print(report.summary())
print(report.ok)          # True if there are zero violations
print(report.violations)  # list[A11yFinding]: rule_id, impact, wcag_refs, nodes, ...

# Via the LayoutLens API, restricted to WCAG A/AA tags, still keyless
lens = LayoutLens()  # no API key required at construction
result = await lens.check_accessibility("page.html", mode="axe")
print(result.answer)      # "Yes — axe-core found no WCAG A/AA violations" (or lists violated rules)
```

### The three modes
- **`mode="axe"`** — deterministic axe-core only. No API key, no LLM call. `confidence` is always `1.0`.
- **`mode="hybrid"`** (default for `check_accessibility`/`audit_accessibility`) — runs axe-core *and* the LLM
  vision analysis, injecting the axe findings into the LLM's prompt as grounding context. If axe finds any
  violation, the final verdict is deterministically forced to "no" (confidence `1.0`), regardless of what the
  LLM says — axe overrides the model, not the other way around. If axe finds nothing, the LLM's own
  answer/confidence are kept (it can still flag issues axe's automated rules can't catch, like poor
  color choices that pass contrast math or confusing visual hierarchy).
- **`mode="llm"`** — legacy vision-only analysis, no axe-core involved. Requires an API key.

```python
# Hybrid: axe grounds the LLM and can force the verdict
result = await lens.check_accessibility("page.html", mode="hybrid")
print(result.metadata["a11y"])   # full axe report dict
print(result.metadata["engine"])  # "axe-core 4.10.3"
```

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
Perfect for A/B testing and redesign validation. `compare()` accepts URLs or
already-captured screenshot images directly; for local HTML files, capture
screenshots first with `lens.capture(...)`:
```python
result = await lens.compare(
    ["https://old-design.example.com", "https://new-design.example.com"],
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
`analyze()` handles single or multiple sources/queries — pass lists to either
`source` or `query` and it fans out every combination concurrently:
```python
results = await lens.analyze(
    source=["home.html", "about.html", "contact.html"],
    query=["Is it accessible?", "Is it mobile-friendly?"]
)
# Returns a BatchResult; processes 6 combinations concurrently
print(f"{results.successful_queries}/{results.total_queries} succeeded")
```

### 5. High-Performance Async (concurrency-controlled)
```python
# Cap concurrent API calls with max_concurrent
result = await lens.analyze(
    source=["page1.html", "page2.html", "page3.html"],
    query="Is it accessible?",
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

# Expert comparison analysis (compare/compare_with_expert take URLs or
# already-captured screenshots -- see the "Compare Layouts" note above)
result = await lens.compare_with_expert(
    sources=["https://old.example.com", "https://new.example.com"],
    query="Which design converts better?",
    expert_persona="conversion_expert",
    focus_areas=["cta_prominence", "trust_signals"]
)
```

### 8. YAML Test Suites

Test suites are declared in YAML/JSON and loaded into a `UITestSuite`. **Breaking
change (v1.7.0):** every test case must declare `expected_results` — an `answer`
("yes"/"no", matched against the parsed leading yes/no token of the analysis
answer) and/or a `contains` list (terms that must appear, case-insensitively, in
the answer + reasoning). A case with no `expected_results` now raises
`ValidationError` at load time instead of silently grading on confidence alone.

```yaml
# test_suite.yaml
name: "Homepage Suite"
description: "Accessibility and layout checks"
test_cases:
  - name: "Navigation Alignment"
    html_path: "pages/home.html"
    queries:
      - "Is the navigation menu properly centered?"
    viewports: ["desktop"]
    expected_results:
      answer: "yes"
      contains: ["centered"]
    expected_confidence: 0.7   # optional, defaults to 0.7
```

```python
import yaml
from layoutlens import LayoutLens, UITestSuite

with open("test_suite.yaml") as f:
    suite = UITestSuite.from_dict(yaml.safe_load(f))

lens = LayoutLens()
results = await lens.run_test_suite(suite)  # list[UITestResult], one per test case
for r in results:
    print(f"{r.test_case_name}: {r.passed_tests}/{r.total_tests} passed")
    print(r.to_json())  # includes per-assertion "assertion_detail"
```

There is no CLI subcommand for suites — `run_test_suite` is a Python API only.
See [`examples/sample_test_suite.yaml`](examples/sample_test_suite.yaml) for a
complete, runnable example.

## CLI Usage

```bash
# Analyze a single page
layoutlens https://example.com "Is this accessible?"

# Analyze local files
layoutlens page.html "Is the design professional?"

# Compare two designs (compare works with URLs or existing screenshot images;
# for local HTML files, capture screenshots first — see "Compare Layouts" above)
layoutlens https://old.example.com https://new.example.com --compare

# Analyze with different viewport
layoutlens site.com "Is it mobile-friendly?" --viewport mobile

# JSON output for automation
layoutlens page.html "Is it accessible?" --output json

# Deterministic WCAG accessibility scan — no API key required
# (see "Deterministic Accessibility Checks" above for hybrid/llm modes)
layoutlens page.html --a11y axe

# Choose model / pass an API key explicitly
layoutlens page.html "Is it accessible?" --model gpt-4o --api-key sk-...
```

Run `layoutlens` with no arguments (or `--help`) to see the full flag reference:
`--query/-q`, `--compare/-c`, `--viewport/-v {desktop,mobile,tablet}`,
`--output/-o {text,json}`, `--api-key`, `--model/-m`, `--a11y {hybrid,axe,llm}`.

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

### 3. Evaluated Benchmark Artifact
The evaluator scores every answer deterministically (leading yes/no token vs the
answer key; ambiguous answers count as incorrect) and writes an artifact with
per-category and overall accuracy. The committed
[`benchmarks/results/2026-07-21_gpt-4o-mini.json`](benchmarks/results/2026-07-21_gpt-4o-mini.json)
is a real measured run:
```json
{
  "evaluation_summary": {
    "date": "2026-07-21",
    "model": "gpt-4o-mini",
    "total_queries": 74,
    "total_correct": 60,
    "ambiguous_answers": 7,
    "overall_accuracy": 0.811,
    "evaluator_version": "2.0",
    "evaluator_method": "Deterministic structured yes/no; ambiguous answers count as incorrect."
  },
  "category_results": {
    "responsive_design": {"total_queries": 21, "correct_predictions": 20, "accuracy": 0.952},
    "layout_alignment":  {"total_queries": 24, "correct_predictions": 19, "accuracy": 0.792},
    "accessibility":     {"total_queries": 21, "correct_predictions": 16, "accuracy": 0.762},
    "ui_components":      {"total_queries": 8,  "correct_predictions": 5,  "accuracy": 0.625}
  }
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

- 📖 **[Full Documentation](https://gojiplus.github.io/layoutlens/)** - Comprehensive guides and API reference
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
- **Comprehensive Benchmarking** - Built-in evaluation system (81.1% measured accuracy, gpt-4o-mini, 74 queries)
- **Deterministic Accessibility** - Vendored axe-core WCAG 2.1 A/AA checks, no API key or LLM variance

---

*Making UI testing as simple as asking "Does this look right?"*
