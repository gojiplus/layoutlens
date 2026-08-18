# CLAUDE.md - LayoutLens

Guidance for Claude Code when working in this repository. Describes what the
code actually does — verify against source before trusting older assumptions;
this file has drifted from reality before.

## Project Overview

LayoutLens is an AI-powered UI testing framework: it captures screenshots with
Playwright and answers natural-language questions about them via a
vision-capable LLM (through LiteLLM; `gpt-4o-mini` by default). It also ships
a fully deterministic, keyless accessibility engine: vendored axe-core for
WCAG 2.1 A/AA plus focused WCAG 2.2 geometry checks in `LayoutScorer`.

## Package Structure (real, as of v2.1.0)

```
layoutlens/
├── __init__.py                    # Public exports
├── api/
│   ├── core.py                    # LayoutLens class (analyze/compare/capture/checks)
│   ├── judge.py                   # judge() + JudgeResult (verbatim-prompt vision judge)
│   ├── batch.py                   # judge_batch() + BatchRequest (multi-provider batch)
│   └── test_suite.py              # UITestCase/UITestSuite/UITestResult + run_suite_case
├── a11y/
│   ├── axe.py                     # AxeAuditor, AXE_VERSION
│   ├── types.py                   # A11yFinding, A11yReport
│   └── assets/                    # Vendored axe-core bundle (axe.min.js, LICENSE-axe.txt)
├── layout/                        # Deterministic geometry/contrast scorers (keyless, no LLM)
│   ├── geometry.py                # geometry + target exceptions + focus/text occlusion
│   ├── contrast.py                # WCAG contrast math + check_contrast page scan
│   ├── styles.py                  # read_computed_styles, element_geometry
│   └── types.py                   # LayoutFinding, LayoutReport
│                                  #   (math ported from UIJudgeBench's render-verifier)
├── prompts/                       # Expert persona system (Instructions, get_expert, ...)
├── integrations/
│   └── browser_use/               # validate_agent_run (post-run validation) + reports
├── browser.py                     # Playwright page lifecycle (open_page) + ViewportConfig
├── capture.py                     # Capture: screenshot capture for URLs/HTML files
├── cli.py                         # The entire CLI (one file, one command)
├── cache.py                       # AnalysisCache (memory/file backends)
├── logger.py                      # Structured logging setup
├── exceptions.py                  # Custom exception hierarchy
└── types.py                       # Enums (Viewport, Expert, ComplianceLevel, ...) + TypedDicts
```

There is **no** `vision/`, `providers/`, `config.py`, `streamlit/`,
`cli_commands.py`, or `integrations/github.py` — those belonged to earlier
architectures and no longer exist. Don't reintroduce them or write docs that
assume they exist. `check_mobile_friendly`/`check_conversion_optimization`/
`audit_accessibility` were removed in v2.0.0 (use `analyze_mobile_ux`/
`optimize_conversions`/`check_accessibility`).

## CLI

The CLI is a single flat command — there are no subcommands (`test`, `batch`,
`interactive`, `generate`, `validate` do not exist):

```bash
layoutlens SOURCES... [--query TEXT] [--compare] [--suite FILE] \
  [--viewport {desktop,mobile,tablet}] [--a11y {hybrid,axe,llm}] \
  [--layout {hybrid,deterministic,llm}] \
  [--output {text,json,sarif}] [--api-key KEY] [--model MODEL]
```

- Positional args that are URLs or existing paths become sources; a leftover
  positional string (if `--query` wasn't given) becomes the query.
- `--a11y {hybrid,axe,llm}` runs the built-in WCAG checks instead of a
  free-form query; it is an error to combine `--a11y` with `--query`.
  `--a11y axe` is fully deterministic and needs no API key.
- `--layout {hybrid,deterministic,llm}` runs the deterministic geometry/
  contrast/occlusion scan (`check_layout`): contrast, overlap, clipping,
  protrusion (both edges), page-level horizontal overflow, text truncation,
  WCAG-aware target size, complete focus obscuration, and text occlusion.
  `deterministic` needs no API key; in `hybrid` the measured findings ground
  the LLM and force a "no" verdict when any defect is measured.
- `--output sarif` (with `--a11y` or `--layout`) emits a SARIF 2.1.0 log for
  GitHub Code Scanning (`layoutlens/sarif.py`; validated against the official
  OASIS schema).
- `--compare` compares the first two sources; `compare()` (CLI and Python)
  accepts URLs, local HTML files, or screenshot images. Every source is
  rendered once and every screenshot is sent to the vision model, with an
  "Image N" legend mapping images to sources.
- `--suite FILE` runs a YAML/JSON test suite (exit code 1 if any case fails);
  it cannot be combined with sources, `--query`, `--compare`, or `--a11y`.

Run `layoutlens --help` for the authoritative flag reference.

## API

Everything on `LayoutLens` that touches the network or a browser is `async` —
call with `await` inside an `async def`, or wrap top-level scripts in
`asyncio.run(...)`.

```python
from layoutlens import LayoutLens

lens = LayoutLens(
    api_key=None,  # optional; falls back to the provider's env var.
    # NOT required at construction (see below)
    model="gpt-4o-mini",
    provider="openai",  # "openai" | "anthropic" | "google" | "gemini" | "litellm"
    output_dir="layoutlens_output",
    cache_enabled=True,
    cache_type="memory",  # "memory" | "file"
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

## Faithful Judge Interface (v1.8.0)

`LayoutLens.judge(image_path, prompt, *, max_tokens=AUTO) -> JudgeResult` is the
reference-judge surface for external eval harnesses (UIJudgeBench). Unlike
`analyze`, it sends the prompt **verbatim**: no system persona, no
`_format_query_prompt` scaffolding, no appended JSON contract. One user message
(`[text=prompt, image]`). It bypasses the cache (every call hits the model) and
is persona/instructions-free. A missing image raises `ValidationError`.

- **`layoutlens/api/judge.py`** — `JudgeResult` (answer/confidence/rationale/raw/
  refused/usage/model/parse_mode), `judge()`, `parse_judge_response()`
  (strict JSON → yes/no fallback → `"unknown"`; `reasoning` aliases `rationale`),
  `detect_refusal()`. In tests, `acompletion` is patched at
  `layoutlens.api.judge.acompletion` (mirroring `layoutlens.api.core.acompletion`).
- **`layoutlens/param_policy.py`** — `completion_params(model, *, temperature,
  max_tokens)` + `model_omits_temperature(model)`. Ordered `fnmatch` registry;
  first match wins. **Claude Sonnet 5 / Opus 4.6-4.8 return HTTP 400 on any
  non-default sampling param, so those patterns omit `temperature`.** Wired into
  both `_call_vision_api` and `judge()`.
- **`api_base`** — `LayoutLens(..., api_base=...)` forwards `api_base` to
  every `acompletion` call (Ollama/vLLM/OpenAI-compatible).
- **Usage split** — `_read_usage` records prompt/completion/total tokens in
  analysis metadata and `JudgeResult.usage` (0 when the provider omits them).

## pytest Plugin & MCP Server (v2.1.0)

- `layoutlens/pytest_plugin.py` registers via the `pytest11` entry point: a
  session-scoped `layoutlens` fixture with keyless `assert_a11y`/`assert_layout`
  and LLM-backed `assert_ui` (skips without a key / with `--layoutlens-no-llm`).
  Tested via pytester in `tests/test_pytest_plugin.py`.
- `layoutlens/mcp_server.py` (extra `layoutlens[mcp]`, script `layoutlens-mcp`,
  FastMCP): tools `audit_accessibility`/`scan_layout` (keyless, compact
  summaries — never raw axe JSON) and `check_ui`/`compare_ui` (LLM).
- `layoutlens/sarif.py` emits SARIF 2.1.0 for both deterministic engines
  (validated against the official OASIS schema).

## Deterministic Accessibility (axe-core)

`layoutlens/a11y/` wraps a vendored axe-core bundle
(`layoutlens/a11y/assets/axe.min.js` + `LICENSE-axe.txt`, version pinned in
`AXE_VERSION` in `layoutlens/a11y/axe.py`), injected into a live Playwright
page via `AxeAuditor`.

```python
from layoutlens import AxeAuditor

report = await AxeAuditor(run_only=["wcag2a", "wcag2aa"]).audit(source, viewport)
```

`check_layout(source, viewport=..., mode="hybrid"|"deterministic"|"llm")`
mirrors the accessibility stack for the layout scorers: one browser session
for screenshot + scan, `LayoutReport.summary()` injected as LLM grounding,
and a deterministic override (measured defects force "no", confidence 1.0).

`check_accessibility` on `LayoutLens` takes a `mode` (plus `compliance_level`
and optional `standards`/`instructions`):
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

`UITestSuite.load(...)` loads a suite from JSON **or YAML** (by extension;
`from_yaml`/`from_dict`/`from_specs` also exist). Run with
`await lens.run_test_suite(suite, parallel=..., max_workers=...)` (real methods
on `LayoutLens` as of v2.0.0 — no more monkey-patching), or from the CLI with
`layoutlens --suite FILE`.

**Breaking change (v1.7.0):** every test case must declare `expected_results`
(`answer: "yes"|"no"` and/or `contains: [...]`) — a case with neither raises
`ValidationError` at load time. There is no confidence-only fallback anymore.
See `examples/sample_test_suite.yaml` for a complete example, and
`layoutlens/api/test_suite.py` (`_evaluate_case_assertions`) for exactly how
assertions are graded (`assertion_detail` is attached to each result's
metadata and included in `UITestResult.to_json()`).

## Benchmarks

`benchmarks/` holds 18 HTML fixtures / 74 labeled yes/no queries across 4
categories, with answer keys in `benchmarks/answer_keys/`. The full-scale
sibling benchmark is https://github.com/gojiplus/uijudge-bench (vendors this
repo's browser/axe modules; LayoutLens is a planned baseline there).

```bash
# 1. Run LayoutLens over all fixtures
uv run python benchmarks/run_benchmark.py --no-batch --output benchmarks/run_out \
#   [--model MODEL --provider PROVIDER --api-base URL]  # harness is model-agnostic

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
uv run pyright                                   # Type check (CI gate, standard mode over layoutlens/)
uv run pytest tests/ -v                          # Full suite
uv run pytest tests/ -v -m "not browser"         # Skip tests that launch a real Chromium browser
uv build                                         # Build the wheel/sdist
uv run sphinx-build -W -q -b html docs /tmp/_site  # Docs build; warnings are errors in CI
```

The `browser` pytest marker (`pytest.mark.browser`) flags tests that launch a
real Chromium instance via Playwright — slower and require
`playwright install chromium` first.

## Fleet Standard (py-canon) and Releases

This repo is adopted into the [py-canon](https://github.com/gojiplus/py-canon)
fleet standard (`.copier-answers.yml` tracks the template version; `preen
check` audits conformance). Consequences that matter here:

- **Version comes from git tags** (hatchling + uv-dynamic-versioning). There
  is no static `version` in `pyproject.toml`; do not add one. A release is
  `git tag vX.Y.Z && git push --tags` (or `preen release X.Y.Z`) — the tag
  triggers `release.yml`, which tests, builds, publishes to PyPI via trusted
  publishing, and creates the GitHub Release. `citation-sync.yml` then
  updates CITATION.cff.
- **CI is a shim** (`.github/workflows/ci.yml`) calling py-canon's
  reusable-ci: ruff + pyright lint, a 3-OS × 3.11–3.14 test
  matrix, a wheel install smoke test, zizmor workflow-security lint, and
  dependency review. `docstrings.yml` runs pydoclint in an isolated uv tool
  environment to avoid its parser dependency collision. Do NOT add jobs to
  `ci.yml` — `preen update` overwrites
  it wholesale. Repo-specific CI lives in sibling workflows:
  `browser.yml` (installs Chromium, runs `pytest -m browser` — the reusable
  CI has no pre-test hook, so browser tests skip there) and
  `citation-sync.yml` and `docstrings.yml`. Pin third-party actions by SHA
  (zizmor gates on it).
- **Dependabot auto-merges** via `dependabot-auto-merge.yml` (py-canon
  reusable): GitHub-Actions updates and minor/patch Python bumps merge once
  every check is green; majors wait for a human.
- Docs build with `-W` and a doctest pass through the shared
  `py_canon.sphinx.configure` (see `docs/conf.py`). Docstring `>>>` blocks
  are illustrative and deliberately not executed
  (`doctest_test_doctest_blocks=""`).

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
