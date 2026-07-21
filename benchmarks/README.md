# LayoutLens Benchmark Suite v2.0

**Clean, organized benchmark structure with clear separation of concerns**

## 🏗️ Structure Overview

```
benchmarks/
├── generators/              # Scripts that create test data
│   └── benchmark_runner.py  # Main generator - run this to create all test files
├── test_data/              # Generated HTML test files (paired good/bad examples)
│   ├── layout_alignment/   # Navigation centering, logo positioning
│   ├── accessibility/      # WCAG compliance vs violations
│   ├── responsive_design/  # Mobile-friendly vs broken layouts
│   └── ui_components/      # Well-designed forms and components
├── answer_keys/            # Expected answers in unified JSON format
│   ├── layout_alignment.json
│   ├── accessibility.json
│   ├── responsive_design.json
│   └── ui_components.json
├── evaluation/             # Scripts to check answers against keys
│   └── evaluator.py        # Main evaluation engine
└── README.md              # This file
```

## 🚀 Quick Start

### 1. Generate Test Data
```bash
# Create all HTML test files
python3 benchmarks/generators/benchmark_runner.py
```

### 2. Run LayoutLens on Test Data
```bash
# Set your API key
export OPENAI_API_KEY="your-key-here"

# Test a few examples (LayoutLens's API is async)
python3 -c "
import asyncio
from layoutlens import LayoutLens

async def main():
    lens = LayoutLens()

    # Positive example (should be judged well-aligned)
    result = await lens.analyze(
        'benchmarks/test_data/layout_alignment/nav_centered.html',
        'Is the navigation menu properly centered?',
    )
    print(f'Navigation centered: {result.answer} (confidence: {result.confidence:.1%})')

    # Negative example (should detect the misalignment)
    result = await lens.analyze(
        'benchmarks/test_data/layout_alignment/nav_misaligned.html',
        'Is the navigation menu properly centered?',
    )
    print(f'Navigation misaligned: {result.answer} (confidence: {result.confidence:.1%})')

asyncio.run(main())
"
```

### 3. Evaluate Against Ground Truth
```bash
# Run benchmark evaluation (see "Testing LayoutLens" below for the full,
# verified end-to-end command)
uv run python benchmarks/evaluation/evaluator.py \
  --answer-keys benchmarks/answer_keys \
  --results benchmarks/run_out \
  --output benchmark_evaluation.json
```

## 📊 Test Categories

The suite has **18 HTML fixtures** with **74 labeled yes/no queries** across 4
categories. Counts below reflect the answer keys in `answer_keys/`.

### Layout Alignment (8 fixtures / 24 queries)
- `nav_centered.html`, `nav_misaligned.html`, `logo_correct.html`, `logo_wrong.html`,
  `flexbox_center_correct.html`, `flexbox_center_broken.html`,
  `grid_layout_correct.html`, `grid_layout_broken.html`

### Accessibility (4 fixtures / 21 queries)
- `wcag_compliant.html` ✅ Clean under axe-core (wcag2a+wcag2aa)
- `wcag_violations.html` ❌ color-contrast + image-alt (axe-confirmed)
- `focus_management_good.html`, `focus_management_broken.html`

### Responsive Design (5 fixtures / 21 queries)
- `mobile_friendly.html`, `mobile_broken.html`, `container_queries_good.html`,
  `viewport_units_broken.html`, `fluid_typography_good.html`

### UI Components (1 fixture / 8 queries)
- `form_well_designed.html` ✅ Professional form with best practices

### Axe ground truth (accessibility)

Each accessibility fixture's answer-key entry carries an `axe_ground_truth`
block written by `generators/generate_a11y_ground_truth.py` — the real axe-core
findings (rule ids, impacts, WCAG refs, engine version) so labels are
machine-traceable. Regenerate/verify with:

```bash
uv run python benchmarks/generators/generate_a11y_ground_truth.py          # write
uv run python benchmarks/generators/generate_a11y_ground_truth.py --check  # CI guard
```

## 🎯 Answer Key Format

Each answer key contains structured ground truth data:

```json
{
  "test_cases": {
    "nav_misaligned.html": {
      "queries": {
        "Is the navigation menu properly centered?": {
          "expected": "no",
          "confidence_threshold": 0.9,
          "reasoning": "Navigation is positioned 2% off-center",
          "measurable_criteria": "left: 52% instead of 50%",
          "issue_severity": "medium"
        }
      }
    }
  }
}
```

## 🔬 Evaluation Features

### Deterministic yes/no scoring (evaluator v2.0)
- Every answer key `expected` is `"yes"` or `"no"`.
- The evaluator parses the **leading yes/no token** of the model answer
  (word-boundary parse, same parser as the runtime test suite) and compares it
  to `expected`.
- **Ambiguous / unparseable answers count as INCORRECT** — they are never
  silently mapped to "no" (the old keyword-sentiment matcher did exactly that,
  handing out free "no" credit).

### Comprehensive Reporting
- Overall accuracy across all categories
- Per-category breakdown, with an ambiguous-answer count
- Model, date, query count, and evaluator version/method recorded in the artifact

### Measured Evaluation Output (real run):
```
BENCHMARK EVALUATION SUMMARY
============================================================
Model: gpt-4o-mini
Overall Accuracy: 81.1% (60/74)
Ambiguous (unparseable) answers: 7
Categories Evaluated: 4

Responsive Design:  95.2% (20/21)
Layout Alignment:   79.2% (19/24)
Accessibility:      76.2% (16/21)
Ui Components:       62.5% (5/8)
```
See the committed artifact: `results/2026-07-21_gpt-4o-mini.json`.

## ⚡ Key Improvements Over v1

### ✅ **Clear Structure**
- Scripts separate from data
- Test files paired (good/bad examples)
- Unified answer key format
- Dedicated evaluation framework

### ✅ **Objective Testing**
- Every test file has measurable criteria
- Intentional issues with known causes
- Deterministic yes/no scoring (ambiguous answers count as incorrect)
- Confidence thresholds per test

### ✅ **Easy Automation**
- Single command generates all test data
- Single command evaluates all results
- JSON reports for CI/CD integration
- Reproducible test suite

### ✅ **Better Coverage**
- Paired positive/negative examples
- Multiple difficulty levels
- Real-world issue patterns
- Comprehensive answer keys

## 🧪 Testing LayoutLens

### Run Full Benchmark Suite:
```bash
export OPENAI_API_KEY="your-key-here"

# 1. Run LayoutLens over all fixtures (74 queries; --no-batch scores each
#    fixture against its own queries).
uv run python benchmarks/run_benchmark.py --no-batch --output benchmarks/run_out

# 2. Score deterministically against the answer keys.
uv run python benchmarks/evaluation/evaluator.py \
  --answer-keys benchmarks/answer_keys \
  --results benchmarks/run_out \
  --output benchmarks/results/$(date +%F)_gpt-4o-mini.json
```

### Measured Benchmark Performance (gpt-4o-mini, 2026-07-21):
- **Overall**: 81.1% (60/74)
- **Responsive Design**: 95.2% (20/21)
- **Layout Alignment**: 79.2% (19/24)
- **Accessibility**: 76.2% (16/21)
- **UI Components**: 62.5% (5/8)

## 🗂️ Why This Structure

This structure makes it crystal clear:
- **What generates the data** (`generators/`)
- **What the test data is** (`test_data/`)
- **What the right answers are** (`answer_keys/`)
- **How to check if we're right** (`evaluation/`)
