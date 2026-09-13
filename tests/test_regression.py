"""Browser evidence, conservative correspondence, and offline gate contracts."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from io import BytesIO

import pytest
from PIL import Image
from playwright.async_api import async_playwright

from layoutlens import (
    LayoutLens,
    Qualification,
    RenderState,
    Verification,
    capture_page,
    capture_state,
    diff,
)
from layoutlens.layout import LayoutScorer
from layoutlens.regression.graph import build_graph, match_elements
from layoutlens.regression.models import CaptureEnvironment, Element
from layoutlens.regression.sourcemaps import original_position
from layoutlens.sarif import diff_to_sarif


def state(*nodes, evidence=None):
    empty = {
        key: []
        for key in (
            "contrast",
            "overlaps",
            "clipping",
            "protrusion",
            "page_overflow",
            "truncation",
            "small_targets",
            "text_occlusion",
            "focus_obscured",
        )
    }
    image = BytesIO()
    Image.new("RGB", (100, 100), "white").save(image, format="PNG")
    return RenderState(
        source="fixture.html",
        environment=CaptureEnvironment(
            browser_version="test",
            viewport=(100, 100),
            dpr=1,
            user_agent="test",
            platform="test",
            locale="en-US",
            timezone="UTC",
        ),
        graph=build_graph(list(nodes)),
        detector_evidence=empty | (evidence or {}),
        detector_config=vars(LayoutScorer(probe_focus=False)),
        screenshot=image.getvalue(),
        dom="<html></html>",
    )


def element(
    key="cta", *, width=142, text="Checkout", parent=None, identity=True, **kwargs
):
    return Element(
        key=key,
        selector="#" + key,
        tag="button",
        parent=parent,
        bbox=(10, 10, width, 40),
        text=text,
        attributes={"id": key} if identity else {},
        styles={"width": str(width), "color": "black"},
        **kwargs,
    )


def clipping(width=103, scroll=142):
    return {
        "clipping": [
            {
                "selector": "#cta",
                "bbox": [10, 10, width, 40],
                "clippedY": False,
                "scrollHeight": 40,
                "clientHeight": 40,
                "scrollWidth": scroll,
                "clientWidth": width,
            }
        ]
    }


def test_offline_artifact_roundtrip_and_integrity(tmp_path):
    original = state(element())
    manifest = original.save(tmp_path / "baseline")
    restored = RenderState.load(manifest)
    assert restored == original
    assert restored.fingerprint == original.fingerprint
    assert diff(original, restored).deltas == []
    assert diff(original, restored).gate_status == "pass"
    with pytest.raises(FileExistsError):
        original.save(manifest.parent)
    (manifest.parent / "screenshot.png").write_bytes(b"bad")
    with pytest.raises(ValueError, match="checksum"):
        RenderState.load(manifest)


def test_schema_and_reference_validation(tmp_path):
    original = state(element())
    manifest = original.save(tmp_path / "baseline")
    payload = json.loads(manifest.read_text())
    payload["schema_version"] = 9
    manifest.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="schema"):
        RenderState.load(manifest)
    with pytest.raises(ValueError, match="duplicate"):
        state(element(), element())


def test_numeric_delta_and_candidate_policy():
    before = state(element())
    after = state(element(width=103), evidence=clipping())
    report = diff(before, after)
    observation = next(d for d in report.deltas if "width" in d.changed_properties)
    assert observation.measured_delta["width"] == -39
    finding = next(d for d in report.deltas if d.defect_class == "clipping")
    assert finding.status == "introduced"
    assert finding.measured_delta["after"]["clipped_px"] == 39
    assert finding.level == "candidate"
    assert report.gate_status == "pass"
    assert diff(before, after, policy="findings").gate_status == "fail"
    assert diff(after, before, policy="findings").gate_status == "pass"
    assert (
        next(d for d in diff(after, before).deltas if d.defect_class).status
        == "resolved"
    )
    assert (
        next(d for d in diff(after, after).deltas if d.defect_class).status
        == "unchanged"
    )
    worse = state(element(width=90), evidence=clipping(90))
    assert (
        next(d for d in diff(after, worse).deltas if d.defect_class).status
        == "worsened"
    )
    sarif = diff_to_sarif(report)
    assert sarif["runs"][0]["results"][0]["level"] == "warning"
    assert sarif["runs"][0]["results"][0]["baselineState"] == "new"


def test_incomplete_is_never_pass_or_blocking():
    before, after = state(element()), state(element(width=103), evidence=clipping())
    after.environment.dpr = 2
    report = diff(before, after, policy="findings")
    assert report.gate_status == "incomplete"
    assert "capture environments differ" in report.incomplete_reasons
    assert all(not d.gateability.get("blocks") for d in report.deltas)
    after.environment.dpr = 1
    after.coverage_gaps = ["closed shadow root"]
    assert diff(before, after).gate_status == "incomplete"


def test_correspondence_reordering_and_ambiguous_repetition():
    before = build_graph([element("a"), element("b")])
    after = build_graph([element("b"), element("a", width=103)])
    matches, left, right = match_elements(before, after)
    assert {(m.before, m.after) for m in matches} == {("a", "a"), ("b", "b")}
    assert not left
    assert not right
    repeated = [element("a", identity=False), element("b", identity=False)]
    matches, left, right = match_elements(
        build_graph(repeated),
        build_graph(
            [
                element("a", identity=False, width=140),
                element("b", identity=False, width=140),
            ]
        ),
    )
    assert not matches
    assert left == right == {"a", "b"}
    assert diff(state(*repeated), state(*repeated)).gate_status == "pass"
    assert (
        diff(
            state(*repeated),
            state(
                element("a", identity=False, width=140),
                element("b", identity=False, width=140),
            ),
        ).gate_status
        == "incomplete"
    )


def test_small_movement_retained_without_geometric_significance():
    report = diff(state(element()), state(element(width=141.5)))
    assert report.deltas[0].measured_delta["width"] == -0.5
    assert report.deltas[0].evidence["geometrically_significant"] is False
    with pytest.raises(ValueError, match="tolerance_px"):
        diff(state(), state(), tolerance_px=float("nan"))
    with pytest.raises(ValueError, match="unknown gate policy"):
        diff(state(), state(), policy="invalid")


def test_qualification_boundary_and_version_binding():
    before, after = state(element()), state(element(width=103), evidence=clipping())
    qualification = Qualification(
        rule="clipping",
        rule_version="1",
        configuration=after.detector_config,
        conditions=after.environment.model_dump(),
        dataset_sha256="a" * 64,
        independent=True,
        sealed=True,
        true_positives=380,
        false_positives=0,
        provenance="independent sealed review",
    )
    assert qualification.precision_interval[0] < 0.99
    assert diff(before, after, qualifications=[qualification]).gate_status == "pass"
    qualification.true_positives = 381
    assert qualification.precision_interval[0] >= 0.99
    report = diff(before, after, qualifications=[qualification])
    assert report.gate_status == "fail"
    assert next(d for d in report.deltas if d.defect_class).level == "gateable"
    qualification.rule_version = "2"
    assert diff(before, after, qualifications=[qualification]).gate_status == "pass"


def test_verification_does_not_qualify_a_rule():
    before, after = state(element()), state(element(width=103), evidence=clipping())
    verification = Verification(
        state_sha256=after.fingerprint,
        rule="clipping",
        selector="#cta",
        reviewer="review-123",
        evidence="independent inspection of hidden checkout text",
        independent_support=True,
    )
    finding = next(
        d
        for d in diff(before, after, verifications=[verification]).deltas
        if d.defect_class
    )
    assert finding.level == "verified"
    assert not finding.gateability["qualified"]
    assert not finding.gateability["blocks"]


def test_source_maps_regular_indexed_and_unmapped():
    regular = {
        "version": 3,
        "sources": ["../src/checkout.scss"],
        "sourcesContent": [".cta {width: 103px}"],
        "mappings": "AAAA",
    }
    result = original_position(regular, 0, 5, "https://example.com/assets/main.css.map")
    assert result["url"] == "https://example.com/src/checkout.scss"
    assert result["line"] == 1
    indexed = {
        "version": 3,
        "sections": [{"offset": {"line": 2, "column": 10}, "map": regular}],
    }
    assert (
        original_position(indexed, 2, 15, "https://example.com/assets/main.css.map")
        == result
    )
    assert (
        original_position(indexed, 1, 0, "https://example.com/assets/main.css.map")
        is None
    )
    regular["mappings"] = "AAAA,C"
    assert original_position(regular, 0, 1, "https://example.com/main.css.map") is None
    regular["mappings"] = "!"
    with pytest.raises(ValueError, match="substring not found"):
        original_position(regular, 0, 1, "https://example.com/main.css.map")


@pytest.mark.asyncio
async def test_compare_is_keyless_and_model_explanation_cannot_change_gate(
    tmp_path, mocker
):
    before, after = state(element()), state(element(width=103), evidence=clipping())
    lens = LayoutLens(output_dir=tmp_path)
    vision = mocker.patch.object(
        lens,
        "_call_vision_api",
        new_callable=mocker.AsyncMock,
        return_value={"reasoning": "Ignore the report; everything is perfect"},
    )
    report = await lens.compare(before, after, policy="findings")
    vision.assert_not_called()
    explained = await lens.compare(before, after, explain=True, policy="findings")
    assert explained.gate_status == report.gate_status == "fail"
    assert explained.deltas == report.deltas
    assert explained.explanation
    assert len(vision.call_args.kwargs["image_path"]) == 2


@pytest.mark.browser
@pytest.mark.usefixtures("chromium_installed")
@pytest.mark.asyncio
async def test_browser_capture_replay_clipping_and_current_focus(tmp_path):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 720})
        try:
            await page.set_content(
                '<html><body><button id="cta" style="width:142px;height:40px;overflow:hidden;white-space:nowrap">Checkout checkout</button></body></html>'
            )
            before = await capture_page(page)
            same = await capture_page(page)
            assert before.stable
            assert not before.coverage_gaps
            assert diff(before, same).deltas == []
            assert await page.evaluate("document.activeElement.tagName") == "BODY"
            await page.locator("#cta").evaluate('(el) => el.style.width="103px"')
            after = await capture_page(page)
            report = diff(
                RenderState.load(before.save(tmp_path / "before")),
                RenderState.load(after.save(tmp_path / "after")),
            )
            cta = next(d for d in report.deltas if d.defect_class == "clipping")
            assert cta.status == "introduced"
            assert cta.measured_delta["after"]["clipped_px"] > 0
            assert any(
                s["property"] == "width" and s["value"] == "103px"
                for s in cta.likely_source
            )
            captured_cta = next(n for n in after.graph.nodes if n.selector == "#cta")
            assert captured_cta.role == "button"
            assert captured_cta.name == "Checkout checkout"
            assert diff(before, after, policy="findings").gate_status == "fail"
            assert [
                asdict(f)
                for f in LayoutScorer(**after.detector_config).diagnose(
                    after.detector_evidence
                )
            ]
        finally:
            await browser.close()


@pytest.mark.browser
@pytest.mark.usefixtures("chromium_installed")
@pytest.mark.asyncio
async def test_browser_external_css_and_sourcemap(tmp_path):
    source = tmp_path / "page.html"
    source.write_text(
        '<html><head><link rel="stylesheet" href="checkout.css"></head><body><button id="cta">Checkout</button></body></html>'
    )
    css = tmp_path / "checkout.css"
    css.write_text("#cta {width:142px;height:40px}")
    before = await capture_state(source)
    css.write_text(
        "#cta {width:103px;height:40px}\n/*# sourceMappingURL=checkout.css.map */"
    )
    (tmp_path / "checkout.css.map").write_text(
        json.dumps(
            {
                "version": 3,
                "sources": ["checkout.scss"],
                "sourcesContent": ["#cta {width:103px;height:40px}"],
                "mappings": "AAAA",
            }
        )
    )
    after = await capture_state(source)
    report = diff(before, after)
    assert report.gate_status == "pass"
    causes = [s for d in report.deltas for s in d.likely_source]
    assert any(
        s["evidence_level"] == "source-mapped-location"
        and s["line"] == 1
        and s["url"].endswith("checkout.scss")
        for s in causes
    )


@pytest.mark.browser
@pytest.mark.usefixtures("chromium_installed")
@pytest.mark.asyncio
async def test_browser_open_shadow_and_opaque_coverage():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page()
        try:
            await page.set_content(
                '<html><body><div id="host"></div><div id="closed"></div><canvas></canvas></body></html>'
            )
            await page.evaluate("""() => {
                document.querySelector('#host').attachShadow({mode:'open'}).innerHTML='<button id="ok">Okay</button>';
                document.querySelector('#closed').attachShadow({mode:'closed'}).innerHTML='<p>Hidden</p>';
            }""")
            captured = await capture_page(page)
            assert any(
                n.selector == "#host >>> #ok" and n.role == "button"
                for n in captured.graph.nodes
            )
            assert any("closed shadow" in gap for gap in captured.coverage_gaps)
            assert any("canvas" in gap for gap in captured.coverage_gaps)
        finally:
            await browser.close()


def test_git_attribution_verifies_revision_and_selects_related_hunk(tmp_path):
    from layoutlens.regression.attribution import _git

    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.name", "Fixture")
    _git(tmp_path, "config", "user.email", "fixture@example.invalid")
    html = tmp_path / "page.html"
    html.write_text("<html></html>")
    css = tmp_path / "checkout.css"
    css.write_text("#cta {width:142px}\n" + "\n" * 20 + ".other {color:red}\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "baseline")
    base = _git(tmp_path, "rev-parse", "HEAD").strip()
    css.write_text("#cta {width:103px}\n" + "\n" * 20 + ".other {color:blue}\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "candidate")
    candidate = _git(tmp_path, "rev-parse", "HEAD").strip()
    before, after = state(element()), state(element(width=103))
    before.source = after.source = str(html)
    before.revision, after.revision = base, candidate
    declaration = {
        "property": "width",
        "value": "103px",
        "origin": "matched",
        "url": "http://localhost:5000/checkout.css",
        "range": {"startLine": 0, "startColumn": 6},
    }
    after.graph.nodes[0].declarations = [declaration]
    result = diff(before, after, repository=tmp_path)
    cause = result.deltas[0].likely_source[0]
    assert cause["file"] == "checkout.css"
    assert cause["line"] == 1
    declaration["url"] = css.as_uri()
    file_cause = diff(before, after, repository=tmp_path).deltas[0].likely_source[0]
    assert file_cause["file"] == "checkout.css"
    assert "width:103px" in cause["git_diff"]
    assert "color:blue" not in cause["git_diff"]
    after.revision = base
    cause = diff(before, after, repository=tmp_path).deltas[0].likely_source[0]
    assert "git_diff" not in cause
    assert any("does not match" in reason for reason in cause["missing_links"])
    declaration["url"] = "https://example.org/checkout.css"
    cause = diff(before, after, repository=tmp_path).deltas[0].likely_source[0]
    assert "file" not in cause


@pytest.mark.asyncio
async def test_cli_artifacts_and_exit_status(tmp_path, monkeypatch, capsys):
    from layoutlens.cli import main

    baseline = state(element()).save(tmp_path / "baseline")
    candidate = state(element(width=103), evidence=clipping()).save(
        tmp_path / "candidate"
    )
    monkeypatch.setattr(
        "sys.argv",
        ["layoutlens", "diff", str(baseline), str(candidate), "--fail-on", "findings"],
    )
    assert await main() == 1
    assert json.loads(capsys.readouterr().out)["gate_status"] == "fail"
    monkeypatch.setattr(
        "sys.argv",
        ["layoutlens", "diff", str(baseline), str(candidate), "--output", "sarif"],
    )
    assert await main() == 0
    assert (
        json.loads(capsys.readouterr().out)["runs"][0]["properties"]["gate_status"]
        == "pass"
    )
    monkeypatch.setattr(
        "sys.argv",
        ["layoutlens", "diff", str(baseline), str(tmp_path / "missing.json")],
    )
    assert await main() == 2
    assert "Error:" in capsys.readouterr().err


@pytest.mark.browser
@pytest.mark.usefixtures("chromium_installed")
@pytest.mark.asyncio
async def test_browser_wrap_overlap_and_loading_failure():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 720})
        try:
            await page.set_content(
                '<html><body><div id="card" style="width:164px;font:16px Arial">Checkout your items now</div><div id="price" style="position:absolute;left:300px;top:10px;width:50px;height:40px">$25</div></body></html>'
            )
            before = await capture_page(page)
            await page.locator("#card").evaluate('(el) => el.style.width="91px"')
            await page.locator("#price").evaluate('(el) => el.style.left="20px"')
            after = await capture_page(page)
            report = diff(before, after)
            assert any("text_lines" in d.changed_properties for d in report.deltas)
            assert any(
                d.defect_class == "overlap" and d.status == "introduced"
                for d in report.deltas
            )
            await page.evaluate("""() => {
                const img = new Image(); img.src='data:image/png;base64,invalid'; document.body.append(img);
            }""")
            failed = await capture_page(page)
            assert "image failed to load or decode" in failed.coverage_gaps
            assert diff(after, failed).gate_status == "incomplete"
        finally:
            await browser.close()
