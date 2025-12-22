"""Rich context and instruction handling for enhanced prompt engineering."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class UserContext:
    """Rich user context for targeted UI analysis."""

    target_audience: str | None = None
    device_usage: str | None = None  # "mobile_primary", "desktop_primary", "mixed"
    business_goals: list[str] = field(default_factory=list)
    industry: str | None = None
    accessibility_needs: list[str] = field(default_factory=list)
    technical_constraints: list[str] = field(default_factory=list)
    brand_guidelines: dict[str, Any] = field(default_factory=dict)
    user_personas: list[str] = field(default_factory=list)

    def to_prompt_text(self) -> str:
        """Convert context to natural language for prompt inclusion."""
        parts = []

        if self.target_audience:
            parts.append(f"Target audience: {self.target_audience}")

        if self.device_usage:
            parts.append(f"Primary device usage: {self.device_usage}")

        if self.business_goals:
            parts.append(f"Business goals: {', '.join(self.business_goals)}")

        if self.industry:
            parts.append(f"Industry: {self.industry}")

        if self.accessibility_needs:
            parts.append(f"Accessibility requirements: {', '.join(self.accessibility_needs)}")

        if self.technical_constraints:
            parts.append(f"Technical constraints: {', '.join(self.technical_constraints)}")

        if self.user_personas:
            parts.append(f"User personas to consider: {', '.join(self.user_personas)}")

        if self.brand_guidelines:
            guidelines_str = ", ".join(f"{k}: {v}" for k, v in self.brand_guidelines.items())
            parts.append(f"Brand guidelines: {guidelines_str}")

        return ". ".join(parts)


@dataclass
class EvaluationCriteria:
    """Structured evaluation criteria for UI analysis."""

    primary_focus: str  # Main evaluation focus
    standards: list[str] = field(default_factory=list)  # WCAG, Material Design, etc.
    metrics: list[str] = field(default_factory=list)  # Specific metrics to evaluate
    priorities: list[str] = field(default_factory=list)  # Priority order of evaluation
    constraints: list[str] = field(default_factory=list)  # Must-have constraints

    def to_prompt_text(self) -> str:
        """Convert criteria to structured prompt text."""
        text = f"Primary focus: {self.primary_focus}"

        if self.standards:
            text += f"\nStandards to apply: {', '.join(self.standards)}"

        if self.metrics:
            text += f"\nMetrics to evaluate: {', '.join(self.metrics)}"

        if self.priorities:
            text += f"\nPriority order: {' > '.join(self.priorities)}"

        if self.constraints:
            text += f"\nMust-have requirements: {', '.join(self.constraints)}"

        return text


@dataclass
class Instructions:
    """Rich instruction set for enhanced UI analysis."""

    expert_persona: str | None = None  # Which expert to use
    focus_areas: list[str] = field(default_factory=list)  # Specific areas to focus on
    evaluation_criteria: str | None = None  # Custom evaluation criteria
    user_context: UserContext | None = None  # Rich user context
    output_style: str = "actionable_recommendations"  # How to structure output
    depth_level: str = "detailed"  # "quick", "detailed", "comprehensive"
    comparison_baseline: str | None = None  # What to compare against
    custom_instructions: str | None = None  # Additional custom guidance

    @classmethod
    def for_accessibility_audit(
        cls, standards: list[str] = None, user_needs: list[str] = None, compliance_level: str = "AA"
    ) -> Instructions:
        """Create instructions for accessibility auditing."""
        standards = standards or ["WCAG_2.1", "Section_508"]
        user_needs = user_needs or ["screen_readers", "keyboard_navigation", "low_vision"]

        return cls(
            expert_persona="accessibility_expert",
            focus_areas=["contrast_ratios", "keyboard_navigation", "screen_reader_compatibility"],
            evaluation_criteria=f"Evaluate against {' and '.join(standards)} Level {compliance_level}",
            user_context=UserContext(accessibility_needs=user_needs, target_audience="users_with_disabilities"),
            output_style="checklist_format",
            depth_level="comprehensive",
        )

    @classmethod
    def for_conversion_optimization(
        cls, business_goals: list[str] = None, industry: str = None, target_audience: str = None
    ) -> Instructions:
        """Create instructions for conversion rate optimization."""
        business_goals = business_goals or ["reduce_cart_abandonment", "increase_signups"]

        return cls(
            expert_persona="conversion_expert",
            focus_areas=["cta_prominence", "trust_signals", "friction_points", "value_proposition"],
            evaluation_criteria="Analyze for conversion optimization and user flow efficiency",
            user_context=UserContext(business_goals=business_goals, industry=industry, target_audience=target_audience),
            output_style="actionable_recommendations",
            depth_level="detailed",
        )

    @classmethod
    def for_mobile_optimization(cls, device_types: list[str] = None, performance_focus: bool = True) -> Instructions:
        """Create instructions for mobile optimization analysis."""
        device_types = device_types or ["smartphone", "tablet"]

        focus_areas = ["touch_targets", "readability", "navigation"]
        if performance_focus:
            focus_areas.extend(["loading_performance", "interaction_responsiveness"])

        return cls(
            expert_persona="mobile_expert",
            focus_areas=focus_areas,
            evaluation_criteria="Evaluate mobile user experience and performance",
            user_context=UserContext(
                device_usage="mobile_primary", technical_constraints=["limited_bandwidth", "touch_only_interaction"]
            ),
            output_style="actionable_recommendations",
            depth_level="detailed",
        )

    @classmethod
    def for_ecommerce_analysis(cls, page_type: str = "product_page", business_model: str = "b2c") -> Instructions:
        """Create instructions for e-commerce analysis."""
        focus_areas_map = {
            "product_page": ["product_imagery", "pricing_clarity", "add_to_cart", "trust_signals"],
            "checkout": ["form_simplicity", "payment_security", "progress_indicators", "error_handling"],
            "homepage": ["value_proposition", "navigation", "product_discovery", "brand_trust"],
        }

        return cls(
            expert_persona="ecommerce_expert",
            focus_areas=focus_areas_map.get(page_type, []),
            evaluation_criteria=f"Analyze {page_type} for {business_model} e-commerce best practices",
            user_context=UserContext(
                business_goals=["increase_conversions", "reduce_cart_abandonment"], industry="ecommerce"
            ),
            output_style="actionable_recommendations",
            depth_level="detailed",
        )

    def merge_with_context(self, additional_context: dict[str, Any]) -> Instructions:
        """Merge with additional context while preserving existing instructions."""
        # Create a copy of current instructions
        merged = Instructions(
            expert_persona=self.expert_persona,
            focus_areas=self.focus_areas.copy(),
            evaluation_criteria=self.evaluation_criteria,
            user_context=self.user_context,
            output_style=self.output_style,
            depth_level=self.depth_level,
            comparison_baseline=self.comparison_baseline,
            custom_instructions=self.custom_instructions,
        )

        # Merge additional context
        for key, value in additional_context.items():
            if hasattr(merged, key):
                if key == "focus_areas" and isinstance(value, list):
                    merged.focus_areas.extend(value)
                elif key == "custom_instructions" and value:
                    if merged.custom_instructions:
                        merged.custom_instructions += f" {value}"
                    else:
                        merged.custom_instructions = value
                else:
                    setattr(merged, key, value)

        return merged
