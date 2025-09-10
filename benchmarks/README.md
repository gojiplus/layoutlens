# LayoutLens Benchmark Suite v2.0

**Clean, organized benchmark structure with clear separation of concerns**

## 🏗️ Structure Overview

```
benchmarks_new/
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
python3 benchmarks_new/generators/benchmark_runner.py
```

### 2. Run LayoutLens on Test Data
```bash
# Set your API key
export OPENAI_API_KEY="your-key-here"

# Test a few examples
python3 -c "
from layoutlens import LayoutLens
tester = LayoutLens()

# Test positive example (should pass)
result = tester.test_page('benchmarks_new/test_data/layout_alignment/nav_centered.html')
print(f'Navigation centered: {result.success_rate:.1%}')

# Test negative example (should detect issues)  
result = tester.test_page('benchmarks_new/test_data/layout_alignment/nav_misaligned.html')
print(f'Navigation misaligned: {result.success_rate:.1%}')
"
```

### 3. Evaluate Against Ground Truth
```bash
# Run benchmark evaluation
python3 benchmarks_new/evaluation/evaluator.py \\
  --answer-keys benchmarks_new/answer_keys \\
  --results layoutlens_output/results \\
  --output benchmark_evaluation.json
```

## 📊 Test Categories

### Layout Alignment (4 tests)
- **nav_centered.html** ✅ Perfect navigation centering
- **nav_misaligned.html** ❌ 2% off-center (subtle issue)  
- **logo_correct.html** ✅ Logo on left (follows web conventions)
- **logo_wrong.html** ❌ Logo on right (violates conventions)

### Accessibility (2 tests)  
- **wcag_compliant.html** ✅ Meets WCAG AA standards
- **wcag_violations.html** ❌ Multiple accessibility violations

### Responsive Design (2 tests)
- **mobile_friendly.html** ✅ Adapts perfectly to all screen sizes
- **mobile_broken.html** ❌ Fixed width causes mobile issues

### UI Components (1 test)
- **form_well_designed.html** ✅ Professional form with best practices

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

### Semantic Answer Matching
- Understands "No, the navigation is not properly centered" matches expected "no"
- Handles various response formats and confidence levels
- Accounts for AI explanation styles

### Comprehensive Reporting
- Overall accuracy across all categories
- Per-category breakdown
- Confidence-based analysis
- Detailed mismatch analysis

### Example Evaluation Output:
```
📊 BENCHMARK EVALUATION SUMMARY
========================================
Overall Accuracy: 87.5% (14/16)
Categories Evaluated: 4

📂 Layout Alignment:
  Accuracy: 100.0% (4/4)
  High Confidence Correct: 4
  Avg AI Confidence: 0.95

📂 Accessibility:
  Accuracy: 75.0% (6/8)
  High Confidence Correct: 5
  Avg AI Confidence: 0.88
```

## ⚡ Key Improvements Over v1

### ✅ **Clear Structure**
- Scripts separate from data
- Test files paired (good/bad examples)  
- Unified answer key format
- Dedicated evaluation framework

### ✅ **Objective Testing** 
- Every test file has measurable criteria
- Intentional issues with known causes
- Semantic answer matching vs string matching
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
# Generate test data
python3 benchmarks_new/generators/benchmark_runner.py

# Test all categories
for category in layout_alignment accessibility responsive_design ui_components; do
  echo "Testing $category..."
  for file in benchmarks_new/test_data/$category/*.html; do
    python3 -c "
from layoutlens import LayoutLens
tester = LayoutLens()
result = tester.test_page('$file')
print(f'$(basename $file): {result.success_rate:.1%}' if result else '$(basename $file): FAILED')
"
  done
done

# Evaluate results
python3 benchmarks_new/evaluation/evaluator.py
```

### Expected Benchmark Performance:
- **Layout Alignment**: >95% accuracy (issues are measurable)
- **Accessibility**: >90% accuracy (clear violations)  
- **Responsive Design**: >85% accuracy (obvious mobile issues)
- **UI Components**: >80% accuracy (design quality subjective)

## 🔄 Migration from Old Structure

The old `benchmarks/` folder can be migrated by:
1. Moving HTML files to appropriate `test_data/` categories
2. Converting scattered answer formats to unified JSON keys
3. Updating evaluation logic to use semantic matching

This new structure makes it crystal clear:
- **What generates the data** (`generators/`)
- **What the test data is** (`test_data/`)  
- **What the right answers are** (`answer_keys/`)
- **How to check if we're right** (`evaluation/`)