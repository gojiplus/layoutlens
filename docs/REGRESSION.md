# Structured regressions and migration to 3.0

Python 3.12+ and Chromium are required. `compare(before, after)` replaces the
old list-of-screenshots/query API and returns `DiffReport`. `ComparisonResult`
is removed. `compare_with_expert(before, after, expert_persona, intent=...)`
adds explanation to a measured diff. Generic screenshot questions still use
`analyze()`.

## Capture and replay

```python
from layoutlens import RenderState, capture_state, diff

baseline = await capture_state("checkout.html", revision="BASE_COMMIT")
baseline.save("artifacts/baseline")
candidate = await capture_state("checkout.html", revision="CANDIDATE_COMMIT")
candidate.save("artifacts/candidate")
report = diff(RenderState.load("artifacts/baseline"), candidate, repository=".")
```

Each artifact is a new directory containing `state.json`, `screenshot.png`,
and `dom.html`. Asset SHA-256 hashes are verified on load. Unsupported schema
versions and corrupt assets raise errors. Saving never overwrites a baseline;
review and explicitly replace baseline directories through your normal version
control or artifact workflow. DOM/text/screenshot artifacts contain page data;
store them with the same access controls as your test captures.

`capture_page(page)` records an existing Chromium page, including caller-set
focus or interaction state. Capture disables animations, hides carets, and uses
light color scheme and reduced motion. It waits for fonts and image decoding,
then checks that measurements stayed stable across evidence and screenshot
acquisition. Open shadow DOM is traversed; closed roots, frame interiors,
canvas, and video are reported as coverage gaps.

Coordinates are floating-point document CSS pixels. Screenshots also record
DPR; pixel-only differences are observations. Temporary local-server origins are
normalized only during comparison; raw artifacts retain the browser values. Default geometric significance tolerance
is 1 CSS pixel. Text-line, visibility, and relationship transitions
remain explicit. Geometric reading order is not an accessibility reading-order
claim. Unique test IDs and IDs are matched first; ambiguous feature matches
abstain and make comparison incomplete.

## Findings and gates

`diff()` replays the shared layout predicates against captured evidence.
Findings are introduced, worsened, unchanged, resolved, or unresolved. A
candidate is not proof of broken design. Intentional overlap, target-size
exceptions, and other context require review.

- `qualified` is the default: only independently qualified introduced/worsened
  findings block. No layout rule ships qualified.
- `findings` explicitly blocks introduced/worsened candidates, without
  upgrading their evidence level.
- `nothing` reports findings without blocking.

`Qualification` records bind a sealed independent dataset, provenance, counts,
rule version/configuration, and exact capture conditions. The two-sided 95%
Wilson precision lower bound must be at least 99%. With zero false positives,
381 reviewed positive predictions are needed. Fixture tests are development
checks and cannot be submitted as independent qualification evidence.

`Verification` binds the reviewer, supporting evidence, and resolved manual
exceptions to a rule/selector and the exact `RenderState.fingerprint`.
Verification does not qualify a rule. A qualification cannot bypass unresolved manual exceptions.

`report.gate_status` is `pass`, `fail`, or `incomplete`. Environment mismatch,
unstable captures, unsupported regions, missing evidence, and ambiguous
correspondence prevent a passing result. A lack of source attribution alone
does not invalidate measured geometry.

Standalone `assert_layout()` now warns for candidates by default. Use
`assert_layout(..., policy="findings")` for the old strict intention, and
`assert_regression(before, after)` for baseline-aware checks. `LayoutReport.ok`
continues to mean no candidate findings, not empirical defect qualification.
Hybrid layout analysis preserves measured candidates without forcing the model
answer to a statistically certain verdict. Deterministic `AnalysisResult`
confidence is unestimated (`0.0` with `confidence_kind="not_estimated"`).
Axe findings retain their separate rule-outcome semantics.

## Source attribution

Each changed property can carry matched CSS declarations, stylesheet ranges,
inline values, available source-map locations, and missing-link reasons.
Declarations are candidate causes; matching a declaration does not prove it
won the cascade or caused a defect. Source maps are saved with the resolved
location evidence so replay does not fetch them again.

Git attribution requires an explicit repository and both revision labels.
Local paths must resolve inside that repository, and the captured declaration
or embedded source-map content must agree with the candidate revision. Remote
application URLs without a verified local mapping retain stylesheet URLs.
Unavailable maps, dynamic styles, and unresolvable locations remain explicit.

## CLI and agent tools

```bash
layoutlens capture before.html --save artifacts/baseline
layoutlens capture after.html --save artifacts/candidate
layoutlens diff artifacts/baseline artifacts/candidate --output json
layoutlens diff artifacts/baseline artifacts/candidate --fail-on findings --output sarif
```

Capture/diff exit codes are 0 for complete success, 1 for a blocking finding,
and 2 for execution errors or incomplete evidence. MCP exposes
`capture_render_state` and structured `compare_ui`; neither requires a key.
Optional model explanation cannot mutate evidence or gate decisions.

## Coordinated release

Build and test the LayoutLens wheel on Python 3.12 and the highest supported
Python, then exercise UIJudgeBench adapters and Action report handling against
that wheel. Publish LayoutLens 3 before its consumers: UIJudgeBench declares
`layoutlens>=3.0.0,<4` with Python 3.12+, and Action v2 pins LayoutLens 3.
The `judge` extra in UIJudgeBench no longer requests LayoutLens's removed
`gemini` extra. This change does not collect benchmark labels, qualify rules,
or publish any package automatically.
