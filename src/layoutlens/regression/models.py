"""Versioned, portable browser evidence and regression reports."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Record(BaseModel):
    """Reject unknown fields and non-finite measurements in saved evidence."""

    model_config = ConfigDict(
        extra="forbid", allow_inf_nan=False, validate_default=True
    )


class Element(Record):
    """One DOM element; coordinates are unrounded document CSS pixels."""

    key: str
    selector: str
    parent: str | None = None
    tag: str
    attributes: dict[str, str] = Field(default_factory=dict)
    bbox: tuple[float, float, float, float]
    styles: dict[str, str] = Field(default_factory=dict)
    text: str = ""
    role: str = ""
    name: str = ""
    visible: bool = True
    focusable: bool = False
    interactive: bool = False
    control_state: dict[str, Any] = Field(default_factory=dict)
    focused: bool = False
    text_rects: list[tuple[float, float, float, float]] = Field(default_factory=list)
    declarations: list[dict[str, Any]] = Field(default_factory=list)
    attribution_gaps: list[str] = Field(default_factory=list)


class Edge(Record):
    """A measured structural or geometric relation between two nodes."""

    source: str
    target: str
    relation: str
    measured: float = 0


class LayoutGraph(Record):
    """Rendered nodes with sparse spatial and structural relations."""

    nodes: list[Element] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)


class CaptureEnvironment(Record):
    """Conditions that must agree before a regression gate is meaningful."""

    browser: str = "chromium"
    browser_version: str
    viewport: tuple[int, int]
    dpr: float = Field(gt=0)
    user_agent: str
    platform: str
    locale: str
    timezone: str
    color_scheme: str = "light"
    reduced_motion: str = "reduce"
    has_touch: bool = False
    emulation: dict[str, Any] = Field(default_factory=dict)
    scroll: tuple[float, float] = (0, 0)


class RenderState(Record):
    """A replayable capture with screenshot bytes kept outside its manifest."""

    schema_version: Literal[2] = 2
    source: str
    environment: CaptureEnvironment
    graph: LayoutGraph
    capabilities: dict[str, bool] = Field(default_factory=dict)
    geometry: dict[str, float] = Field(default_factory=dict)
    loading: dict[str, Any] = Field(default_factory=dict)
    accessibility: list[dict[str, Any]] = Field(default_factory=list)
    dom: str = ""
    detector_evidence: dict[str, Any] = Field(default_factory=dict)
    detector_config: dict[str, Any] = Field(default_factory=dict)
    rule_version: Literal["1"] = "1"
    coverage_gaps: list[str] = Field(default_factory=list)
    stable: bool = True
    revision: str | None = None
    screenshot: bytes = Field(default=b"", exclude=True)

    @model_validator(mode="after")
    def validate_graph(self) -> RenderState:
        """Require unique node identities and valid graph references."""
        keys = {node.key for node in self.graph.nodes}
        if len(keys) != len(self.graph.nodes):
            raise ValueError("duplicate element keys")
        if any(node.parent and node.parent not in keys for node in self.graph.nodes):
            raise ValueError("unknown parent")
        if any(
            edge.source not in keys or edge.target not in keys
            for edge in self.graph.edges
        ):
            raise ValueError("unknown edge endpoint")
        parents = {node.key: node.parent for node in self.graph.nodes}
        for key in parents:
            visited = set()
            node = key
            while node is not None:
                if node in visited:
                    raise ValueError("cyclic element ancestry")
                visited.add(node)
                node = parents[node]
        if any(node.bbox[2] < 0 or node.bbox[3] < 0 for node in self.graph.nodes):
            raise ValueError("negative element dimensions")
        channels = {
            "contrast",
            "overlaps",
            "clipping",
            "protrusion",
            "page_overflow",
            "truncation",
            "small_targets",
            "text_occlusion",
            "focus_obscured",
        }
        if self.detector_evidence and set(self.detector_evidence) != channels:
            raise ValueError("missing or unknown detector evidence channels")
        return self

    @property
    def fingerprint(self) -> str:
        """Bind review evidence to the exact captured facts and screenshot."""
        return hashlib.sha256(
            json.dumps(
                self.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
            ).encode()
            + self.screenshot
        ).hexdigest()

    def save(self, directory: str | Path) -> Path:
        """Save a new artifact directory; refuse to overwrite a baseline."""
        target = Path(directory)
        target.mkdir(parents=True, exist_ok=False)
        payload = self.model_dump(exclude={"dom"})
        assets = {"screenshot.png": self.screenshot, "dom.html": self.dom.encode()}
        payload["assets"] = {}
        for name, data in assets.items():
            (target / name).write_bytes(data)
            payload["assets"][name] = hashlib.sha256(data).hexdigest()
        manifest = target / "state.json"
        manifest.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        return manifest

    @classmethod
    def load(cls, path: str | Path) -> RenderState:
        """Load a versioned artifact and verify every referenced asset."""
        manifest = Path(path)
        if manifest.is_dir():
            manifest /= "state.json"
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        if payload.get("schema_version") != 2:
            raise ValueError("unsupported RenderState schema version")
        assets = payload.pop("assets", {})
        if set(assets) != {"screenshot.png", "dom.html"}:
            raise ValueError("artifact must contain screenshot.png and dom.html")
        data = {}
        for name, checksum in assets.items():
            asset = (manifest.parent / name).resolve()
            if asset.parent != manifest.parent.resolve():
                raise ValueError("asset escapes artifact directory")
            data[name] = asset.read_bytes()
            if hashlib.sha256(data[name]).hexdigest() != checksum:
                raise ValueError(f"asset checksum mismatch: {name}")
        return cls.model_validate(
            {
                **payload,
                "screenshot": data["screenshot.png"],
                "dom": data["dom.html"].decode(),
            }
        )

    def diff(self, after: RenderState, **options: Any) -> DiffReport:
        """Compare this baseline with a candidate without opening a browser."""
        from .diff import diff

        return diff(self, after, **options)


class Correspondence(Record):
    """An accepted one-to-one match, with the evidence used to accept it."""

    before: str
    after: str
    method: str
    score: float = Field(ge=0, le=1)


class VisualDelta(Record):
    """Measured change, diagnosis, and independently evaluated gate decision."""

    element: str
    before_element: str | None = None
    after_element: str | None = None
    before_bbox: tuple[float, float, float, float] | None = None
    after_bbox: tuple[float, float, float, float] | None = None
    changed_properties: dict[str, Any] = Field(default_factory=dict)
    pixel_region: dict[str, Any] = Field(default_factory=dict)
    measured_delta: dict[str, Any] = Field(default_factory=dict)
    defect_class: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    severity: Literal["note", "warning", "error"] = "note"
    level: Literal["observation", "candidate", "verified", "gateable"] = "observation"
    status: Literal[
        "changed", "introduced", "worsened", "unchanged", "resolved", "unresolved"
    ] = "changed"
    likely_source: list[dict[str, Any]] = Field(default_factory=list)
    gateability: dict[str, Any] = Field(
        default_factory=lambda: {"qualified": False, "blocks": False}
    )


class DiffReport(Record):
    """Structured comparison whose gate status never depends on prose."""

    schema_version: Literal[1] = 1
    before: str
    after: str
    matches: list[Correspondence] = Field(default_factory=list)
    deltas: list[VisualDelta] = Field(default_factory=list)
    incomplete_reasons: list[str] = Field(default_factory=list)
    policy: Literal["qualified", "findings", "nothing"] = "qualified"
    tolerance_px: float = 1
    explanation: str | None = None

    @property
    def gate_status(self) -> Literal["pass", "fail", "incomplete"]:
        """Distinguish missing evidence from a successful comparison."""
        if self.incomplete_reasons:
            return "incomplete"
        return (
            "fail" if any(d.gateability.get("blocks") for d in self.deltas) else "pass"
        )

    def to_json(self) -> str:
        """Serialize evidence and the derived gate status."""
        return json.dumps(
            {**self.model_dump(), "gate_status": self.gate_status}, indent=2
        )

    def summary(self) -> str:
        """Describe the result without interpreting observations as defects."""
        counts = {
            status: sum(
                d.status == status and d.defect_class is not None for d in self.deltas
            )
            for status in (
                "introduced",
                "worsened",
                "unchanged",
                "resolved",
                "unresolved",
            )
        }
        return f"Gate: {self.gate_status}; candidate findings: {counts}; observations: {sum(d.defect_class is None for d in self.deltas)}"
