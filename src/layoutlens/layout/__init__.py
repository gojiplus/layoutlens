"""Deterministic layout/geometry scorers for LayoutLens.

The layout analog of :mod:`layoutlens.a11y`: keyless, LLM-free detectors that
measure geometric and contrast defects directly off a rendered page — overlap,
clipping, viewport protrusion, undersized interactive targets, and low text
contrast — plus focus obscuration, text occlusion, and a computed-style reader.
Foundational measurement math was ported from the UIJudgeBench render-verifier;
the newer standards and occlusion checks are independent LayoutLens detectors.
"""

from __future__ import annotations

from .contrast import (
    AA_LARGE_TEXT,
    AA_NORMAL_TEXT,
    check_contrast,
    contrast_ratio,
    is_large_text,
    parse_css_color,
    relative_luminance,
)
from .geometry import LayoutScorer
from .styles import element_geometry, read_computed_styles
from .types import LayoutFinding, LayoutReport

__all__ = [
    "AA_LARGE_TEXT",
    "AA_NORMAL_TEXT",
    "LayoutFinding",
    "LayoutReport",
    "LayoutScorer",
    "check_contrast",
    "contrast_ratio",
    "element_geometry",
    "is_large_text",
    "parse_css_color",
    "read_computed_styles",
    "relative_luminance",
]
