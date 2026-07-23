"""Deterministic accessibility engine for LayoutLens.

Provides real, engine-backed WCAG checks by injecting a vendored axe-core
bundle into pages via Playwright and mapping the results into typed reports.

This subpackage is intentionally self-contained; wiring it into the public
``check_accessibility`` API is handled separately.
"""

from .axe import AXE_VERSION, AxeAuditor
from .types import A11yFinding, A11yReport

__all__ = [
    "AXE_VERSION",
    "AxeAuditor",
    "A11yFinding",
    "A11yReport",
]
