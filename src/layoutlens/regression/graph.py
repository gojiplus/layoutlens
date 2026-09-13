"""Sparse rendered relations and conservative element correspondence."""

from __future__ import annotations

from collections import defaultdict
from itertools import pairwise

from .models import Correspondence, Edge, Element, LayoutGraph


def build_graph(nodes: list[Element], tolerance: float = 1) -> LayoutGraph:
    """Build spatial relations with an x-axis sweep and sibling ordering."""
    edges = []
    by_key = {n.key: n for n in nodes}
    siblings: dict[str | None, list[Element]] = defaultdict(list)
    for node in nodes:
        if node.parent:
            edges.append(Edge(source=node.parent, target=node.key, relation="parent"))
        if node.visible:
            siblings[node.parent].append(node)
    visible = sorted((n for n in nodes if n.visible), key=lambda n: (n.bbox[0], n.key))
    active: list[Element] = []
    for node in visible:
        x, y, w, h = node.bbox
        active = [other for other in active if other.bbox[0] + other.bbox[2] >= x]
        for other in active:
            ox, oy, ow, oh = other.bbox
            ix = max(0, min(x + w, ox + ow) - max(x, ox))
            iy = max(0, min(y + h, oy + oh) - max(y, oy))
            if ix * iy > 0:
                edges.append(
                    Edge(
                        source=other.key,
                        target=node.key,
                        relation="overlap",
                        measured=ix * iy,
                    )
                )
                if ox <= x and oy <= y and ox + ow >= x + w and oy + oh >= y + h:
                    edges.append(
                        Edge(source=other.key, target=node.key, relation="containment")
                    )
                elif x <= ox and y <= oy and x + w >= ox + ow and y + h >= oy + oh:
                    edges.append(
                        Edge(source=node.key, target=other.key, relation="containment")
                    )
        active.append(node)
    for children in siblings.values():
        for axis, relation in ((0, "adjacent-x"), (1, "adjacent-y")):
            ordered = sorted(
                children, key=lambda n: (n.bbox[axis], n.bbox[1 - axis], n.key)
            )
            for a, b in pairwise(ordered):
                gap = b.bbox[axis] - a.bbox[axis] - a.bbox[axis + 2]
                edges.append(
                    Edge(source=a.key, target=b.key, relation=relation, measured=gap)
                )
                edges.append(
                    Edge(
                        source=a.key,
                        target=b.key,
                        relation="proximity",
                        measured=max(0, gap),
                    )
                )
        ordered = sorted(children, key=lambda n: (n.bbox[1], n.bbox[0], n.key))
        for a, b in pairwise(ordered):
            edges.append(Edge(source=a.key, target=b.key, relation="reading-order"))
        for axis, relation in ((0, "aligned-left"), (1, "aligned-top")):
            ordered = sorted(children, key=lambda n: (n.bbox[axis], n.key))
            for a, b in pairwise(ordered):
                distance = b.bbox[axis] - a.bbox[axis]
                if distance <= tolerance:
                    edges.append(
                        Edge(
                            source=a.key,
                            target=b.key,
                            relation=relation,
                            measured=distance,
                        )
                    )
    unique = {
        (e.source, e.target, e.relation): e
        for e in edges
        if e.source in by_key and e.target in by_key
    }
    return LayoutGraph(nodes=nodes, edges=[unique[k] for k in sorted(unique)])


def match_elements(
    before: LayoutGraph, after: LayoutGraph
) -> tuple[list[Correspondence], set[str], set[str]]:
    """Match unique identities, then mutual best candidates under matched parents.

    Geometric proximity alone cannot establish identity. Fallback matches need
    score >= 0.7 and a margin of >= 0.15 in both directions; ties abstain.
    """
    excluded = {"declarations", "attribution_gaps"}
    if [node.model_dump(exclude=excluded) for node in before.nodes] == [
        node.model_dump(exclude=excluded) for node in after.nodes
    ]:
        return (
            [
                Correspondence(
                    before=node.key,
                    after=node.key,
                    method="identical-rendered-structure",
                    score=1,
                )
                for node in before.nodes
            ],
            set(),
            set(),
        )
    left = {n.key: n for n in before.nodes}
    right = {n.key: n for n in after.nodes}
    matches: list[Correspondence] = []
    mapping: dict[str, str] = {}

    def accept(a: str, b: str, method: str, score: float = 1) -> None:
        matches.append(Correspondence(before=a, after=b, method=method, score=score))
        mapping[a] = b
        del left[a]
        del right[b]

    for attribute in ("data-testid", "id"):
        old: dict[str, list[str]] = defaultdict(list)
        new: dict[str, list[str]] = defaultdict(list)
        for node in left.values():
            if value := node.attributes.get(attribute):
                old[value].append(node.key)
        for node in right.values():
            if value := node.attributes.get(attribute):
                new[value].append(node.key)
        for value in sorted(old.keys() & new.keys()):
            if len(old[value]) == len(new[value]) == 1:
                a, b = old[value][0], new[value][0]
                if left[a].tag == right[b].tag:
                    accept(a, b, attribute)

    while left and right:
        groups_left: dict[tuple[str | None, str], list[Element]] = defaultdict(list)
        groups_right: dict[tuple[str | None, str], list[Element]] = defaultdict(list)
        for node in left.values():
            if node.parent is None or node.parent in mapping:
                groups_left[(mapping.get(node.parent or ""), node.tag)].append(node)
        for node in right.values():
            groups_right[(node.parent, node.tag)].append(node)
        candidates: list[tuple[float, str, str]] = []
        for group, old_nodes in groups_left.items():
            new_nodes = groups_right.get(group, [])
            for a in old_nodes:
                for b in new_nodes:
                    semantic = bool(
                        a.role and a.name and (a.role, a.name) == (b.role, b.name)
                    )
                    text = bool(a.text and a.text == b.text)
                    attrs = bool(a.attributes and a.attributes == b.attributes)
                    singleton = len(old_nodes) == len(new_nodes) == 1
                    if not singleton and not (semantic or text or attrs):
                        continue
                    same_styles = sum(
                        a.styles.get(k) == v for k, v in b.styles.items()
                    ) / max(1, len(b.styles))
                    geometry = 1 / (
                        1
                        + sum(abs(x - y) for x, y in zip(a.bbox, b.bbox, strict=True))
                        / 100
                    )
                    score = (
                        0.35
                        + 0.25 * (semantic or text or attrs)
                        + 0.2 * same_styles
                        + 0.2 * geometry
                    )
                    candidates.append((score, a.key, b.key))
        ranks_left: dict[str, list[tuple[float, str]]] = defaultdict(list)
        ranks_right: dict[str, list[tuple[float, str]]] = defaultdict(list)
        for score, a, b in candidates:
            ranks_left[a].append((score, b))
            ranks_right[b].append((score, a))
        for ranks in (ranks_left, ranks_right):
            for key, values in ranks.items():
                ranks[key] = sorted(values, reverse=True)[:2]
        accepted = []
        for a, values in ranks_left.items():
            score, b = values[0]
            reverse = ranks_right[b]
            if reverse[0][1] != a or score < 0.7:
                continue
            rivals = [items[1][0] for items in (values, reverse) if len(items) > 1]
            if not rivals or score - max(rivals) >= 0.15:
                accepted.append((score, a, b))
        if not accepted:
            break
        for score, a, b in sorted(accepted, reverse=True):
            if a in left and b in right:
                accept(a, b, "parent-and-features", score)
    return sorted(matches, key=lambda m: m.before), set(left), set(right)
