"""Base prompt template system for LayoutLens expert analysis."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from .context import EvaluationCriteria, Instructions, UserContext


@dataclass
class PromptTemplate:
    """A reusable prompt template with variable substitution."""

    name: str
    description: str
    system_prompt: str
    user_prompt_template: str
    variables: dict[str, str] = field(default_factory=dict)
    evaluation_criteria: list[str] = field(default_factory=list)
    confidence_calibration: dict[str, Any] = field(default_factory=dict)

    def render(self, query: str, instructions: Instructions | None = None, **kwargs) -> tuple[str, str]:
        """Render the template with provided variables and context.

        Returns:
            tuple: (system_prompt, user_prompt)
        """
        # Start with base system prompt
        system = self.system_prompt

        # Add evaluation criteria if specified
        if self.evaluation_criteria:
            criteria_text = "\n\nEVALUATION CRITERIA:\n" + "\n".join(
                f"- {criterion}" for criterion in self.evaluation_criteria
            )
            system += criteria_text

        # Add confidence calibration guidance
        if self.confidence_calibration:
            confidence_text = "\n\nCONFIDENCE CALIBRATION:\n"
            for level, guidance in self.confidence_calibration.items():
                confidence_text += f"- {level}: {guidance}\n"
            system += confidence_text

        # Render user prompt with variables
        user_prompt = self.user_prompt_template.format(query=query, **self.variables, **kwargs)

        # Add instruction-based enhancements
        if instructions:
            if instructions.focus_areas:
                user_prompt += f"\n\nPay special attention to: {', '.join(instructions.focus_areas)}"

            if instructions.evaluation_criteria:
                user_prompt += f"\n\nEvaluation criteria: {instructions.evaluation_criteria}"

            if instructions.user_context:
                context_str = instructions.user_context.to_prompt_text()
                if context_str:
                    user_prompt += f"\n\nUser context: {context_str}"

            if instructions.output_style:
                style_guidance = self._get_output_style_guidance(instructions.output_style)
                user_prompt += f"\n\n{style_guidance}"

        return system, user_prompt

    def _get_output_style_guidance(self, output_style: str) -> str:
        """Get guidance text for different output styles."""
        styles = {
            "actionable_recommendations": "Provide specific, implementable recommendations with priority levels.",
            "quick_assessment": "Provide a concise assessment focusing on the most critical issues.",
            "detailed_analysis": "Provide comprehensive analysis with examples and detailed explanations.",
            "checklist_format": "Structure your response as a checklist of pass/fail items.",
            "comparative_analysis": "Compare against industry best practices and competitors.",
        }
        return styles.get(output_style, "")


class ExpertPrompt(ABC):
    """Abstract base class for domain expert prompts."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Expert name/identifier."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of expert's specialty."""
        pass

    @property
    @abstractmethod
    def domain_knowledge(self) -> list[str]:
        """List of domain knowledge areas."""
        pass

    @abstractmethod
    def get_template(self) -> PromptTemplate:
        """Get the expert's prompt template."""
        pass

    def analyze(self, query: str, instructions: Instructions | None = None) -> tuple[str, str]:
        """Generate expert analysis prompts for the given query.

        Returns:
            tuple: (system_prompt, user_prompt)
        """
        template = self.get_template()
        return template.render(query, instructions)


def build_custom_prompt(
    name: str,
    description: str,
    expertise_areas: list[str],
    evaluation_criteria: list[str],
    confidence_guidelines: dict[str, str],
    focus_instructions: str | None = None,
) -> PromptTemplate:
    """Build a custom expert prompt for specific domain needs.

    Args:
        name: Name of the expert persona
        description: Description of the expert's role
        expertise_areas: List of domain expertise areas
        evaluation_criteria: Specific criteria to evaluate
        confidence_guidelines: Guidelines for confidence scoring
        focus_instructions: Additional focus instructions

    Returns:
        PromptTemplate: Ready-to-use prompt template
    """
    # Build system prompt
    system_prompt = f"You are a {name} with deep expertise in:\n"
    system_prompt += "\n".join(f"- {area}" for area in expertise_areas)
    system_prompt += f"\n\n{description}"

    if focus_instructions:
        system_prompt += f"\n\nFOCUS: {focus_instructions}"

    system_prompt += """

Your role is to analyze user interface screenshots and provide expert-level feedback based on your specialized knowledge. Always:

1. Reference specific visual elements you observe
2. Apply industry best practices and standards
3. Provide actionable, implementable recommendations
4. Explain your reasoning clearly
5. Calibrate confidence based on visual evidence

Respond in this JSON format:
{"answer": "your expert assessment", "confidence": 0.0-1.0, "reasoning": "detailed professional analysis"}"""

    # Build user prompt template
    user_prompt_template = """Analyze this UI screenshot and answer: {query}

Apply your expertise to evaluate this interface against professional standards and best practices in your domain."""

    return PromptTemplate(
        name=name,
        description=description,
        system_prompt=system_prompt,
        user_prompt_template=user_prompt_template,
        evaluation_criteria=evaluation_criteria,
        confidence_calibration=confidence_guidelines,
    )
