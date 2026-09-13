# LayoutLens: Measured UI Regressions

[![PyPI version](https://img.shields.io/pypi/v/layoutlens.svg)](https://pypi.org/project/layoutlens/)
[![Downloads](https://static.pepy.tech/badge/layoutlens)](https://pepy.tech/project/layoutlens)
[![Supported Python](https://img.shields.io/pypi/pyversions/layoutlens)](https://pypi.org/project/layoutlens/)
[![Documentation](https://img.shields.io/badge/docs-github.io-blue)](https://gojiplus.github.io/layoutlens/)

LayoutLens captures browser evidence, matches elements across versions, and
reports measured layout changes with candidate DOM/CSS causes. Capture and
diff run locally without an API key. Model explanation is optional.

```python
import asyncio
from layoutlens import capture_state, diff


async def main():
    before = await capture_state("before.html")
    after = await capture_state("after.html")
    before.save("artifacts/baseline")
    after.save("artifacts/candidate")
    report = diff(before, after)
    print(report.to_json())


asyncio.run(main())
```

Create the two HTML files before running this example. Each `save()` writes a
new artifact directory and refuses to overwrite an existing baseline.

A `RenderState` contains the screenshot, DOM structure, computed styles,
geometry, accessibility roles/names, text rectangles, focus/interaction
information, loading state, browser conditions, and replayable detector
evidence. Its graph records containment, alignment, overlap, adjacency,
proximity, and geometric reading order.

`VisualDelta` records before/after boxes, changed properties, numeric deltas,
image regions, correspondence evidence, candidate defect class, source
attribution, and gate policy. Saved artifacts can be compared offline.

| Evidence level | Meaning |
|---|---|
| Observation | A measured browser fact or rendered change |
| Candidate | A measurement matches a defect predicate |
| Verified | Recorded exception resolution or independent evidence supports the finding |
| Gateable | An applicable independent precision evaluation qualifies the rule |

Default CI blocking requires a sealed independent evaluation whose **95%
Wilson precision interval has a lower bound of at least 99%**. Rule version,
configuration, capture conditions, dataset hash, and evaluation counts must
match. No layout rules ship with qualifying evidence yet. Candidates remain
warnings; `policy="findings"` explicitly opts into strict blocking. An
incomplete comparison never reports a passing gate.

Axe accessibility rule outcomes remain separately identified. Standalone
layout scans and optional hybrid model analysis also retain candidate findings
without equating deterministic measurement with proven defects.

The bundled model benchmark recorded 60 correct answers out of 74 labeled
queries (81.1%, `gpt-4o-mini`, 2026-07-21). That result measures single-page
questions, not the accuracy of the regression engine. The
[benchmark section](#benchmark--evaluation-workflow) links the recorded results
and scoring method.

## Quick Start

### Installation
Requires Python 3.12 or newer.

```bash
pip install layoutlens
playwright install chromium  # For screenshot capture
```

### Capture and compare

```bash
layoutlens capture before.html --save artifacts/baseline
layoutlens capture after.html --save artifacts/candidate
layoutlens diff artifacts/baseline artifacts/candidate --output json
```

These commands need Chromium but no model API key. Diff exits with 0 for a
passing gate, 1 for a blocking finding, and 2 for incomplete evidence or an
execution error. Candidates warn by default; add `--fail-on findings` to block
introduced or worsened candidates without upgrading their evidence level.

Python capture and analysis methods are async. The opening example uses
`asyncio.run(...)`; the remaining Python examples assume an async function or
a notebook that supports `await`.

## Deterministic Accessibility Checks (axe-core) — No API Key Required

LayoutLens runs vendored [axe-core](https://github.com/dequelabs/axe-core)
4.10.3 against a Playwright-rendered page. It reports outcomes from automated
WCAG A/AA rules without an API key. A passing scan means those rules found no
violations; it does not establish WCAG conformance.

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
print(report.ok)  # True if there are zero violations
print(report.violations)  # list[A11yFinding]: rule_id, impact, wcag_refs, nodes, ...

# Via the LayoutLens API, restricted to WCAG A/AA tags, still keyless
lens = LayoutLens()  # no API key required at construction
result = await lens.check_accessibility("page.html", mode="axe")
print(
    result.answer
)  # "Yes — axe-core found no WCAG A/AA violations" (or lists violated rules)
```

### The three modes
- **`mode="axe"`** — axe-core only. No API key or model call. The API sets
  `confidence=1.0` to identify the rule result; this is not a calibrated
  probability that the page is accessible.
- **`mode="hybrid"`** (default for `check_accessibility`) — runs axe-core *and* the LLM
  vision analysis, injecting the axe findings into the LLM's prompt as grounding context. If axe finds any
  violation, the final verdict is deterministically forced to "no" (confidence `1.0`), regardless of what the
  LLM says — axe overrides the model, not the other way around. If axe finds nothing, the LLM's own
  answer/confidence are kept (it can still flag issues axe's automated rules can't catch, like poor
  color choices that pass contrast math or confusing visual hierarchy).
- **`mode="llm"`** — legacy vision-only analysis, no axe-core involved. Requires an API key.

```python
# Hybrid: axe grounds the LLM and can force the verdict
result = await lens.check_accessibility("page.html", mode="hybrid")
print(result.metadata["a11y"])  # full axe report dict
print(result.metadata["engine"])  # "axe-core 4.10.3"
```

## Deterministic Layout Scorers (geometry & contrast) — No API Key Required

`LayoutScorer` measures geometry and contrast in the rendered page and reports
candidate defects without a model call. Foundational contrast and geometry measurements were ported from
[UIJudgeBench](https://github.com/gojiplus/uijudge-bench); newer WCAG and text-occlusion
checks are independent LayoutLens implementations evaluated by that benchmark. It finds:

- **contrast** — text below the WCAG AA ratio (4.5:1 normal, 3.0:1 large), with the measured ratio
- **overlap** — sibling elements whose bounding boxes collide
- **clipping** — content cut off by a fixed-size box with hidden overflow
- **viewport-protrusion** — elements extending past the viewport width (horizontal-scroll bugs)
- **target-size** — undersized targets that also fail the machine-measurable WCAG 2.5.8
  spacing, inline, and unmodified user-agent-control exceptions
- **focus-obscured** — keyboard-focused components entirely hidden by author DOM content
  (the automatable geometric core of WCAG 2.4.11)
- **text-occlusion** — rendered text, including chart labels, covered by another painted
  DOM element; this is a visual-quality finding, not a WCAG criterion

```python
from layoutlens.layout import LayoutScorer, contrast_ratio, read_computed_styles

# Scan a page — no LayoutLens instance, no API key, deterministic.
report = await LayoutScorer().scan("page.html", viewport="mobile")
print(report.ok)  # True if no candidate findings
print(report.summary())  # findings grouped by class, with measured receipts
for f in report.findings:
    print(
        f.defect_class, f.selector, f.measured
    )  # each finding carries the numbers behind it

# Or use the pure WCAG contrast math directly (no browser):
contrast_ratio((0x76, 0x76, 0x76), (0xFF, 0xFF, 0xFF))  # -> 4.54
```

Each finding includes a selector, bounding box, measured value, and threshold.
`scan(viewport=...)` measures the page at the requested viewport, including
protrusion or overlap that appears only on mobile. Automated findings are not a
site-wide WCAG conformance claim. In particular, target-size equivalent/essential exceptions
and focus-obscuration interaction-history exceptions remain explicit manual-review fields.

## pytest Plugin

Installing layoutlens registers a pytest plugin (entry point `layoutlens`).
The `layoutlens` fixture provides four assertions:

```python
def test_checkout(layoutlens):
    layoutlens.assert_regression("artifacts/baseline", "artifacts/candidate")
    layoutlens.assert_a11y("checkout.html")  # keyless axe gate
    layoutlens.assert_layout(
        "checkout.html", viewport="mobile"
    )  # keyless candidate layout scan
    layoutlens.assert_ui(
        "checkout.html", "Is the pay button the most prominent element?"
    )
```

`assert_regression` checks a complete before/after comparison.
`assert_layout` warns on candidates by default; pass `policy="findings"` for
strict blocking. `assert_a11y` fails when axe reports violations. These three
methods require no model key and return measured evidence.

`assert_ui` asks a vision model and skips when no API key is configured, or
when `--layoutlens-no-llm` is set. `--layoutlens-model` selects its model.

## MCP Server (for coding agents)

`layoutlens-mcp` exposes the checks as [MCP](https://modelcontextprotocol.io)
tools for Claude Code, Cursor, and friends:

```bash
pip install "layoutlens[mcp]"
# register the stdio server in your agent config:
#   command: layoutlens-mcp
```

The server exposes `capture_render_state`, `compare_ui`, `audit_accessibility`,
and `scan_layout` without a model key. `check_ui` provides optional vision-model
analysis. Measured findings cover contrast, geometry, target spacing, focus
obscuration, and text occlusion, including chart labels covered by other elements.

## SARIF Output for GitHub Code Scanning

Both deterministic engines emit [SARIF 2.1.0](https://sarifweb.azurewebsites.net/):

```bash
layoutlens page.html --layout deterministic --output sarif > layout.sarif
layoutlens page.html --a11y axe --output sarif > a11y.sarif
```

Upload with `github/codeql-action/upload-sarif` and findings appear as PR
annotations with stable rule ids (`layout/page-overflow`, `axe/color-contrast`,
...) tracked over time. Scanning needs no model key; uploading SARIF requires
GitHub permissions appropriate to the workflow and fork context.

[`gojiplus/layoutlens-action`](https://github.com/gojiplus/layoutlens-action)
handles installation, scanning, job summaries, PR annotations, an optional
results comment, and SARIF upload. This example pins the Action revision tested
against LayoutLens 3:

```yaml
- uses: gojiplus/layoutlens-action@23c0fa2ca3e2b238927e6f9d6e6c59ac61fc9031
  with:
    sources: "dist/*.html"
```

## Key Functions

### 1. Analyze Pages
Ask a vision model about a page or screenshot. This example uses
`OPENAI_API_KEY`; choose another provider through `LayoutLens` configuration.
Model confidence is self-reported, not a measured probability of correctness.

```python
from layoutlens import LayoutLens

lens = LayoutLens()

# Analyze a local HTML file
result = await lens.analyze("checkout.html", "Is the payment form user-friendly?")

# Test with expert context
from layoutlens.prompts import Instructions, UserContext

instructions = Instructions(
    expert_persona="conversion_expert",
    user_context=UserContext(
        business_goals=["reduce_cart_abandonment"], target_audience="mobile_shoppers"
    ),
)

result = await lens.analyze(
    "checkout.html",
    "How can we optimize this checkout flow?",
    instructions=instructions,
)
```

### 2. Compare Layouts
`compare()` accepts exactly two render states, artifact paths, URLs, or HTML
files. It returns a structured `DiffReport` and never calls a model by default.

```python
result = await lens.compare("artifacts/baseline", "artifacts/candidate")
print(result.summary())

explained = await lens.compare(
    "before.html",
    "after.html",
    explain=True,
    intent="Reduce checkout button width while keeping its text readable",
)
print(explained.explanation)
```

Screenshot-only comparison is unsupported. Optional explanation cannot change
measurements, evidence levels, or gate decisions. See the
[migration and artifact guide](https://github.com/gojiplus/layoutlens/blob/72c99eacc14c2c6f7bbf828efced6cb73cf2f4be/docs/REGRESSION.md).

### 3. Analysis with expert prompts
Use a preset prompt for the task:
```python
# Hybrid accessibility analysis (requires a model key)
result = await lens.check_accessibility("product-page.html", compliance_level="AA")

# Conversion rate optimization (CRO expert)
result = await lens.optimize_conversions(
    "landing.html", business_goals=["increase_signups"], industry="saas"
)

# Mobile UX analysis (Mobile expert)
result = await lens.analyze_mobile_ux("app.html", performance_focus=True)

# E-commerce audit (Retail expert)
result = await lens.audit_ecommerce("checkout.html", page_type="checkout")
```

### 4. Batch Testing
`analyze()` handles single or multiple sources/queries — pass lists to either
`source` or `query` and it fans out every combination concurrently:
```python
results = await lens.analyze(
    source=["home.html", "about.html", "contact.html"],
    query=["Is it accessible?", "Is it mobile-friendly?"],
)
# Returns a BatchResult; processes 6 combinations concurrently
print(f"{results.successful_queries}/{results.total_queries} succeeded")
```

### 5. Limit concurrent requests
```python
# Cap concurrent API calls with max_concurrent
result = await lens.analyze(
    source=["page1.html", "page2.html", "page3.html"],
    query="Is it accessible?",
    max_concurrent=5,
)
```

### 6. Structured JSON Output
Results provide `to_json()` for automation. Analysis output includes the answer,
confidence, reasoning, screenshot path, viewport, timing, and metadata. A
`DiffReport` instead exposes deltas, evidence, and gate status.

```python
import json
from layoutlens.types import AnalysisResultJSON

result = await lens.analyze("page.html", "Is the navigation clearly visible?")
print(result.to_json())
data: AnalysisResultJSON = json.loads(result.to_json())
confidence = data["confidence"]
```

### 7. Domain Experts & Rich Context
Choose from six expert personas to guide the model prompt:
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
        "industry": "healthcare",
    },
)

# Explain the measured comparison with an expert persona
result = await lens.compare_with_expert(
    "https://old.example.com",
    "https://new.example.com",
    intent="Improve the checkout flow",
    expert_persona="conversion_expert",
    focus_areas=["cta_prominence", "trust_signals"],
)
```

### 8. YAML Test Suites

Load YAML or JSON test cases into a `UITestSuite`. Each case must declare
`expected_results`: an `answer` ("yes" or "no", matched against the parsed leading
token) and/or a `contains` list (terms required in the answer and reasoning,
case-insensitively). A case without expected results raises `ValidationError`
at load time. Confidence alone cannot make a case pass.

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
See [`examples/sample_test_suite.yaml`](https://github.com/gojiplus/layoutlens/blob/main/examples/sample_test_suite.yaml) for a
complete, runnable example.

## Using LayoutLens as an LLM Judge

For external evaluation harnesses (e.g. UIJudgeBench), `judge()` sends your
prompt **verbatim** — no persona, no scaffolding, no appended JSON contract —
alongside a single image, and returns a parsed, structured verdict. Your harness
owns the entire prompt, including its own response contract and prompt versioning.

```python
from layoutlens import LayoutLens

lens = LayoutLens(model="gpt-4o")  # or any vision model via provider/api_base

prompt = (
    "You are a UI evaluation judge. Compare the layout in the image against the "
    "criteria below and respond ONLY as JSON: "
    '{"answer": "A" | "B", "confidence": 0.0-1.0, "rationale": "..."}.\n'
    "Criteria: which layout has clearer visual hierarchy?"
)

result = await lens.judge("candidate.png", prompt, max_tokens=300)

result.answer  # parsed "answer" field, or "unknown" if unparseable
result.confidence  # parsed 0-1, else 0.0
result.rationale  # parsed "rationale"/"reasoning", else ""
result.raw  # full raw model text
result.refused  # True if the model declined
result.usage  # {"prompt_tokens": ..., "completion_tokens": ..., "total_tokens": ...}
result.parse_mode  # "json" | "fallback" | "none"
```

For bulk evaluation, `judge_batch()` uses
[batchlane](https://github.com/gojiplus/batchlane) for asynchronous provider jobs.
Native OpenAI retains Responses requests, including image detail and reasoning
effort; Gemini and Anthropic use their native batch lanes through batchlane.
Provider calls run outside the event loop. Gemini no longer needs a separate
`layoutlens[gemini]` extra. Custom `api_base` values and unshipped provider lanes
are rejected before submission.

```python
from layoutlens import BatchRequest, LayoutLens

lens = LayoutLens(provider="openai", model="gpt-5.6-luna")
results = await lens.judge_batch(
    [BatchRequest("item-1", "target.jpg", prompt)],
    max_tokens=256,
    reasoning_effort="low",
    image_detail="original",
)
```

Resume manifests are content-addressed by the exact prompts, images, model,
backend, endpoint, token budget, reasoning effort, and image detail, so a changed
request cannot reuse a stale response. A per-manifest lock prevents two
processes from submitting the same exact batch concurrently. Manifests created
before 2.1.1 fail closed with explicit migration details because they cannot
attest their original prompts, images, or token budget. Changing an input creates
a new fingerprint; if any prior same-model manifest records an overlapping
submitted id, resume fails closed until the user explicitly migrates the job or
authorizes a fresh billed run. An ungraceful process stop can leave
a `.json.lock` file: confirm no matching run is active, then remove only that
lock file to resume from the preserved manifest.

Key guarantees:

- **Verbatim prompt** — LayoutLens adds nothing to the text you provide.
- **Fresh single-image judgments** — `judge()` does not cache results.
  `judge_batch()` persists completed judgments so resuming a batch reuses them.
- **Per-model parameter policy** — models that reject non-default sampling params
  (Claude Sonnet 5, Opus 4.6+) omit `temperature` automatically; others send
  `temperature=0.0`.
- **Self-hosted endpoints for `judge()`** — configure `api_base` for a local
  provider. `judge_batch()` rejects custom API bases:

  ```python
  lens = LayoutLens(
      provider="litellm",
      model="ollama/qwen2.5vl",
      api_base="http://localhost:11434",
  )
  ```

## CLI Usage

```bash
# Analyze a single page
layoutlens https://example.com "Is this accessible?"

# Analyze local files
layoutlens page.html "Is the design professional?"

# Compare rendered pages through saved artifacts
layoutlens capture before.html --save artifacts/baseline
layoutlens capture after.html --save artifacts/candidate
layoutlens diff artifacts/baseline artifacts/candidate --output json

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
`--output/-o {text,json,sarif}`, `--api-key`, `--model/-m`, and
`--a11y {hybrid,axe,llm}`. Run `layoutlens capture --help` or
`layoutlens diff --help` for artifact commands.

## CI/CD Integration

### GitHub Actions

Compare stored baselines with a candidate built by the workflow:

```yaml
- name: Compare rendered checkout
  run: |
    pip install layoutlens
    playwright install chromium
    layoutlens capture dist/checkout.html --save artifacts/candidate
    layoutlens diff baselines/checkout artifacts/candidate --fail-on findings
```

This example explicitly blocks introduced or worsened candidate findings. Omit
`--fail-on findings` to use the default qualification policy.

### Python testing

```python
def test_checkout_regression(layoutlens):
    layoutlens.assert_regression(
        "baselines/checkout", "artifacts/candidate", policy="findings"
    )
```

Keep baseline and candidate capture conditions the same. An incomplete
comparison fails the assertion rather than reporting a pass.

## Benchmark & Evaluation Workflow

The bundled benchmark contains 18 fixtures and 74 labeled questions for testing
single-page model answers. It does not evaluate `RenderState.diff()` or qualify
layout rules for CI. [UIJudgeBench](https://github.com/gojiplus/uijudge-bench)
provides a separate evaluation harness with LayoutLens adapters and tasks for
accessibility, layout, and referring to elements
([dataset](https://huggingface.co/datasets/gojiberries/uijudge-bench)).

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
[`benchmarks/results/2026-07-21_gpt-4o-mini.json`](https://github.com/gojiplus/layoutlens/blob/main/benchmarks/results/2026-07-21_gpt-4o-mini.json)
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
        {"source": "page2.html", "query": "Is it mobile-friendly?"},
    ]

    results = []
    for case in test_cases:
        result = await lens.analyze(case["source"], case["query"])
        results.append(
            {
                "test": case,
                "result": result.to_json(),  # Clean JSON output
                "model_confidence": result.confidence,
            }
        )

    return results
```

Score custom runs against an answer key. A model's confidence is not evidence
that its answer is correct.

## Configuration

Set a provider key in the environment:

```bash
export OPENAI_API_KEY="sk-..."
```

Or configure the client in Python:

```python
from layoutlens import LayoutLens

lens = LayoutLens(
    api_key="sk-...",
    model="gpt-4o-mini",
    cache_enabled=True,  # Reduce API costs
    cache_type="memory",  # "memory" or "file"
)
```

## Limitations

- **Vision models miss subtle changes.** On
  [DiffSpot](https://arxiv.org/abs/2605.29615), the best of 13 tested models
  recovered 40.7% of true changes; every model had recall below 23% on the hard
  tier. The benchmark uses 3,900 controlled CSS-change pairs and 500 no-change
  controls. Those results concern model perception, not LayoutLens diff accuracy.
- **Passing axe-core does not establish WCAG conformance.** A passing result
  means no rule in that automated scan reported a violation. Manual checks remain
  necessary for criteria and exceptions outside those rules.
- **Measured layout candidates need context.** Target spacing, inline targets,
  and unmodified browser controls have machine-checkable exceptions. Equivalent
  controls, essential presentation, and focus-obscuration interaction history
  still require review. Text occlusion is a visual-quality signal.
- **Capture coverage is limited.** The regression engine uses Chromium. It
  traverses open shadow DOM but reports closed roots, frame interiors, canvas,
  and video as coverage gaps. Unstable captures and ambiguous element matches
  make comparisons incomplete. CSS and git attribution identify candidate
  causes; they do not prove causality.
- **The bundled model benchmark is small.** Its 81.1% result covers 74 labeled
  queries from one recorded run. Rerun it with your model and pages before
  relying on its answers.

## Resources

- [Documentation and API reference](https://gojiplus.github.io/layoutlens/)
- [Examples](https://github.com/gojiplus/layoutlens/tree/main/examples)
- [Report an issue](https://github.com/gojiplus/layoutlens/issues)
