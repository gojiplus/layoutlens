# Changelog

All notable changes to LayoutLens are documented in this file.

## [Unreleased]

## [2.1.0] - 2026-08-17

### Added

- Deterministic `text-occlusion` findings sample rendered text fragments across the
  full document and identify the painted DOM element covering them. This includes graph
  lines drawn over labels and general overlays; it is a visual-quality rule, not a WCAG
  success criterion.
- Deterministic `focus-obscured` findings exercise keyboard-focusable components and report
  components entirely hidden by author DOM content, implementing the automatable geometric
  core of WCAG 2.4.11 Focus Not Obscured (Minimum).

### Fixed

- `target-size` now checks the WCAG 2.5.8 spacing-circle, inline-target, and unmodified
  user-agent-control exceptions instead of reporting every target below 24 by 24 CSS pixels.
  Findings explicitly retain equivalent-control and essential-presentation as manual-review
  exceptions rather than pretending those semantic questions are automated.

### Documentation

- Separate LayoutLens's role as a deterministic system under test from UIJudgeBench's
  independent ownership of benchmark pages, admission oracles, gold labels, and scoring.

## [2.0.0] - 2026-08-15

### Added

- **`check_layout(source, mode="hybrid"|"deterministic"|"llm")`** — the
  deterministic layout scorer now grounds and can overrule the vision model,
  exactly like axe-core does for accessibility: one browser session for
  screenshot + scan, `LayoutReport.summary()` injected as LLM context, and
  measured defects forcing the verdict to "no" at confidence 1.0.
  `deterministic` mode is fully keyless. CLI: `--layout {hybrid,deterministic,llm}`.
- **Three new layout detectors**: page-level horizontal overflow, ellipsis
  text truncation, and left-edge viewport protrusion.
- **pytest plugin** (auto-registered): `layoutlens` fixture with keyless
  `assert_a11y`/`assert_layout` (fail with rule ids, selectors, and measured
  numbers) and LLM-backed `assert_ui` (skips without an API key or with
  `--layoutlens-no-llm`).
- **MCP server** (`layoutlens-mcp`, extra `layoutlens[mcp]`): tools
  `audit_accessibility` + `scan_layout` (keyless, compact summaries) and
  `check_ui` + `compare_ui` (vision LLM).
- **SARIF 2.1.0 output** (`--output sarif` with `--a11y`/`--layout`),
  validated against the official OASIS schema, for GitHub Code Scanning.
- `JudgeResult.prompt_sha256` (judge-contract pinning),
  `batch_usage_summary()`, and `BatchResult` token totals +
  `estimated_cost_usd`.
- `UITestSuite.from_yaml`/`from_specs`; `layoutlens --suite FILE`;
  `run_test_suite(parallel=..., max_workers=...)` actually parallelizes.
- `benchmarks/run_benchmark.py --model/--provider/--api-base` (harness is now
  model-agnostic).

### Fixed

- `compare()` sent only the first screenshot to the vision model (the rest
  were pasted in as filenames); it now sends every image with an "Image N"
  legend, and renders each source once instead of twice.
- Cache keys now include model/provider/api_base and an instructions hash —
  previously a persistent cache could serve one model's answers for another.
- Typed errors from single-source `analyze()` calls now propagate instead of
  being flattened into error-results; batch runs still isolate per item.
- The analyze-path JSON parser now tolerates nested objects and code fences
  (shared with the judge parser).
- Capture batches share one Chromium launch instead of one per URL.

### Changed (breaking)

- `audit_accessibility` merged into `check_accessibility(compliance_level=...)`;
  `check_mobile_friendly`/`check_conversion_optimization` removed (use
  `analyze_mobile_ux`/`optimize_conversions`).
- `run_test_suite`/`create_test_suite` are real methods (no monkey-patching).
- browser-use integration rewritten as `validate_agent_run(lens, history)`
  over the stable `AgentHistoryList` seam (the old per-step hooks targeted an
  API browser-use removed and silently no-oped); extra pinned
  `browser-use>=0.13,<0.14`.
- Removed: `streamlit/` app, `Config`/`config.py`, prompt-optimizer
  heuristics, unused exception classes (`APIError`, `RateLimitError`,
  `ScreenshotError`, `NetworkError`, `TestSuiteError`, custom `TimeoutError`).
- `Instructions`/`UserContext`/`get_expert`/`list_available_experts` exported
  at top level; `Instructions.for_healthcare()`/`for_finance()` added.
- aiohttp/openai overridden past browser-use's lockstep pins to pick up
  security-patched litellm/aiohttp lines.

### Changed

- **Adopted the py-canon fleet standard** (`preen adopt --release-migration`):
  - Build backend switched from `uv_build` to hatchling + uv-dynamic-versioning;
    the version now derives from git tags (`vX.Y.Z`) instead of a static
    `version` field in `pyproject.toml`.
  - CI/docs/release/Dependabot-automerge workflows are now thin shims calling
    py-canon's reusable workflows. Playwright browser tests moved to a
    dedicated `browser.yml` workflow (the reusable CI has no pre-test hook).
  - Releases are cut by pushing a `v*` tag (or `preen release`); the old
    `python-publish.yml` (GitHub-release-triggered) was removed. CITATION.cff
    syncing moved to its own `citation-sync.yml`.
  - Ruff config replaced by the fleet standard: line length 120 → 88, a much
    wider rule set (docstrings, security, print bans outside CLIs/scripts).
  - Pyright (`standard` mode) is now a hard CI gate; the package is clean, and
    `analyze()`/`capture()` gained `@overload` signatures so single-source
    calls type as `AnalysisResult`/`str` rather than unions.
  - Docs build via the shared `py_canon.sphinx.configure` config, with `-W`
    (warnings are errors) and a doctest pass.

### Fixed

- `_initialize_default_logging` no longer assumes the layoutlens logger has a
  parent, and the `__init__` version fallback no longer references
  `importlib` from an except clause where it could be unbound.
- Placeholder URLs in docs/examples now use the RFC-reserved `example.com` /
  `example.org` domains.

## [1.9.0] - 2026-07-25

### 🚀 Major Features

- **Deterministic layout scorers** (`LayoutScorer`, `LayoutReport`, `LayoutFinding`,
  `check_contrast`, `contrast_ratio`, `read_computed_styles`, `element_geometry`):
  the geometry/contrast analog of the axe-core accessibility engine — keyless,
  LLM-free detectors that measure defects directly off the rendered page with the
  browser's own layout engine. Five defect classes: **contrast** (WCAG AA ratio,
  4.5:1 normal / 3.0:1 large, with the measured ratio), **overlap** (sibling
  bounding-box collision), **clipping** (content cut off by hidden overflow),
  **viewport-protrusion** (elements past the viewport width), and **target-size**
  (interactive targets under 24×24px, WCAG 2.5.8). Every finding is a receipt —
  offending selector, bbox, measured value, and violated threshold. `scan(source,
  viewport=...)` owns the browser; `scan_page(page)` runs on an open page. New
  module: `layoutlens/layout/`.
- The measurement math (WCAG relative-luminance/contrast-ratio, bbox intersection,
  `scrollHeight`/`clientHeight`, right-edge vs viewport) and the computed-style
  reader are ported verbatim from the UIJudgeBench render-verifier
  (`uijudge/engine/verify.py`, `wcag.py`, `referring.py`) — the same detectors the
  benchmark used to build its layout ground truth — generalized from verifying one
  claimed selector to scanning the whole page for every instance.

### ✅ Tests

- `tests/test_layout.py`: pure WCAG contrast-math unit tests against published
  pairs (`#767676`/white = 4.54:1) plus browser-marked tests that plant one defect
  per class and assert the matching finding fires with the right measured value,
  and that a clean page yields none.

## [1.8.0] - 2026-07-25

### 🚀 Major Features

- **Multi-provider batch judging** (`LayoutLens.judge_batch`, `BatchRequest`):
  the batched counterpart to `judge()` for bulk offline evaluation (e.g.
  UIJudgeBench) — provider batch APIs are ~50% cheaper and the correct transport
  for thousands of independent judgments. Each request sends its prompt
  **verbatim** with one image, **byte-identical** to `judge()` (a parity test
  enforces this by reusing the same message/result builders). Two backends,
  dispatched by model: `gemini/*` (AI Studio) uses a **google-genai inline
  batch** (optional extra `layoutlens[gemini]`, imported lazily); every other
  model (`gpt-*`/`openai/*`/`anthropic/*`/`vertex_ai/*`/`bedrock/*`) uses the
  **litellm file-based batch** (`acreate_file` → `acreate_batch` →
  `aretrieve_batch` → `afile_content`). Both are **resumable** via a manifest
  that persists submitted job ids before polling, so a killed run collects prior
  work and re-submits only uncovered ids (never re-billing). Missing images
  yield an `"unknown"` result instead of aborting the batch. New module:
  `layoutlens/api/batch.py`.
- **Reasoning-aware `max_tokens` defaults**: `judge()`/`judge_batch()` now
  default `max_tokens` to `AUTO`, which resolves to **8000 for reasoning/thinking
  models** (Gemini 3, Gemini 2.5, GPT-5, o1/o3/o4 — they spend thinking tokens
  inside the completion budget) and **300 otherwise**. An explicit integer still
  passes through unchanged. Detection lives in a data-driven registry
  (`param_policy.is_reasoning_model`), mirroring the temperature registry.
  `JudgeResult` gains **`truncated`**, set when the model stopped on the token
  budget (`finish_reason == "length"`), with a logged warning.
- **Faithful judge interface** (`LayoutLens.judge`, `JudgeResult`): LayoutLens
  can now serve as a reference judge for external evaluation harnesses (e.g.
  [UIJudgeBench](https://github.com/gojiplus/uijudge-bench)). The caller-supplied
  prompt is sent **verbatim** — no system persona, no query scaffolding, no
  appended JSON-format instruction — alongside a single image. The response is
  parsed (strict JSON, then a yes/no fallback, then `"unknown"`), refusals are
  detected, and a real token-usage split is returned. Judge calls always hit the
  model (no caching) so a harness controls its own prompt versioning.
  New module: `layoutlens/api/judge.py`.
- **Per-model parameter policy** (`layoutlens/param_policy.py`): a data-driven,
  ordered registry decides which sampling parameters are safe per model. Claude
  Sonnet 5 and Opus 4.6/4.7/4.8 reject non-default sampling params with a 400, so
  those patterns omit `temperature` entirely; every other model includes it.
  Wired into both the analyze path and `judge()`.
- **`api_base` support**: `LayoutLens(..., api_base=...)` (and `LLMConfig.api_base`)
  forwards `api_base` to every model call, enabling self-hosted / OpenAI-compatible
  endpoints such as Ollama and vLLM
  (`LayoutLens(provider="litellm", model="ollama/qwen2.5vl", api_base="http://localhost:11434")`).

### 🔧 Improvements

- **Token-usage split**: analysis metadata and `JudgeResult.usage` now record
  `prompt_tokens` and `completion_tokens` in addition to `total_tokens` (each
  defaults to 0 when the provider does not report it).
- **Analyze temperature is now configurable**: `_call_vision_api` no longer
  hardcodes `temperature=0.1`. It honors the new constructor `temperature`
  override (defaulting to 0.1 to preserve prior behavior), subject to the
  per-model parameter policy.

## [1.7.0] - 2026-07-21

### 🚀 Major Features

- **Deterministic accessibility engine**: vendored [axe-core](https://github.com/dequelabs/axe-core)
  4.10.3 (`layoutlens/a11y/`, assets under `layoutlens/a11y/assets/`) runs real
  WCAG 2.1 A/AA checks against a live Playwright-rendered page — no LLM, no
  API key, fully reproducible. New public exports: `AxeAuditor`, `A11yReport`,
  `A11yFinding`, `AXE_VERSION`.
- **Three accessibility modes** on `check_accessibility` / `audit_accessibility`:
  `"axe"` (deterministic only, keyless), `"hybrid"` (default — axe grounds the
  LLM's prompt and deterministically forces a "no" verdict on any violation),
  `"llm"` (legacy vision-only).
- **`--a11y {hybrid,axe,llm}` CLI flag** — `layoutlens page.html --a11y axe`
  runs a full WCAG scan with no API key configured. Mutually exclusive with
  `--query`.
- **Keyless construction**: `LayoutLens()` no longer requires an API key at
  construction time. The requirement is deferred to the first LLM call
  (`AuthenticationError`, provider-aware message), so deterministic-only
  workflows never need credentials.
- **browser_use findings verified against axe-core**: `AgentValidator`
  findings now carry a `verified` flag (`True`/`False`/`None`) cross-checked
  against a deterministic axe-core scan of the same page.

### 💥 Breaking Changes

- **YAML/JSON test suites now require `expected_results` per test case.** A
  case must declare `answer` ("yes"/"no") and/or `contains` (a list of
  required terms); a case with neither raises `ValidationError` at load time
  (`UITestSuite.from_dict`, `LayoutLens.create_test_suite`). There is no
  confidence-only fallback anymore — `run_test_suite` actually asserts
  against these expectations instead of trusting self-reported confidence.
  Per-case `expected_confidence` (default `0.7`) is honored as an additional
  gate, and `assertion_detail` (per-assertion pass/fail) is attached to each
  result's metadata and included in `UITestResult.to_json()`.

### 🔧 Fixes

- Fixed `_get_api_key_for_provider` selecting the wrong provider's API key
  environment variable in some configurations.

### 📊 Benchmarks

- Rewrote the benchmark evaluator to score structured yes/no answers
  deterministically; ambiguous/unparseable answers now count as **incorrect**
  instead of being silently treated as "no".
- Replaced fabricated accuracy claims (previously "95.2%", "31 test cases
  across 9 categories") with a real measured run: **81.1% (60/74)** on
  `gpt-4o-mini`, 18 fixtures / 74 queries / 4 categories, committed as
  `benchmarks/results/2026-07-21_gpt-4o-mini.json`.
- Accessibility fixtures are now grounded in real axe-core output
  (`axe_ground_truth` blocks per fixture, generated/verified by
  `benchmarks/generators/generate_a11y_ground_truth.py`).

### 📚 Documentation

- Rewrote `README.md`, `docs/`, and `CLAUDE.md` to describe the real flat CLI
  (`layoutlens SOURCES... [--query] [--compare] [--viewport] [--a11y] ...`)
  and package layout. Removed references to a prior architecture that no
  longer exists in this codebase (`vision/`, `providers/`, `cli_commands.py`,
  `cli_interactive.py`, `integrations/github.py`, and the `test`/`batch`/
  `interactive`/`generate`/`validate` subcommands).
- Added a Sphinx API page for the accessibility engine (`docs/api/a11y.rst`).
- Fixed several broken example snippets (wrong keyword argument names on
  `analyze()`, `compare()` called with local HTML paths instead of
  screenshots, benchmark fixture paths that no longer exist).

## [1.4.0] - 2024-12-21

### 🚀 Major Changes
- **LiteLLM Integration**: Complete migration to LiteLLM as the unified provider
  - Removed OpenRouter provider in favor of LiteLLM's unified interface
  - Support for OpenAI, Anthropic, Google via LiteLLM's standardized API
  - Simplified architecture with single provider handling all models
  - Model naming follows LiteLLM conventions (e.g., "anthropic/claude-3-5-sonnet")

### 🎯 Breaking Changes
- **No backward compatibility** for OpenRouter provider
- Removed `openrouter` from provider choices
- Updated default provider to `openai` (via LiteLLM)
- Changed API key environment variable references (removed OPENROUTER_API_KEY)

### 🔧 Updated Provider Support
- **Provider Options**: `openai`, `anthropic`, `google`, `gemini`, `litellm`
- **Unified Interface**: All providers use LiteLLM for consistent behavior
- **Model Format**: LiteLLM naming convention for all models

## [1.3.0] - 2024-01-21

### 🚀 Major Features Added
- **Multi-Provider Support**: Complete plugin architecture for AI providers
  - LiteLLM integration for unified access to 25+ AI models
  - Support for OpenAI, Anthropic Claude, Google Gemini, and more
  - Factory pattern for easy provider instantiation and management
  - Backward compatibility with existing OpenAI-only code

### 🎯 Interactive Mode
- **Interactive CLI**: New `layoutlens interactive` command for real-time analysis
  - Session statistics and progress tracking
  - Rich terminal formatting (optional, falls back gracefully)
  - Live progress indicators and error handling
  - Command history and help system

### 🔧 Enhanced CLI Experience
- **Provider Selection**: `--provider` flag with choices (litellm, openai, anthropic, google, gemini)
- **Model Selection**: `--model` flag for specifying exact models
- **Enhanced Info Command**: Shows available providers, models, and API key status
- **Unified API Keys**: Support for OPENAI_API_KEY environment variable

### 🏗️ Architecture Improvements
- **Provider Architecture**: Abstract base classes with unified interface
  - VisionProvider, VisionProviderConfig, VisionAnalysisRequest/Response
  - LiteLLMProvider as unified gateway to multiple AI services
  - Extensible factory pattern for adding new providers

### 📦 Dependencies
- **Optional Rich Support**: Enhanced interactive mode with `pip install layoutlens[interactive]`
- **OpenAI SDK**: Single dependency for all provider communication via OpenRouter

### 🧪 Testing
- **Comprehensive Provider Tests**: 40+ tests covering provider architecture
- **Integration Tests**: Full API integration with provider system
- **Interactive Mode Tests**: Session management and progress tracking
- **Backward Compatibility**: Ensures existing code continues to work

## [1.2.0] - 2024-01-20

### 🚀 Major Features Added
- **Async Processing**: Added high-performance async analysis methods
  - `analyze_async()` - Single page async analysis
  - `analyze_batch_async()` - Concurrent batch processing with configurable limits
  - 3-5x performance improvement for batch operations
  - Semaphore-based concurrency control to prevent API overload

### 🔧 CLI Enhancements
- Added `--async` flag to main CLI for async processing
- Added `--max-concurrent` parameter for concurrency control
- New dedicated `layoutlens-async` CLI with enhanced batch commands
- Added async support to test and compare commands

### 📚 Documentation
- Updated README with async examples and performance metrics
- Added comprehensive async usage examples
- Updated CLI help text with async command examples

### 🐛 Bug Fixes
- Fixed pytest class name conflicts (TestCase → UITestCase, etc.)
- Enhanced error handling in batch operations
- Improved type annotations for Python 3.11+ compatibility

### 🔧 Developer Experience
- Enhanced pre-commit hooks with full CI/CD integration
- Improved GitHub Actions workflows (ci.yml, docs.yml, python-publish.yml)
- Added performance benchmarking tests
- Clean up of unused imports and linting improvements

## [1.1.0] - 2024-01-15

### ✨ Features Added
- Production-ready test suites with `UITestCase` and `UITestSuite`
- Smart caching system with memory and file backends
- Comprehensive exception hierarchy for better error handling
- Enhanced CLI with regression testing commands

### 🔧 Improvements
- Modernized type annotations for Python 3.11+
- GitHub Pages documentation with Furo theme
- Comprehensive integration tests with mocked OpenAI API
- Pre-commit hooks and local CI/CD setup

### 🐛 Bug Fixes
- Fixed CLI regression command implementation
- Improved error handling across the codebase
- Better resource management and cleanup

## [1.0.2] - 2024-01-10

### 🔒 Security
- **CRITICAL**: Fixed API key logging vulnerability in CLI
- Enhanced security practices across the codebase

### 🐛 Bug Fixes
- CLI no longer exposes API keys in logs
- Improved error handling for missing dependencies

## [1.0.1] - 2024-01-05

### 🐛 Bug Fixes
- Fixed import issues in certain environments
- Improved error messages for missing API keys
- Better handling of screenshot capture failures

## [1.0.0] - 2024-01-01

### 🎉 Initial Release
- Core LayoutLens functionality for UI testing
- Natural language visual analysis using GPT-4 Vision API
- Screenshot capture with Playwright
- Accessibility and mobile-friendly checks
- Basic CLI commands (test, compare, generate)
- Support for multiple viewports and queries
