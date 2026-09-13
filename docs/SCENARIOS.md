# Stateful scenarios and local browser matrices

LayoutLens 4 adds stateful scenarios and local browser selection. A scenario runs in one
browser context, records actions and focus transitions, and captures a
`RenderState` at each named checkpoint. It needs no model or API key.

```python
from layoutlens import Scenario

scenario = (
    Scenario("/checkout", base_url="http://localhost:3000")
    .tab()
    .expect_focus("email")
    .type("me@example.com")
    .click("Continue")
    .expect_visible("payment")
    .checkpoint("payment")
)
report = await scenario.run(browser="firefox", viewport=(1280, 800))
report.save("artifacts/checkout-firefox")
assert report.gate_status == "pass", report.to_json()
```

Start your application before running this example. Local HTML files also work;
LayoutLens serves the file and its neighboring assets over a temporary local
HTTP server. `navigate()` follows routes in the existing context, retaining
cookies and storage. Builder methods return a new scenario, so one definition
can be reused across browsers. The [standalone checkout example](../examples/stateful_checkout.py)
creates its own pages and runs all three engines.

## Actions and expectations

A plain target such as `email` resolves by exact ID, then accessible label, then
test ID, then exact text. Use `css=#checkout button`, `#email`, or a Playwright
selector with an explicit engine prefix such as `role=button[name="Continue"]`
when you need explicit targeting. Prefix bare CSS tag selectors with `css=`. A selector that matches several
elements is an execution error for single-element actions; the runner never
picks an arbitrary match. `expect_count()` deliberately accepts multiple matches.

| Interaction | Methods and evidence |
|---|---|
| Keyboard navigation | `tab()`, `tab(backwards=True)`, `press("Escape")`; focused element, bounding box, styles, and focus events |
| Form entry | `type(text)` enters text into the focused editable element; `fill(target, text)` replaces a control's value |
| Hover content | `hover(target)`, `expect_visible(target)`, `expect_hidden(target)` |
| Dialog dismissal | `click("Close").expect_hidden("#dialog")` or `press("Escape").expect_hidden("#dialog")` tests a declared close path |
| Overlay interference | `expect_clickable(target)` runs Playwright's actionability checks without clicking; failed clicks retain target hit-test samples |
| Focus appearance | `expect_style("email", "outline-width", "3px")` tests a design contract; receipts retain computed focus-style changes |
| Keyboard reachability | `expect_tab_reaches("Continue", max_tabs=20)` records a bounded Tab sequence and fails if it does not reach the target |
| Responsive navigation | `resize(390, 844)` changes the existing page; follow it with visibility or style expectations |
| Dragging and pointers | `drag(source, target)`, `pointer_move(x, y)`, `pointer_down()`, `pointer_up()` |
| Routes and content | `navigate(url)`, `expect_url("/payment")`, `expect_text(target, text)`, and named checkpoints |

Checkpoints preserve focus, DOM attributes, color scheme, and motion preference.
They wait for fonts and images and check for changes during capture. They do not
stop animations or reset the application. Use explicit expectations to wait for
the application state you intend to test. Animated or changing captures can be
incomplete.

A repeated focus target, fully obscured focus, an obscured click target, or
multiple visible modals can produce a **candidate finding** with measurements
and unresolved exceptions. These observations do not prove a keyboard trap or
an inaccessible dialog. Intentional focus containment and nested modal workflows
can be valid. A bounded reachability failure means only that the specified
sequence did not reach its target within the configured bound.

Focus styling checks do not establish WCAG focus-appearance conformance.
Computed outlines and borders do not account for every pseudo-element, image,
contrast condition, or surrounding pixel. Use the screenshot and declared
expectations to inspect the evidence.

## Outcomes and saved evidence

- `pass`: all steps ran, checkpoints were complete, and the selected policy passed.
- `fail`: an explicit expectation failed, or `policy="findings"` selected a candidate finding.
- `incomplete`: navigation or an action failed, a checkpoint was unstable or lacked required evidence, or event retention reached its limit.

The default `qualified` policy leaves automatic interaction candidates as
warnings. Explicit expectations are user-declared contracts and can fail a run
without statistical qualification of a heuristic. `nothing` reports failures
without blocking; execution gaps still produce `incomplete`.

Expectations continue after a failed assertion so later checkpoints can retain
evidence. Action errors stop the sequence and attempt a failure checkpoint.
Unexpected native browser dialogs are dismissed and mark the run incomplete.
New windows also mark it incomplete; the runner follows the original page.
DOM dialogs and navigation within that page are supported.

`report.steps` contains before/after focus and target receipts. `report.events`
contains ordered focus, keyboard, input, pointer, drag, and navigation events.
Typed characters are masked in keyboard events and input values are omitted from
the event log. Reports retain a SHA-256 fingerprint of the steps, including their
arguments; this is an identity check, not a way to protect secret input. Definitions exported by `scenario.to_dict()` include their typed
values. Checkpoints contain page data, including visible form values; password
control values are redacted. DOM attributes and screenshots are not scrubbed. Save artifacts with the same care as application test data.
Events before instrumentation starts are not replayed; the first step records
the current page state. The run retains at most 10,000 events.

```python
from layoutlens import ScenarioReport

baseline = ScenarioReport.load("artifacts/baseline")
candidate = ScenarioReport.load("artifacts/candidate")
regression = baseline.diff(candidate, policy="findings")
assert regression.gate_status == "pass"
```

Comparison matches checkpoints by name and reports changed focus transitions.
Missing checkpoints, different definitions (including action arguments), and incompatible capture
conditions prevent a passing comparison. The per-checkpoint `DiffReport` contains
the rendered deltas. Across routes in one run, the saved states are also available
as `report.checkpoints[name]` for direct inspection or explicit comparison.

## Browser configuration

Install the local engines you intend to use:

```bash
playwright install chromium firefox webkit
```

`Scenario.run()`, `capture_state()`, and `LayoutLens()` accept `browser`,
`color_scheme`, `reduced_motion`, `locale`, `timezone_id`, and
`device_scale_factor`. Capture and scenario APIs accept named viewports or a
`(width, height)` tuple in CSS pixels. Lower-level capture and auditor objects
accept a `BrowserConfig` through their `browser_config` argument.

```python
for engine in ("chromium", "firefox", "webkit"):
    report = await scenario.run(
        browser=engine,
        viewport=(1280, 800),
        color_scheme="dark",
        reduced_motion="reduce",
        locale="en-US",
        device_scale_factor=2,
    )
    report.save(f"artifacts/{engine}")
```

Each state identifies its actual browser/version, viewport, DPR, user agent,
platform, locale, timezone, media preferences, touch capability, and requested
emulation settings. Compare each browser with its own baseline. A Chromium
baseline and Firefox candidate are incompatible for a regression gate.

All three engines capture DOM, computed styles, geometry, screenshots, form
state, and accessible roles/names. Firefox and WebKit use Playwright ARIA
snapshots; Chromium additionally supplies its native accessibility tree and
matched CSS/source-map attribution through CDP. `state.capabilities` records
these differences. Missing native CSS attribution is disclosed on elements and
does not by itself invalidate measured layout comparisons.

Firefox uses the requested narrow viewport and DPR for mobile presets but does
not enable Playwright's unsupported `is_mobile` emulation. This does not simulate
a mobile Firefox device. These are local Playwright engines; no remote browser
farm is involved. Closed shadow-root inspection is available only through
Chromium's CDP, and closed contents remain unsupported. Frame interiors, canvas,
and video retain their existing coverage limitations.

RenderState uses artifact schema 2 for the new environment and form-state fields.
Schema 1 artifacts must be recaptured; loading an unsupported schema fails explicitly.

## CLI, pytest, and MCP

Write a JSON definition from `scenario.to_dict()`, then run:

```bash
layoutlens scenario checkout.json --browser webkit --save artifacts/checkout
layoutlens scenario checkout.json --browser firefox --output sarif
layoutlens capture checkout.html --browser firefox --color-scheme dark --save artifacts/page
```

The scenario command exits with 0 for pass, 1 for fail, and 2 for incomplete.
It accepts the same media, locale, timezone, and DPR flags as capture/diff.
`--width` and `--height` must be supplied together for a custom viewport.

The pytest fixture adds `layoutlens.assert_scenario(scenario)` and the
`--layoutlens-browser` option. The MCP server exposes `run_ui_scenario`, taking
a definition and a new artifact directory, and browser options on
`capture_render_state`. Both return structured evidence. SARIF includes explicit
expectation failures, candidate interaction findings, and execution completeness.
