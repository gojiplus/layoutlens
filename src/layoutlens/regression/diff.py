"""Offline correspondence, measured deltas, and replayed defect predicates."""

from __future__ import annotations

from dataclasses import asdict
from io import BytesIO
from typing import TYPE_CHECKING, Any

from PIL import Image, ImageChops

from ..layout.geometry import LayoutScorer
from .graph import build_graph, match_elements
from .models import DiffReport, Element, RenderState, VisualDelta
from .policy import GatePolicy, Qualification, Verification, gate_decision

if TYPE_CHECKING:
    from pathlib import Path


def _changes(a: Element, b: Element) -> dict[str, Any]:
    changes = {}
    for field in (
        "text",
        "role",
        "name",
        "visible",
        "focusable",
        "interactive",
        "focused",
        "attributes",
    ):
        before, after = getattr(a, field), getattr(b, field)
        if before != after:
            changes[field] = {"before": before, "after": after}
    for prop in sorted(a.styles.keys() | b.styles.keys()):
        if a.styles.get(prop) != b.styles.get(prop):
            changes[f"css.{prop}"] = {
                "before": a.styles.get(prop),
                "after": b.styles.get(prop),
            }
    for index, field in enumerate(("x", "y", "width", "height")):
        if a.bbox[index] != b.bbox[index]:
            changes[field] = {
                "before": a.bbox[index],
                "after": b.bbox[index],
                "delta": b.bbox[index] - a.bbox[index],
            }
    lines_a = len({round(r[1], 2) for r in a.text_rects})
    lines_b = len({round(r[1], 2) for r in b.text_rects})
    if lines_a != lines_b:
        changes["text_lines"] = {"before": lines_a, "after": lines_b}
    return changes


def _delta(a: Element | None, b: Element | None, **kwargs: Any) -> VisualDelta:
    node = b or a
    if node is None:
        raise ValueError("a delta needs an element")
    return VisualDelta(
        element=node.selector,
        before_element=a.key if a else None,
        after_element=b.key if b else None,
        before_bbox=a.bbox if a else None,
        after_bbox=b.bbox if b else None,
        pixel_region={
            "before_css": a.bbox if a else None,
            "after_css": b.bbox if b else None,
        },
        **kwargs,
    )


def _magnitude(finding: dict) -> float:
    measured = finding["measured"]
    rule = finding["defect_class"]
    if rule == "contrast":
        return max(0, finding["threshold"]["min_ratio"] - measured["contrast_ratio"])
    if rule == "target-size":
        return max(
            0,
            finding["threshold"]["min_px"]
            - min(measured["width_px"], measured["height_px"]),
        )
    if rule in {"text-occlusion", "focus-obscured"}:
        return measured.get(
            "covered_samples",
            measured["sampled_points"] - measured.get("visible_sample_points", 0),
        ) / max(1, measured["sampled_points"])
    return next(
        (
            float(measured[k])
            for k in ("intersection_px2", "clipped_px", "overflow_px", "hidden_px")
            if k in measured
        ),
        0,
    )


def _diagnose(state: RenderState) -> list[dict]:
    if not state.detector_evidence:
        return []
    return [
        asdict(f)
        for f in LayoutScorer(**state.detector_config).diagnose(state.detector_evidence)
    ]


def diff(
    before: RenderState,
    after: RenderState,
    *,
    tolerance_px: float = 1,
    policy: GatePolicy = "qualified",
    qualifications: list[Qualification] | None = None,
    verifications: list[Verification] | None = None,
    repository: str | Path | None = None,
) -> DiffReport:
    """Compare persisted measurements without a browser or model call.

    Args:
        before: Baseline render state.
        after: Candidate render state.
        tolerance_px: Significance tolerance for geometric movement in CSS pixels.
        policy: Qualified gates by default, explicit findings, or report-only nothing.
        qualifications: Independent rule qualification records; none ship by default.
        verifications: Recorded review or independent evidence for individual findings.
        repository: Optional local repository for revision-verified git attribution.

    Returns:
        Structured observations, candidate regressions, and completeness status.
    """
    if tolerance_px < 0 or not float("-inf") < tolerance_px < float("inf"):
        raise ValueError("tolerance_px must be finite and non-negative")
    gate_decision(policy, regression=False)
    gaps = [
        f"{label}: {gap}"
        for label, state in [("before", before), ("after", after)]
        for gap in state.coverage_gaps
    ]
    for label, state in [("before", before), ("after", after)]:
        if not state.stable:
            gaps.append(f"{label}: unstable capture")
        if not state.screenshot:
            gaps.append(f"{label}: missing screenshot")
        if not state.detector_evidence:
            gaps.append(f"{label}: missing detector evidence")
    if before.environment != after.environment:
        gaps.append("capture environments differ")
    if (
        before.detector_config != after.detector_config
        or before.rule_version != after.rule_version
    ):
        gaps.append("detector configuration or version differs")
    old = {n.key: n for n in before.graph.nodes}
    new = {n.key: n for n in after.graph.nodes}
    matches, unmatched_before, unmatched_after = match_elements(
        before.graph, after.graph
    )
    mapping = {m.before: m.after for m in matches}
    reverse = {m.after: m.before for m in matches}
    deltas = []
    ambiguous_before, ambiguous_after = set(), set()
    for a in unmatched_before:
        for b in unmatched_after:
            if old[a].tag == new[b].tag:
                ambiguous_before.add(a)
                ambiguous_after.add(b)
    if ambiguous_before:
        gaps.append("ambiguous element correspondence")
    for match in matches:
        a, b = old[match.before], new[match.after]
        changes = _changes(a, b)
        if changes:
            geometry = {
                key: value["delta"]
                for key, value in changes.items()
                if "delta" in value
            }
            deltas.append(
                _delta(
                    a,
                    b,
                    changed_properties=changes,
                    measured_delta=geometry,
                    evidence={
                        "match": match.model_dump(),
                        "geometrically_significant": any(
                            abs(v) > tolerance_px for v in geometry.values()
                        ),
                    },
                )
            )
    deltas.extend(
        _delta(
            old[key],
            None,
            status="unresolved" if key in ambiguous_before else "resolved",
            changed_properties={"presence": {"before": True, "after": False}},
        )
        for key in sorted(unmatched_before)
    )
    deltas.extend(
        _delta(
            None,
            new[key],
            status="unresolved" if key in ambiguous_after else "introduced",
            changed_properties={"presence": {"before": False, "after": True}},
        )
        for key in sorted(unmatched_after)
    )

    def edges(state: RenderState, translate: dict[str, str] | None = None) -> dict:
        result = {}
        for edge in build_graph(state.graph.nodes, tolerance_px).edges:
            a, b = edge.source, edge.target
            if translate is not None:
                if a not in translate or b not in translate:
                    continue
                a, b = translate[a], translate[b]
            if edge.relation in {"overlap", "proximity", "aligned-left", "aligned-top"}:
                a, b = sorted((a, b))
            result[a, b, edge.relation] = edge.measured
        return result

    old_edges, new_edges = edges(before, mapping), edges(after)
    for key in sorted(old_edges.keys() | new_edges.keys()):
        if old_edges.get(key) == new_edges.get(key):
            continue
        a, b, relation = key
        if a not in reverse or b not in reverse:
            continue
        deltas.append(
            _delta(
                old[reverse[a]],
                new[a],
                changed_properties={
                    f"relation.{relation}": {
                        "before": old_edges.get(key),
                        "after": new_edges.get(key),
                    }
                },
                evidence={"partner": b},
                measured_delta={
                    "before": old_edges.get(key),
                    "after": new_edges.get(key),
                },
            )
        )
    selectors_old = {n.selector: n.key for n in old.values()}
    selectors_new = {n.selector: n.key for n in new.values()}

    def finding_key(f: dict, selectors: dict, translate: dict | None = None) -> tuple:
        node = selectors.get(f["selector"], f["selector"])
        partner_selector = f["measured"].get(
            "partner", f["measured"].get("occluder", "")
        )
        partner = selectors.get(partner_selector, partner_selector)
        if translate is not None:
            node, partner = (
                translate.get(node, "before:" + node),
                translate.get(partner, partner),
            )
        if f["defect_class"] == "overlap":
            node, partner = sorted((node, partner))
        return (
            f["defect_class"],
            node,
            partner,
            f["measured"].get("edge", ""),
            f["measured"].get("clipped_axis", ""),
        )

    after_fingerprint = after.fingerprint if verifications else ""
    old_findings = {
        finding_key(f, selectors_old, mapping): f for f in _diagnose(before)
    }
    new_findings = {finding_key(f, selectors_new): f for f in _diagnose(after)}
    for key in sorted(old_findings.keys() | new_findings.keys()):
        a, b = old_findings.get(key), new_findings.get(key)
        f = b or a
        if f is None:
            continue
        old_node = old.get(selectors_old.get(a["selector"], "")) if a else None
        new_node = new.get(selectors_new.get(b["selector"], "")) if b else None
        if new_node and not old_node and new_node.key in reverse:
            old_node = old[reverse[new_node.key]]
        if old_node and not new_node and old_node.key in mapping:
            new_node = new[mapping[old_node.key]]
        if not old_node and not new_node:
            gaps.append(f"unresolved finding element: {f['selector']}")
            continue
        status = (
            "resolved"
            if b is None
            else "introduced"
            if a is None
            else "worsened"
            if _magnitude(b) > _magnitude(a)
            else "unchanged"
        )
        if (old_node and old_node.key in ambiguous_before) or (
            new_node and new_node.key in ambiguous_after
        ):
            status = "unresolved"
        qualification = next(
            (
                q
                for q in qualifications or []
                if q.qualifies(
                    f["defect_class"],
                    after.rule_version,
                    after.detector_config,
                    after.environment.model_dump(),
                )
            ),
            None,
        )
        verification = next(
            (v for v in verifications or [] if v.supports(f, after_fingerprint)), None
        )
        exceptions = f["measured"].get("manual_review_exceptions", [])
        qualified = qualification is not None and (
            not exceptions or verification is not None
        )
        evidence = {
            "before": a,
            "after": b,
            "verification": verification.model_dump() if verification else None,
            "qualification": qualification.model_dump()
            | {"precision_interval": qualification.precision_interval}
            if qualification
            else None,
        }
        deltas.append(
            _delta(
                old_node,
                new_node,
                status=status,
                defect_class=f["defect_class"],
                level="gateable"
                if qualified
                else "verified"
                if verification
                else "candidate",
                severity="warning",
                evidence=evidence,
                measured_delta={
                    "before": a["measured"] if a else None,
                    "after": b["measured"] if b else None,
                },
                gateability=gate_decision(
                    policy,
                    regression=status in {"introduced", "worsened"},
                    qualified=qualified,
                    complete=not gaps,
                ),
            )
        )
    if before.geometry != after.geometry:
        deltas.append(
            VisualDelta(
                element="document",
                changed_properties={
                    "geometry": {"before": before.geometry, "after": after.geometry}
                },
            )
        )
    if before.screenshot and after.screenshot:
        with (
            Image.open(BytesIO(before.screenshot)) as a_image,
            Image.open(BytesIO(after.screenshot)) as b_image,
        ):
            if a_image.size == b_image.size:
                region = ImageChops.difference(
                    a_image.convert("RGB"), b_image.convert("RGB")
                ).getbbox()
                if region:
                    deltas.append(
                        VisualDelta(
                            element="pixels",
                            pixel_region={
                                "device_pixels": region,
                                "dpr": after.environment.dpr,
                            },
                            evidence={
                                "classification": "pixel observation; no defect inferred"
                            },
                        )
                    )
            else:
                deltas.append(
                    VisualDelta(
                        element="pixels",
                        changed_properties={
                            "image_size": {
                                "before": a_image.size,
                                "after": b_image.size,
                            }
                        },
                    )
                )
    from .attribution import attribute

    for delta in deltas:
        delta.pixel_region.update(
            before_dpr=before.environment.dpr, after_dpr=after.environment.dpr
        )
        delta.likely_source = attribute(delta, before, after, repository)
        if delta.after_element and not delta.likely_source:
            node = new.get(delta.after_element)
            delta.evidence["attribution_gaps"] = (
                node.attribution_gaps if node else []
            ) or ["no changed matched declaration linked to this consequence"]
        if gaps:
            delta.gateability["blocks"] = False
            delta.gateability["reason"] = "incomplete comparison"
    return DiffReport(
        before=before.source,
        after=after.source,
        matches=matches,
        deltas=deltas,
        incomplete_reasons=sorted(set(gaps)),
        policy=policy,
        tolerance_px=tolerance_px,
    )
