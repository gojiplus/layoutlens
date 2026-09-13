"""Stateful browser contracts, interrupted runs, and portable evidence."""

import json
from pathlib import Path

import pytest
import pytest_asyncio
from playwright.async_api import async_playwright

from layoutlens import (
    BrowserConfig,
    LayoutLens,
    Scenario,
    ScenarioReport,
    capture_page,
    capture_state,
    diff,
)
from layoutlens.browser import open_page
from layoutlens.sarif import scenario_to_sarif
from layoutlens.scenarios.models import Step

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<link rel="icon" href="data:,"><title>Checkout</title>
<style>
body{margin:20px;font-family:Arial} input:focus-visible{outline:3px solid blue}
#help{display:none} #trigger:hover+#help{display:block}
#nav{display:block}@media(max-width:500px){#nav{display:none}}
.overlay{position:fixed;inset:0;background:white;z-index:100}
</style></head><body>
<label for="email">Email</label><input id="email">
<button id="continue" onclick="sessionStorage.setItem('email',document.querySelector('#email').value);location.href='payment.html'">Continue</button>
<button id="trigger">Help</button><span id="help">Help text</span>
<nav id="nav">Navigation</nav>
<button id="show" onclick="document.querySelector('#dialog').showModal()">Open</button>
<dialog id="dialog"><button id="close" onclick="document.querySelector('#dialog').close()">Close</button></dialog>
</body></html>"""


@pytest_asyncio.fixture(autouse=True)
async def installed_browser(request):
    if request.node.get_closest_marker("browser"):
        engine = getattr(request.node, "callspec", None)
        name = engine.params.get("engine", "chromium") if engine else "chromium"
        async with async_playwright() as playwright:
            if not Path(getattr(playwright, name).executable_path).exists():
                pytest.skip(f"Playwright {name} is not installed")


@pytest.fixture
def checkout(tmp_path):
    source = tmp_path / "checkout.html"
    source.write_text(PAGE)
    (tmp_path / "payment.html").write_text(
        """<!doctype html><html lang="en"><head><link rel="icon" href="data:,"><title>Payment</title></head><body><h1 id="payment">Payment</h1><p id="saved"></p><script>document.querySelector('#saved').textContent=sessionStorage.getItem('email')</script></body></html>"""
    )
    return source


@pytest.mark.parametrize(
    "bad",
    [
        {"action": "resize", "value": [0, 600]},
        {"action": "pointer_down", "value": "extra"},
        {"action": "expect_tab_reaches", "target": "email", "value": 0},
        {"action": "click"},
        {"action": "type", "value": 42},
        {"action": "checkpoint", "target": "x", "value": "ignored"},
        {"action": "evaluate", "value": "alert(1)"},
    ],
)
def test_definitions_reject_invalid_steps_before_execution(bad):
    with pytest.raises(ValueError, match="validation error"):
        Scenario.from_dict({"source": "/checkout", "steps": [bad]})


def test_builder_reuse_and_checkpoint_names():
    original = Scenario("/checkout", base_url="https://example.test")
    sequence = original.tab().expect_focus("email").checkpoint("payment")
    assert not original.steps
    assert sequence.source == "https://example.test/checkout"
    assert Scenario.from_dict(sequence.to_dict()).to_dict() == sequence.to_dict()
    with pytest.raises(ValueError, match="unique"):
        sequence.checkpoint("payment")
    with pytest.raises(ValueError, match="reserved"):
        sequence.checkpoint("__failure_0")
    with pytest.raises(ValueError, match="finite"):
        Step(action="pointer_move", value=[float("nan"), 0])


@pytest.mark.browser
@pytest.mark.asyncio
@pytest.mark.parametrize("engine", ["chromium", "firefox", "webkit"])
async def test_checkout_sequence_and_persistence(checkout, tmp_path, engine):
    scenario = (
        Scenario(checkout)
        .tab()
        .expect_focus("email")
        .expect_style("email", "outline-width", "3px")
        .type("me@example.com")
        .checkpoint("email")
        .click("Continue")
        .expect_url("/payment.html")
        .expect_text("saved", "me@example.com")
        .checkpoint("payment")
    )
    report = await scenario.run(browser=engine, timeout=10000, viewport=(800, 600))
    assert report.gate_status == "pass", report.to_json()
    assert list(report.checkpoints) == ["email", "payment"]
    state = report.checkpoints["email"]
    email = next(node for node in state.graph.nodes if node.selector == "#email")
    assert email.control_state["value"] == "me@example.com"
    assert email.focused
    assert email.role == "textbox"
    assert email.name == "Email"
    assert any(event.kind == "focusin" for event in report.events)
    assert any(event.kind == "input" for event in report.events)
    assert any(
        event.kind == "navigation" and "payment.html" in event.url
        for event in report.events
    )
    assert "me@example.com" not in json.dumps(
        [event.model_dump() for event in report.events]
    )
    assert [event.sequence for event in report.events] == list(
        range(len(report.events))
    )
    manifest = report.save(tmp_path / f"run-{engine}")
    loaded = ScenarioReport.load(manifest)
    assert loaded.checkpoints["email"].fingerprint == state.fingerprint
    assert loaded.gate_status == "pass"
    assert loaded.diff(report).gate_status == "pass"
    assert loaded.diff(report).checkpoints["email"].deltas == []
    with pytest.raises(FileExistsError):
        report.save(manifest.parent)
    data = json.loads(manifest.read_text())
    data["checkpoints"]["email"]["directory"] = "../escape"
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="escapes"):
        ScenarioReport.load(manifest)


@pytest.mark.browser
@pytest.mark.asyncio
@pytest.mark.parametrize("engine", ["chromium", "firefox", "webkit"])
async def test_media_identity_and_capture_preserve_state(checkout, engine):
    config = BrowserConfig(engine, "dark", "no-preference", "fr-FR", "Europe/Paris", 2)
    async with open_page(checkout, (800, 600), config=config) as page:
        await page.locator("#email").focus()
        original = await page.locator("#email").evaluate("el => el.outerHTML")
        first = await capture_page(page, config=config)
        second = await capture_page(page, config=config)
        assert first.stable
        assert not first.coverage_gaps
        assert first.environment.browser == engine
        assert first.environment.viewport == (800, 600)
        assert first.environment.color_scheme == "dark"
        assert first.environment.reduced_motion == "no-preference"
        assert first.environment.locale == "fr-FR"
        assert first.environment.timezone == "Europe/Paris"
        assert first.environment.dpr == 2
        assert await page.locator("#email").evaluate("el => el.outerHTML") == original
        assert await page.locator("#email").evaluate(
            "el => el === document.activeElement"
        )
        assert not await page.locator("style[data-layoutlens-capture]").count()
        assert first.capabilities["matched_css_declarations"] == (engine == "chromium")
        assert diff(first, second).gate_status == "pass"
        second.environment.locale = "en-US"
        assert diff(first, second).gate_status == "incomplete"


@pytest.mark.browser
@pytest.mark.asyncio
async def test_explicit_failure_and_blocked_action_are_distinct(checkout):
    failure = (
        await Scenario(checkout)
        .tab()
        .expect_focus("continue")
        .checkpoint("after")
        .run(timeout=500)
    )
    assert failure.gate_status == "fail"
    assert failure.steps[1].status == "fail"
    assert not failure.incomplete_reasons
    source = checkout.parent / "blocked.html"
    source.write_text(PAGE.replace("</body>", '<div class="overlay"></div></body>'))
    blocked = (
        await Scenario(source)
        .click("continue")
        .checkpoint("unreached")
        .run(timeout=1000)
    )
    assert blocked.gate_status == "incomplete"
    assert blocked.steps[0].status == "error"
    assert "unreached" not in blocked.checkpoints
    assert "__failure_0" in blocked.checkpoints
    assert any(f.defect_class == "target-obscured" for f in blocked.findings)
    sarif = scenario_to_sarif(blocked)
    assert sarif["runs"][0]["properties"]["incomplete"]
    assert not sarif["runs"][0]["invocations"][0]["executionSuccessful"]
    assert blocked.diff(failure).gate_status == "incomplete"


@pytest.mark.browser
@pytest.mark.asyncio
async def test_bounded_keyboard_trap_and_obscured_focus(checkout):
    source = checkout.parent / "trap.html"
    source.write_text(
        PAGE.replace(
            "</body>",
            """<div class="overlay"></div><script>
    document.addEventListener('keydown', e=>{if(e.key==='Tab')e.preventDefault()});
    document.querySelector('#email').focus();</script></body>""",
        )
    )
    report = (
        await Scenario(source)
        .tab()
        .expect_tab_reaches("continue", max_tabs=3)
        .checkpoint("trapped")
        .run(timeout=5000)
    )
    assert report.gate_status == "fail"
    classes = {f.defect_class for f in report.findings}
    assert {"focus-did-not-advance", "focus-obscured"} <= classes
    assert "within 3 Tab presses" in report.steps[1].error
    assert len(report.steps[1].evidence["visited"]) == 3
    assert report.checkpoints["trapped"].graph.nodes
    warning = await Scenario(source).tab().checkpoint("trapped").run(timeout=5000)
    assert warning.gate_status == "pass"
    strict = (
        await Scenario(source)
        .tab()
        .checkpoint("trapped")
        .run(timeout=5000, policy="findings")
    )
    assert strict.gate_status == "fail"


@pytest.mark.browser
@pytest.mark.asyncio
async def test_hover_dialog_dismissal_and_responsive_transition(checkout):
    report = await (
        Scenario(checkout)
        .hover("Help")
        .expect_visible("help")
        .pointer_move(790, 590)
        .expect_hidden("help")
        .click("Open")
        .expect_visible("dialog")
        .press("Escape")
        .expect_hidden("dialog")
        .resize(400, 600)
        .expect_style("nav", "display", "none")
        .checkpoint("mobile")
        .run(viewport=(800, 600), timeout=5000)
    )
    assert report.gate_status == "pass", report.to_json()
    assert report.checkpoints["mobile"].environment.viewport == (400, 600)


@pytest.mark.browser
@pytest.mark.asyncio
async def test_stacked_modals_are_candidates_and_count_is_an_explicit_contract(
    tmp_path,
):
    source = tmp_path / "stacked.html"
    source.write_text(
        """<html lang="en"><head><link rel="icon" href="data:,"></head><body><div role="dialog" aria-modal="true">First</div><div role="dialog" aria-modal="true">Second</div></body></html>"""
    )
    report = (
        await Scenario(source)
        .expect_count('css=[role="dialog"]:visible', 1)
        .checkpoint("dialogs")
        .run(timeout=500)
    )
    assert report.gate_status == "fail"
    assert all(f.level == "candidate" for f in report.findings)
    assert report.findings[0].defect_class == "stacked-modals"


@pytest.mark.browser
@pytest.mark.asyncio
async def test_pointer_drag_records_events_and_expectation(tmp_path):
    source = tmp_path / "drag.html"
    source.write_text(
        """<html lang="en"><head><link rel="icon" href="data:,"></head><body><div id="drag" draggable="true" style="width:80px;height:40px">Drag</div><div id="drop" style="width:120px;height:70px" ondragover="event.preventDefault()" ondrop="this.textContent='Dropped'">Drop</div></body></html>"""
    )
    report = (
        await Scenario(source)
        .drag("drag", "drop")
        .expect_text("drop", "Dropped")
        .checkpoint("drop")
        .run(timeout=5000)
    )
    assert report.gate_status == "pass", report.to_json()
    assert any(event.kind == "pointerdown" for event in report.events)


@pytest.mark.browser
@pytest.mark.asyncio
async def test_lens_browser_configuration_reaches_existing_scanners(checkout, tmp_path):
    lens = LayoutLens(
        browser="firefox", color_scheme="dark", output_dir=str(tmp_path / "out")
    )
    report = await lens.run_scenario(Scenario(checkout).checkpoint("page"))
    assert report.checkpoints["page"].environment.browser == "firefox"
    assert report.checkpoints["page"].environment.color_scheme == "dark"
    before = await capture_state(checkout, browser="chromium")
    assert diff(before, report.checkpoints["page"]).gate_status == "incomplete"
    async with async_playwright() as p:
        browser = await p.firefox.launch()
        try:
            with pytest.raises(ValueError, match="does not match"):
                async with open_page(checkout, browser=browser, config=BrowserConfig()):
                    pass
        finally:
            await browser.close()


def test_corrupt_receipts_and_changed_inputs_cannot_pass(render_state):
    from layoutlens.scenarios.models import StepResult

    baseline = ScenarioReport(
        source="fixture.html",
        definition_fingerprint="0" * 64,
        planned_steps=1,
        steps=[StepResult(index=0, action="checkpoint", target="ready")],
        checkpoints={"ready": render_state},
    )
    assert baseline.gate_status == "pass"
    corrupt = baseline.model_copy(deep=True)
    corrupt.steps[0].index = 1
    assert corrupt.gate_status == "incomplete"
    corrupt = baseline.model_copy(deep=True)
    corrupt.checkpoints.clear()
    assert corrupt.gate_status == "incomplete"
    changed = baseline.model_copy(deep=True)
    changed.definition_fingerprint = "1" * 64
    assert baseline.diff(changed).gate_status == "incomplete"


@pytest.mark.browser
@pytest.mark.asyncio
async def test_pointer_receipts_native_dialog_and_noneditable_type(tmp_path):
    page = tmp_path / "pointer.html"
    page.write_text("""<!doctype html><html><head><title>Pointer</title></head><body>
    <button id="button" style="position:fixed;left:20px;top:20px;width:100px;height:40px"
      onclick="this.textContent='Clicked'">Click</button>
    <input type="checkbox" id="box"><button id="alert" style="display:block;margin-top:100px" onclick="window.alert('unexpected')">Alert</button>
    </body></html>""")
    report = await (
        Scenario(page)
        .pointer_move(50, 40)
        .pointer_down()
        .pointer_up()
        .expect_text("button", "Clicked")
        .checkpoint("clicked")
        .run()
    )
    assert report.gate_status == "pass", report.to_json()
    moved = next(event for event in report.events if event.kind == "pointermove")
    assert (moved.detail["x"], moved.detail["y"]) == (50, 40)
    report = await Scenario(page).click("box").type("not editable").run(timeout=1000)
    assert report.gate_status == "incomplete"
    assert "editable focused element" in report.steps[1].error
    report = await Scenario(page).click("alert").checkpoint("dismissed").run()
    assert report.gate_status == "incomplete"
    assert any(event.kind == "browser-dialog" for event in report.events)


@pytest.mark.browser
@pytest.mark.asyncio
async def test_shared_context_closes_on_caller_exception(checkout):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:

            async def fail_inside_context():
                async with open_page(checkout, browser=browser):
                    assert len(browser.contexts) == 1
                    raise RuntimeError("caller failed")

            with pytest.raises(RuntimeError, match="caller failed"):
                await fail_inside_context()
            assert not browser.contexts
        finally:
            await browser.close()


@pytest.mark.browser
@pytest.mark.asyncio
@pytest.mark.parametrize("engine", ["firefox"])
async def test_cli_exit_codes_and_artifact_browser(checkout, tmp_path, capsys, engine):
    from layoutlens.cli import _regression_main

    definition = tmp_path / "checkout.json"
    definition.write_text(
        json.dumps(
            Scenario(checkout).tab().expect_focus("email").checkpoint("ready").to_dict()
        )
    )
    target = tmp_path / "cli-run"
    code = await _regression_main(
        [
            "scenario",
            str(definition),
            "--browser",
            engine,
            "--save",
            str(target),
            "--output",
            "sarif",
        ]
    )
    assert code == 0
    sarif = json.loads(capsys.readouterr().out)
    assert sarif["runs"][0]["properties"]["gate_status"] == "pass"
    assert (
        ScenarioReport.load(target).checkpoints["ready"].environment.browser == engine
    )
    definition.write_text(
        json.dumps(Scenario(checkout).expect_visible("#missing").to_dict())
    )
    assert (
        await _regression_main(["scenario", str(definition), "--timeout", "250"]) == 1
    )
    capsys.readouterr()
    definition.write_text(json.dumps(Scenario(checkout).click("#missing").to_dict()))
    assert (
        await _regression_main(["scenario", str(definition), "--timeout", "250"]) == 2
    )
    capsys.readouterr()


@pytest.mark.browser
@pytest.mark.asyncio
@pytest.mark.parametrize("engine", ["webkit"])
async def test_mcp_scenario_browser_options(checkout, tmp_path, engine):
    fastmcp = pytest.importorskip("fastmcp")
    from layoutlens.mcp_server import mcp

    async with fastmcp.Client(mcp) as client:
        result = await client.call_tool(
            "run_ui_scenario",
            {
                "definition": Scenario(checkout)
                .tab()
                .expect_focus("email")
                .checkpoint("ready")
                .to_dict(),
                "directory": str(tmp_path / "mcp-run"),
                "browser": engine,
                "color_scheme": "dark",
                "locale": "fr-FR",
                "timezone_id": "Europe/Paris",
            },
        )
    assert not result.is_error
    saved = ScenarioReport.load(tmp_path / "mcp-run")
    assert saved.gate_status == "pass"
    assert saved.checkpoints["ready"].environment.browser == engine
    assert saved.checkpoints["ready"].environment.color_scheme == "dark"
    assert saved.checkpoints["ready"].environment.timezone == "Europe/Paris"


@pytest.mark.browser
@pytest.mark.asyncio
@pytest.mark.parametrize("engine", ["chromium", "firefox", "webkit"])
async def test_shadow_focus_receipts_match_checkpoint_selectors(tmp_path, engine):
    source = tmp_path / "shadow.html"
    source.write_text("""<!doctype html><html><head><title>Shadow</title></head><body>
    <div id="first"></div><div id="second"></div><script>
    for (const id of ['first','second']) {
      document.getElementById(id).attachShadow({mode:'open'}).innerHTML =
        '<label for="shared">Email</label><input id="shared">';
    }
    </script></body></html>""")
    report = await (
        Scenario(source)
        .click("css=#second >> #shared")
        .expect_focus("css=#second >> #shared")
        .type("hello")
        .checkpoint("focused")
        .run(browser=engine)
    )
    assert report.gate_status == "pass", report.to_json()
    selector = report.steps[0].after["focus"]["selector"]
    assert selector == "#second >>> #shared"
    node = next(
        node
        for node in report.checkpoints["focused"].graph.nodes
        if node.selector == selector
    )
    assert node.focused
    assert node.control_state["value"] == "hello"
    assert node.role == "textbox"
    assert node.name == "Email"
