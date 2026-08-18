"""Expert persona registry for LayoutLens."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .experts import (
    AccessibilityExpert,
    ConversionExpert,
    EcommerceExpert,
    FinanceExpert,
    HealthcareExpert,
    MobileExpert,
)

if TYPE_CHECKING:
    from .base import ExpertPrompt

EXPERT_REGISTRY = {
    "accessibility_expert": AccessibilityExpert(),
    "conversion_expert": ConversionExpert(),
    "mobile_expert": MobileExpert(),
    "ecommerce_expert": EcommerceExpert(),
    "healthcare_expert": HealthcareExpert(),
    "finance_expert": FinanceExpert(),
}


def get_expert(expert_name: str) -> ExpertPrompt | None:
    """Get an expert instance by name."""
    return EXPERT_REGISTRY.get(expert_name)


def list_available_experts() -> list[str]:
    """Get list of available expert personas."""
    return list(EXPERT_REGISTRY.keys())
