"""Browser evidence, offline layout regression, and explicit CI policy."""

from .models import DiffReport, LayoutGraph, RenderState, VisualDelta
from .policy import GatePolicy, Qualification, Verification

__all__ = [
    "DiffReport",
    "GatePolicy",
    "LayoutGraph",
    "Qualification",
    "RenderState",
    "Verification",
    "VisualDelta",
]
