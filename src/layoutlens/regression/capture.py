"""Capture a consistent rendered state using Playwright and explicit browser capabilities."""

from __future__ import annotations

import asyncio
import base64
import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import unquote_to_bytes, urljoin

from playwright.async_api import Error as PlaywrightError

from ..browser import BrowserConfig, open_page
from ..layout.geometry import LayoutScorer
from .graph import build_graph
from .models import CaptureEnvironment, Element, RenderState
from .sourcemaps import original_position

if TYPE_CHECKING:
    from playwright.async_api import Page

    from ..types import ViewportType

_SCRIPT = Path(__file__).with_suffix(".js").read_text(encoding="utf-8")


async def _attribution(
    page: Page, nodes: list[Element]
) -> tuple[list[dict], list[str]]:
    client = await page.context.new_cdp_session(page)
    gaps: list[str] = []
    headers: dict[str, dict] = {}
    client.on(
        "CSS.styleSheetAdded",
        lambda event: headers.update(
            {event["header"]["styleSheetId"]: event["header"]}
        ),
    )
    try:
        await client.send("DOM.enable")
        await client.send("CSS.enable")
        await client.send("Accessibility.enable")
        document = await client.send("DOM.getDocument", {"depth": -1, "pierce": True})
        pending = [document["root"]]
        while pending:
            item = pending.pop()
            if item.get("shadowRootType") == "closed":
                gaps.append("closed shadow root contents are unsupported")
            pending.extend(item.get("children", []) + item.get("shadowRoots", []))
        tree = (await client.send("Accessibility.getFullAXTree"))["nodes"]
        ax = {node.get("backendDOMNodeId"): node for node in tree}
        for node in nodes:
            if not node.visible:
                continue
            expression = (
                """(selector => {
              let root = document, el;
              const parts = selector.split(' >>> ');
              for (let i = 0; i < parts.length; i++) {
                el = root.querySelector(parts[i]);
                if (!el) return null;
                if (i < parts.length - 1) root = el.shadowRoot;
              }
              return el;
            })("""
                + json.dumps(node.selector)
                + ")"
            )
            remote = await client.send(
                "Runtime.evaluate",
                {"expression": expression, "objectGroup": "layoutlens"},
            )
            object_id = remote["result"].get("objectId")
            if not object_id:
                node.attribution_gaps.append("element disappeared during CSS capture")
                gaps.append(f"element disappeared: {node.selector}")
                continue
            try:
                described = (
                    await client.send("DOM.describeNode", {"objectId": object_id})
                )["node"]
                identity = (
                    await client.send("DOM.requestNode", {"objectId": object_id})
                )["nodeId"]
                accessibility = ax.get(described["backendNodeId"], {})
                node.role = accessibility.get("role", {}).get("value", "")
                node.name = accessibility.get("name", {}).get("value", "")
                matched = await client.send(
                    "CSS.getMatchedStylesForNode", {"nodeId": identity}
                )
                for origin, groups in [
                    ("matched", matched.get("matchedCSSRules", [])),
                    *[
                        ("inherited", ancestor.get("matchedCSSRules", []))
                        for ancestor in matched.get("inherited", [])
                    ],
                ]:
                    for group in groups:
                        rule = group["rule"]
                        style = rule["style"]
                        header = headers.get(style.get("styleSheetId", ""), {})
                        for prop in style.get("cssProperties", []):
                            if (
                                prop.get("disabled")
                                or prop.get("parsedOk") is False
                                or not prop.get("range")
                            ):
                                continue
                            node.declarations.append(
                                {
                                    "property": prop["name"],
                                    "value": prop["value"],
                                    "important": prop.get("important", False),
                                    "selector": rule["selectorList"]["text"],
                                    "origin": origin,
                                    "url": header.get("sourceURL", ""),
                                    "source_map_url": header.get("sourceMapURL"),
                                    "range": prop["range"],
                                    "stylesheet_start_line": header.get("startLine", 0),
                                    "stylesheet_start_column": header.get(
                                        "startColumn", 0
                                    ),
                                }
                            )
                for prop in matched.get("inlineStyle", {}).get("cssProperties", []):
                    if not prop.get("disabled") and prop.get("parsedOk") is not False:
                        node.declarations.append(
                            {
                                "property": prop["name"],
                                "value": prop["value"],
                                "origin": "inline",
                                "url": page.url,
                                "range": prop.get("range"),
                                "selector": node.selector,
                            }
                        )
            except PlaywrightError as error:
                node.attribution_gaps.append(str(error))
        await _map_sources(page, nodes)
        return tree, gaps
    finally:
        await client.send("Runtime.releaseObjectGroup", {"objectGroup": "layoutlens"})
        await client.detach()


async def _map_sources(page: Page, nodes: list[Element]) -> None:
    maps: dict[str, dict | None] = {}
    for node in nodes:
        for declaration in node.declarations:
            reference = declaration.get("source_map_url")
            location = declaration.get("range")
            if not reference or not location:
                continue
            map_url = urljoin(declaration["url"], reference)
            try:
                if map_url not in maps:
                    maps[map_url] = None
                    if map_url.startswith("data:"):
                        header, payload = map_url.split(",", 1)
                        raw = (
                            base64.b64decode(payload, validate=True)
                            if ";base64" in header
                            else unquote_to_bytes(payload)
                        )
                        maps[map_url] = json.loads(raw)
                    else:
                        response = await page.request.get(map_url, timeout=5000)
                        if not response.ok:
                            raise ValueError(f"source map HTTP {response.status}")
                        maps[map_url] = await response.json()
                source_map = maps[map_url]
                if source_map is None:
                    raise ValueError("source map unavailable")
                declaration["original_source"] = original_position(
                    source_map,
                    location["startLine"],
                    location["startColumn"],
                    declaration["url"] if map_url.startswith("data:") else map_url,
                )
            except (ValueError, KeyError, TypeError, PlaywrightError) as error:
                declaration["source_map_error"] = str(error)


async def _portable_accessibility(page: Page, nodes: list[Element]) -> list[dict]:
    """Read Playwright's accessible roles and names without Chromium's CDP."""
    tree = [
        {
            "format": "playwright-aria-snapshot",
            "value": await page.locator("body").aria_snapshot(),
        }
    ]
    for node in nodes:
        node.attribution_gaps.append("matched CSS declarations require Chromium CDP")
        if not node.visible:
            continue
        snapshot = await page.locator(
            node.selector.replace(" >>> ", " >> ")
        ).aria_snapshot()
        first = snapshot.splitlines()[0] if snapshot else ""
        match = re.match(r"- ([a-zA-Z][a-zA-Z0-9-]*)(.*)", first)
        if (
            match
            and match[1] != "text"
            and await page.get_by_role(cast("Any", match[1]))
            .and_(page.locator(node.selector.replace(" >>> ", " >> ")))
            .count()
        ):
            node.role = match[1]
            remainder = match[2].lstrip()
            if remainder.startswith('"'):
                node.name = json.JSONDecoder().raw_decode(remainder)[0]
    return tree


async def capture_page(
    page: Page,
    *,
    source: str | None = None,
    timeout: int = 30000,
    revision: str | None = None,
    config: BrowserConfig | None = None,
) -> RenderState:
    """Capture an already prepared page without changing its interaction state.

    Args:
        page: Playwright page, including any caller-established interaction state.
        source: Source label recorded in the artifact.
        timeout: Maximum wait for fonts and images, in milliseconds.
        revision: Optional verified source revision label for attribution.
        config: Requested emulation settings recorded alongside measured conditions.

    Returns:
        Browser measurements and screenshot with explicit completeness status.
    """
    engine = (
        page.context.browser.browser_type.name if page.context.browser else "unknown"
    )
    if config and config.browser != engine:
        raise ValueError("capture configuration does not match the page's browser")
    gaps = []
    try:
        await asyncio.wait_for(
            page.evaluate("""async () => {
            await document.fonts.ready;
            await Promise.all([...document.images].map(i => i.decode().catch(() => null)));
            await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        }"""),
            timeout / 1000,
        )
    except TimeoutError:
        gaps.append("font/image readiness timeout")
    raw = await page.evaluate(_SCRIPT)
    raw["loading"]["capture_url"] = page.url
    nodes = [Element.model_validate(node) for node in raw["nodes"]]
    scorer = LayoutScorer(probe_focus=False)
    evidence = await scorer.collect_evidence(page)
    native = engine == "chromium"
    attribution_gaps = []
    if native:
        accessibility, attribution_gaps = await _attribution(page, nodes)
    else:
        accessibility = await _portable_accessibility(page, nodes)
    screenshot = await page.screenshot(
        full_page=True, animations="allow", caret="initial"
    )
    final = await page.evaluate(_SCRIPT)
    stable = (
        raw["nodes"] == final["nodes"]
        and raw["geometry"] == final["geometry"]
        and raw["loading"]["fonts"] == final["loading"]["fonts"]
    )
    if not stable:
        gaps.append("render changed during capture")
    if any(
        not image["complete"] or not image["width"]
        for image in raw["loading"]["images"]
    ):
        gaps.append("image failed to load or decode")
    if any(font["status"] in {"loading", "error"} for font in raw["loading"]["fonts"]):
        gaps.append("font not loaded")
    if any(
        asset.get("status", 0) >= 400
        and not (
            asset.get("type") == "other"
            and asset["name"].split("?")[0].endswith("/favicon.ico")
        )
        for asset in raw["loading"]["assets"]
    ):
        gaps.append("asset request failed")
    return RenderState(
        source=source or page.url,
        environment=CaptureEnvironment(
            browser=engine,
            emulation=asdict(config) if config else {},
            browser_version=page.context.browser.version
            if page.context.browser
            else "unknown",
            **raw["environment"],
        ),
        capabilities={
            "native_accessibility_tree": native,
            "closed_shadow_detection": native,
            "accessible_roles_names": True,
            "matched_css_declarations": native,
            "css_source_maps": native,
        },
        graph=build_graph(nodes),
        geometry=raw["geometry"],
        loading=raw["loading"],
        accessibility=accessibility,
        dom=raw["dom"],
        detector_evidence=evidence,
        detector_config=vars(scorer),
        screenshot=screenshot,
        stable=stable,
        coverage_gaps=sorted(set(gaps + raw["gaps"] + attribution_gaps)),
        revision=revision,
    )


async def capture_state(
    source: str | Path,
    *,
    viewport: ViewportType | tuple[int, int] = "desktop",
    timeout: int = 30000,
    wait_for_selector: str | None = None,
    revision: str | None = None,
    browser: str = "chromium",
    color_scheme: str = "light",
    reduced_motion: str = "reduce",
    locale: str = "en-US",
    timezone_id: str = "UTC",
    device_scale_factor: float | None = None,
) -> RenderState:
    """Capture a URL or HTML source as a portable render state.

    Args:
        source: URL or local HTML file; screenshot-only inputs are unsupported.
        viewport: Named browser viewport or (width, height) in CSS pixels.
        timeout: Navigation and readiness timeout in milliseconds.
        wait_for_selector: Optional application readiness selector.
        revision: Optional source revision recorded for later attribution.
        browser: Local Playwright engine: chromium, firefox, or webkit.
        color_scheme: Emulated light, dark, or no-preference color scheme.
        reduced_motion: Emulated reduce or no-preference motion preference.
        locale: Browser locale.
        timezone_id: Browser timezone.
        device_scale_factor: Optional DPR override for the viewport.

    Returns:
        A versioned render state; use its save method to establish a baseline.
    """
    if Path(str(source)).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        raise ValueError(
            "structured comparison requires a URL, HTML file, or RenderState"
        )
    config = BrowserConfig(
        browser=browser,
        color_scheme=color_scheme,
        reduced_motion=reduced_motion,
        locale=locale,
        timezone_id=timezone_id,
        device_scale_factor=device_scale_factor,
    )
    # preen: allow-dropped-arg -- engine is in config; browser accepts a shared instance.
    async with open_page(
        source, viewport=viewport, timeout=timeout, config=config
    ) as page:
        if wait_for_selector:
            await page.wait_for_selector(wait_for_selector, timeout=timeout)
        return await capture_page(
            page, source=str(source), timeout=timeout, revision=revision, config=config
        )
