"""Execute declared interactions in one browser context and retain measured receipts."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin, urlsplit

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeout
from playwright.async_api import expect

from ..browser import open_page
from ..regression.capture import capture_page
from .models import Event, InteractionFinding, ScenarioReport, StepResult

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page

    from ..browser import BrowserConfig
    from ..regression.policy import GatePolicy
    from ..types import ViewportType
    from .models import Step

_OBSERVE = Path(__file__).with_name("observe.js").read_text(encoding="utf-8")
_RECORDER = Path(__file__).with_name("record.js").read_text(encoding="utf-8")


async def _locate(page: Page, target: str | None) -> Locator:
    if not target:
        raise ValueError("an element target is required")
    if target.startswith(("css=", "text=", "xpath=", "#", ".", "[")):
        return page.locator(target.replace(" >>> ", " >> "))
    by_id = page.locator(f"[id={json.dumps(target)}]")
    if await by_id.count():
        return by_id
    by_label = page.get_by_label(target, exact=True)
    if await by_label.count():
        return by_label
    by_test_id = page.get_by_test_id(target)
    if await by_test_id.count():
        return by_test_id
    return page.get_by_text(target, exact=True)


def _diagnose(report: ScenarioReport, result: StepResult) -> None:
    focus = result.after.get("focus")
    if focus:
        before_style = result.before.get("focus_styles", {}).get(focus["selector"])
        if before_style is not None:
            result.evidence["focus_appearance"] = {
                "before": before_style,
                "after": focus["styles"],
                "changed_properties": {
                    k: {"before": v, "after": focus["styles"].get(k)}
                    for k, v in before_style.items()
                    if v != focus["styles"].get(k)
                },
            }
    target = result.before.get("target")
    if (
        result.action in {"click", "expect_clickable"}
        and result.status != "pass"
        and target
        and not target["exposed_samples"]
    ):
        report.findings.append(
            InteractionFinding(
                step=result.index,
                defect_class="target-obscured",
                element=target["selector"],
                evidence=target,
                exceptions=["hit testing samples nine points"],
            )
        )
    if focus and focus["tag"] not in {"body", "html"} and not focus["exposed_samples"]:
        report.findings.append(
            InteractionFinding(
                step=result.index,
                defect_class="focus-obscured",
                element=focus["selector"],
                evidence=focus,
                exceptions=["sampled hit testing does not measure every pixel"],
            )
        )
    dialogs = result.after.get("dialogs", [])
    if len(dialogs) > 1:
        report.findings.append(
            InteractionFinding(
                step=result.index,
                defect_class="stacked-modals",
                element=dialogs[-1]["selector"],
                evidence={"visible_modals": dialogs},
                exceptions=["intentional nested modal workflow"],
            )
        )
    previous = result.before.get("focus")
    if (
        result.action == "tab"
        and focus
        and previous
        and focus["selector"] == previous["selector"]
    ):
        report.findings.append(
            InteractionFinding(
                step=result.index,
                defect_class="focus-did-not-advance",
                element=focus["selector"],
                evidence={"before": previous, "after": focus},
                exceptions=[
                    "intentional modal focus containment",
                    "single available target",
                ],
            )
        )


class _ExpectationError(AssertionError):
    def __init__(self, message: str, evidence: dict[str, Any]) -> None:
        super().__init__(message)
        self.evidence = evidence


async def _expectation(page: Page, step: Step, timeout: int) -> dict[str, Any]:
    if step.action == "expect_url":
        expected = str(step.value)
        await page.wait_for_url(
            lambda url: (
                str(url) == expected
                if urlsplit(expected).scheme
                else urlsplit(str(url)).path
                + ("?" + urlsplit(str(url)).query if urlsplit(str(url)).query else "")
                == expected
            ),
            timeout=timeout,
        )
        return {"expected": expected, "actual": page.url}
    locator = await _locate(page, step.target)
    match step.action:
        case "expect_focus":
            await expect(locator).to_be_focused(timeout=timeout)
        case "expect_visible":
            await expect(locator).to_be_visible(timeout=timeout)
        case "expect_hidden":
            await expect(locator).to_be_hidden(timeout=timeout)
        case "expect_text":
            await expect(locator).to_have_text(step.value, timeout=timeout)
        case "expect_count":
            await expect(locator).to_have_count(step.value, timeout=timeout)
        case "expect_style":
            await expect(locator).to_have_css(
                step.value["property"], step.value["value"], timeout=timeout
            )
        case "expect_clickable":
            await locator.click(trial=True, timeout=timeout)
        case "expect_tab_reaches":
            visited = []
            for _ in range(step.value):
                await page.keyboard.press("Tab")
                observed = await page.evaluate(_OBSERVE)
                visited.append(observed["focus"])
                if await locator.count() == 1 and await locator.evaluate(
                    "el => el === el.getRootNode().activeElement"
                ):
                    return {"visited": visited, "max_tabs": step.value}
            raise _ExpectationError(
                f"target not reached within {step.value} Tab presses",
                {"visited": visited, "max_tabs": step.value},
            )
        case _:
            raise ValueError(f"unsupported expectation: {step.action}")
    return {"expected": step.value} if step.value is not None else {}


async def _act(page: Page, step: Step) -> None:
    match step.action:
        case "tab":
            await page.keyboard.press("Shift+Tab" if step.value else "Tab")
        case "press":
            await page.keyboard.press(step.value)
        case "type":
            focus = (await page.evaluate(_OBSERVE))["focus"]
            if not focus or not focus["editable"]:
                raise ValueError("type requires an editable focused element")
            await page.keyboard.type(step.value)
        case "fill":
            await (await _locate(page, step.target)).fill(step.value)
        case "click":
            await (await _locate(page, step.target)).click()
        case "hover":
            await (await _locate(page, step.target)).hover()
        case "drag":
            await (await _locate(page, step.target)).drag_to(
                await _locate(page, step.value)
            )
        case "navigate":
            await page.goto(
                urljoin(page.url, step.value), wait_until="domcontentloaded"
            )
        case "resize":
            await page.set_viewport_size(
                {"width": step.value[0], "height": step.value[1]}
            )
        case "pointer_move":
            await page.mouse.move(*step.value)
        case "pointer_down":
            await page.mouse.down(button=step.value)
        case "pointer_up":
            await page.mouse.up(button=step.value)
        case _:
            raise ValueError(f"unsupported action: {step.action}")


async def run_scenario(
    source: str,
    steps: tuple[Step, ...],
    *,
    config: BrowserConfig,
    viewport: ViewportType | tuple[int, int],
    timeout: int,
    policy: GatePolicy,
) -> ScenarioReport:
    """Run one sequence; action failures stop execution and cannot produce a pass."""
    report = ScenarioReport(
        source=source,
        planned_steps=len(steps),
        policy=policy,
        definition_fingerprint=hashlib.sha256(
            json.dumps(
                [step.model_dump(mode="json") for step in steps],
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest(),
    )
    started = time.monotonic()
    current = -1

    def record(_source: dict, event: dict) -> None:
        if len(report.events) >= 10000:
            if "event retention limit reached" not in report.incomplete_reasons:
                report.incomplete_reasons.append("event retention limit reached")
            return
        report.events.append(
            Event(
                sequence=len(report.events),
                step=current,
                time_ms=(time.monotonic() - started) * 1000,
                kind=event["kind"],
                url=event["url"],
                detail=event.get("detail", {}),
            )
        )

    try:
        async with open_page(source, viewport, timeout, config=config) as page:

            async def dismiss_dialog(dialog):
                record(
                    {},
                    {
                        "kind": "browser-dialog",
                        "url": page.url,
                        "detail": {
                            "type": dialog.type,
                            "message": dialog.message,
                            "action": "dismissed",
                        },
                    },
                )
                report.incomplete_reasons.append("unexpected browser dialog dismissed")
                await dialog.dismiss()

            page.on("dialog", dismiss_dialog)
            page.on(
                "popup",
                lambda _popup: report.incomplete_reasons.append(
                    "new window opened; scenario follows the original page"
                ),
            )
            await page.context.expose_binding("__layoutlensEvent", record)
            await page.context.add_init_script(_RECORDER)
            await page.evaluate(_RECORDER)
            page.on(
                "pageerror",
                lambda error: record(
                    {},
                    {
                        "kind": "pageerror",
                        "url": page.url,
                        "detail": {"message": str(error)},
                    },
                ),
            )
            page.on(
                "framenavigated",
                lambda frame: record(
                    {},
                    {
                        "kind": "navigation",
                        "url": frame.url,
                        "detail": {"main_frame": frame == page.main_frame},
                    },
                ),
            )
            for current, step in enumerate(steps):
                result = StepResult(
                    index=current, action=step.action, target=step.target
                )
                report.steps.append(result)
                try:
                    result.before = await page.evaluate(_OBSERVE)
                    if step.target and step.action != "checkpoint":
                        target = await _locate(page, step.target)
                        if await target.count() == 1:
                            result.before = await target.evaluate(
                                "el => (" + _OBSERVE + ")(el)"
                            )
                    if step.action == "checkpoint":
                        state = await capture_page(
                            page, source=page.url, timeout=timeout, config=config
                        )
                        report.checkpoints[str(step.target)] = state
                        result.evidence = {
                            "checkpoint": step.target,
                            "fingerprint": state.fingerprint,
                        }
                        report.incomplete_reasons.extend(
                            f"checkpoint {step.target}: {gap}"
                            for gap in state.coverage_gaps
                        )
                        if not state.stable:
                            report.incomplete_reasons.append(
                                f"checkpoint {step.target}: unstable capture"
                            )
                    elif step.action.startswith("expect_"):
                        try:
                            result.evidence = await _expectation(page, step, timeout)
                        except (AssertionError, PlaywrightTimeout) as error:
                            result.status = "fail"
                            result.error = str(error)
                            if isinstance(error, _ExpectationError):
                                result.evidence = error.evidence
                    else:
                        await _act(page, step)
                    await page.evaluate("() => window.__layoutlensFlush?.()")
                    result.after = await page.evaluate(_OBSERVE)
                    _diagnose(report, result)
                except (PlaywrightError, ValueError, OSError) as error:
                    result.status = "error"
                    result.error = str(error)
                    report.incomplete_reasons.append(
                        f"step {current} ({step.action}): {error}"
                    )
                    try:
                        result.after = await page.evaluate(_OBSERVE)
                        _diagnose(report, result)
                        report.checkpoints[f"__failure_{current}"] = await capture_page(
                            page, timeout=timeout, config=config
                        )
                    except (PlaywrightError, ValueError, OSError):
                        report.incomplete_reasons.append(
                            "failure checkpoint unavailable"
                        )
                    break
    except (PlaywrightError, ValueError, OSError) as error:
        report.incomplete_reasons.append(str(error))
    return report
