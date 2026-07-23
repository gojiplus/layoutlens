# CLAUDE.md - LayoutLens v1.7.0

Guidance for Claude Code when working in this repository. Describes what the
code actually does — verify against source before trusting older assumptions;
this file has drifted from reality before.

## Project Overview

LayoutLens is an AI-powered UI testing framework: it captures screenshots with
Playwright and answers natural-language questions about them via a
vision-capable LLM (through LiteLLM; `gpt-4o-mini` by default). It also ships
a fully deterministic, keyless WCAG 2.1 A/AA accessibility engine built on a
vendored axe-core bundle.

## Package Structure (real, as of v1.7.0)

```
layoutlens/
├── __init__.py                    # Public exports
├── api/
│   ├── core.py                    # LayoutLens class (analyze/compare/capture/checks)
│   └── test_suite.py              # UITestCase/UITestSuite/UITestResult + run_test_suite
├── a11y/
│   ├── axe.py                     # AxeAuditor, AXE_VERSION
│   ├── types.py                   # A11yFinding, A11yReport
│   └── assets/                    # Vendored axe-core bundle (axe.min.js, LICENSE-axe.txt)
├── prompts/                       # Expert persona system (Instructions, get_expert, ...)
├── integrations/
│   └── browser_use/               # AgentValidator, SessionRecorder/Replayer, reports
├── browser.py                     # Shared Playwright page lifecycle (open_page)
├── capture.py                     # Capture: screenshot capture for URLs/HTML files
├── cli.py                         # The entire CLI (one file, one command)
├── config.py                      # Config / layoutlens.yaml handling
├── cache.py                       # AnalysisCache (memory/file backends)
├── logger.py                      # Structured logging setup
├── exceptions.py                  # Custom exception hierarchy
└── types.py                       # Enums (Viewport, Expert, ComplianceLevel, ...) + TypedDicts
```

There is **no** `vision/`, `providers/`, `cli_commands.py`, `cli_interactive.py`,
or `integrations/github.py` — those belonged to an earlier architecture and no
longer exist. Don't reintroduce them or write docs that assume they exist.

## CLI

The CLI is a single flat command — there are no subcommands (`test`, `batch`,
`interactive`, `generate`, `validate` do not exist):

```bash
layoutlens SOURCES... [--query TEXT] [--compare] \
  [--viewport {desktop,mobile,tablet}] [--a11y {hybrid,axe,llm}] \
  [--output {text,json}] [--api-key KEY] [--model MODEL]
```

- Positional args that are URLs or existing paths become sources; a leftover
  positional string (if `--query` wasn't given) becomes the query.
- `--a11y {hybrid,axe,llm}` runs the built-in WCAG checks instead of a
  free-form query; it is an error to combine `--a11y` with `--query`.
  `--a11y axe` is fully deterministic and needs no API key.
- `--compare` compares the first two sources; `compare()` (CLI and Python)
  expects URLs or already-captured screenshots — passing a raw local `.html`
  path skips screenshot rendering and fails with an "unsupported image" error
  from the vision API. Capture first (`lens.capture(...)`) when comparing
  local HTML files.

Run `layoutlens --help` for the authoritative flag reference.

## API

Everything on `LayoutLens` that touches the network or a browser is `async` —
call with `await` inside an `async def`, or wrap top-level scripts in
`asyncio.run(...)`.

```python
from layoutlens import LayoutLens

lens = LayoutLens(
    api_key=None,             # optional; falls back to the provider's env var.
                               # NOT required at construction (see below)
    model="gpt-4o-mini",
    provider="openai",        # "openai" | "anthropic" | "google" | "gemini" | "litellm"
    output_dir="layoutlens_output",
    cache_enabled=True,
    cache_type="memory",      # "memory" | "file"
)

result = await lens.analyze(source, query, viewport="desktop", max_concurrent=5)
```

- `analyze(source, query, ...)` is the one method for single/batch analysis:
  pass a list to `source` and/or `query` to fan out every combination
  concurrently. Single source + single query returns `AnalysisResult`;
  anything else returns `BatchResult`. There is no `analyze_batch` /
  `analyze_batch_async` — those were removed.
- `compare(sources, query, ...)` returns `ComparisonResult`. Takes URLs or
  screenshot paths, not raw local HTML (see CLI section above).
- `capture(source, viewport=...)` renders a URL/HTML file to a PNG and
  returns the path (or a dict of `source -> path` for a list of sources).
- **API key is deferred to first LLM use.** `LayoutLens()` never raises for a
  missing key at construction — `AuthenticationError` is only raised inside
  `_call_vision_api` when an LLM call actually happens. This keeps
  `check_accessibility(..., mode="axe")` and `AxeAuditor` fully keyless.

## Deterministic Accessibility (axe-core)

`layoutlens/a11y/` wraps a vendored axe-core bundle
(`layoutlens/a11y/assets/axe.min.js` + `LICENSE-axe.txt`, version pinned in
`AXE_VERSION` in `layoutlens/a11y/axe.py`), injected into a live Playwright
page via `AxeAuditor`.

```python
from layoutlens import AxeAuditor
report = await AxeAuditor(run_only=["wcag2a", "wcag2aa"]).audit(source, viewport)
```

`check_accessibility` / `audit_accessibility` on `LayoutLens` take a `mode`:
- `"axe"` — deterministic axe-core only, no API key, `confidence` always `1.0`.
- `"hybrid"` (default) — axe-core + LLM vision; axe findings are injected into
  the LLM prompt as grounding context, and **if axe finds any violation the
  final verdict is forced to "no"** (confidence `1.0`) regardless of what the
  LLM said. If axe finds nothing, the LLM's own answer/confidence stand.
- `"llm"` — legacy vision-only check, no axe involved, needs an API key.

**To update the vendored axe-core version:** download the new
`axe.min.js`/license from the [axe-core releases](https://github.com/dequelabs/axe-core/releases),
replace the files in `layoutlens/a11y/assets/`, and bump `AXE_VERSION` in
`layoutlens/a11y/axe.py` to match. Re-run
`uv run python benchmarks/generators/generate_a11y_ground_truth.py --check`
(see Benchmarks below) to confirm the accessibility fixtures' ground truth
still matches.

## Test Suites (YAML/JSON)

`UITestSuite.from_dict(...)` / `UITestSuite.load(...)` (JSON) load a suite;
there is no CLI for suites — `await lens.run_test_suite(suite)` is Python-only.

**Breaking change (v1.7.0):** every test case must declare `expected_results`
(`answer: "yes"|"no"` and/or `contains: [...]`) — a case with neither raises
`ValidationError` at load time. There is no confidence-only fallback anymore.
See `examples/sample_test_suite.yaml` for a complete example, and
`layoutlens/api/test_suite.py` (`_evaluate_case_assertions`) for exactly how
assertions are graded (`assertion_detail` is attached to each result's
metadata and included in `UITestResult.to_json()`).

## Benchmarks

`benchmarks/` holds 18 HTML fixtures / 74 labeled yes/no queries across 4
categories, with answer keys in `benchmarks/answer_keys/`.

```bash
# 1. Run LayoutLens over all fixtures
uv run python benchmarks/run_benchmark.py --no-batch --output benchmarks/run_out

# 2. Score deterministically (leading yes/no token vs. answer key;
#    ambiguous/unparseable answers count as INCORRECT, never free "no" credit)
uv run python benchmarks/evaluation/evaluator.py \
  --answer-keys benchmarks/answer_keys \
  --results benchmarks/run_out \
  --output benchmarks/results/$(date +%F)_gpt-4o-mini.json
```

**Honest-numbers policy:** only commit a results artifact from a real
measured run. The current committed artifact
(`benchmarks/results/2026-07-21_gpt-4o-mini.json`) is real: 81.1% (60/74,
gpt-4o-mini, 7 ambiguous counted incorrect). Do not hand-edit accuracy
numbers in docs — regenerate the artifact and update the number together, in
the same commit, from an actual run.

## Testing Commands

```bash
uv run ruff check --fix && uv run ruff format   # Lint + format, zero tolerance for failures
uv run pytest tests/ -v                          # Full suite
uv run pytest tests/ -v -m "not browser"         # Skip tests that launch a real Chromium browser
uv build                                         # Build the wheel/sdist
```

The `browser` pytest marker (`pytest.mark.browser`) flags tests that launch a
real Chromium instance via Playwright — slower and require
`playwright install chromium` first.

## Development Standards

- Google-style docstrings throughout.
- Async-first: any new method that captures a screenshot or calls an LLM
  must be `async`.
- No backward-compatibility shims unless explicitly requested — breaking
  changes are fine when they're the correct fix; document them clearly in
  `CHANGELOG.md`.
- Docs (`README.md`, `docs/`, this file) must match actual code behavior,
  verified by running the commands/snippets, not by inference. When you
  change a public signature, CLI flag, or module layout, update the docs in
  the same change.
- Don't fabricate benchmark or accuracy numbers — they must come from a real
  run of the evaluator, committed as an artifact under `benchmarks/results/`.
