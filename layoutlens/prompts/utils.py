"""Prompt engineering utilities for testing, optimization, and validation."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from .base import ExpertPrompt, PromptTemplate
from .context import Instructions
from .experts import (
    AccessibilityExpert,
    ConversionExpert,
    EcommerceExpert,
    FinanceExpert,
    HealthcareExpert,
    MobileExpert,
)


@dataclass
class PromptTestResult:
    """Result from testing a prompt variant."""

    prompt_variant: str
    test_query: str
    response_quality: float  # 0.0-1.0 quality score
    response_time: float
    confidence_score: float
    actionability_score: float  # How actionable the recommendations are
    specificity_score: float  # How specific the feedback is
    raw_response: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PromptOptimizationReport:
    """Report from prompt optimization analysis."""

    original_prompt: str
    optimized_prompt: str
    improvement_areas: list[str]
    performance_metrics: dict[str, float]
    recommendations: list[str]
    confidence_in_optimization: float


# Expert registry for easy access
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


def test_prompt(
    prompt_template: PromptTemplate,
    test_queries: list[str],
    instructions_variants: list[Instructions | None] = None,
    evaluation_criteria: dict[str, Any] | None = None,
) -> list[PromptTestResult]:
    """Test a prompt template against multiple queries and instruction variants.

    Args:
        prompt_template: The prompt template to test
        test_queries: List of test queries to evaluate
        instructions_variants: Different instruction sets to test
        evaluation_criteria: Custom criteria for evaluating results

    Returns:
        List of test results for analysis
    """
    results = []
    instructions_variants = instructions_variants or [None]

    for query in test_queries:
        for i, instructions in enumerate(instructions_variants):
            start_time = time.time()

            try:
                # Generate prompt
                system_prompt, user_prompt = prompt_template.render(query, instructions)
                response_time = time.time() - start_time

                # Evaluate prompt quality (simplified heuristic evaluation)
                quality_score = _evaluate_prompt_quality(system_prompt, user_prompt, query)

                result = PromptTestResult(
                    prompt_variant=f"variant_{i}",
                    test_query=query,
                    response_quality=quality_score["overall"],
                    response_time=response_time,
                    confidence_score=quality_score["confidence_guidance"],
                    actionability_score=quality_score["actionability"],
                    specificity_score=quality_score["specificity"],
                    raw_response=f"System: {system_prompt[:200]}...\nUser: {user_prompt[:200]}...",
                    metadata={
                        "instructions_used": instructions.__class__.__name__ if instructions else None,
                        "prompt_length": len(system_prompt) + len(user_prompt),
                        "detailed_scores": quality_score,
                    },
                )
                results.append(result)

            except Exception as e:
                # Handle test failures gracefully
                result = PromptTestResult(
                    prompt_variant=f"variant_{i}",
                    test_query=query,
                    response_quality=0.0,
                    response_time=time.time() - start_time,
                    confidence_score=0.0,
                    actionability_score=0.0,
                    specificity_score=0.0,
                    raw_response=f"Error: {str(e)}",
                    metadata={"error": str(e)},
                )
                results.append(result)

    return results


def optimize_prompt(
    base_prompt: PromptTemplate,
    sample_queries: list[str],
    optimization_goals: list[str] = None,
    expert_domain: str | None = None,
) -> PromptOptimizationReport:
    """Optimize a prompt based on sample queries and optimization goals.

    Args:
        base_prompt: The base prompt template to optimize
        sample_queries: Sample queries to test optimization against
        optimization_goals: Goals like ["improve_specificity", "reduce_length", "increase_actionability"]
        expert_domain: Domain to optimize for (e.g., "accessibility", "conversion")

    Returns:
        Optimization report with recommendations
    """
    optimization_goals = optimization_goals or ["improve_specificity", "increase_actionability"]

    # Analyze current prompt performance
    current_results = test_prompt(base_prompt, sample_queries)
    current_metrics = _aggregate_test_metrics(current_results)

    # Generate optimization recommendations
    improvement_areas = []
    recommendations = []

    # Check specificity
    if current_metrics["avg_specificity"] < 0.7:
        improvement_areas.append("specificity")
        recommendations.append("Add more specific evaluation criteria and concrete examples")

    # Check actionability
    if current_metrics["avg_actionability"] < 0.7:
        improvement_areas.append("actionability")
        recommendations.append("Include implementation steps and priority levels in prompt")

    # Check prompt length efficiency
    if current_metrics["avg_prompt_length"] > 2000:
        improvement_areas.append("conciseness")
        recommendations.append("Reduce prompt length while maintaining key information")

    # Domain-specific optimizations
    if expert_domain and expert_domain in EXPERT_REGISTRY:
        expert = EXPERT_REGISTRY[expert_domain]
        domain_template = expert.get_template()

        # Compare with domain expert template
        domain_results = test_prompt(domain_template, sample_queries)
        domain_metrics = _aggregate_test_metrics(domain_results)

        if domain_metrics["avg_response_quality"] > current_metrics["avg_response_quality"]:
            recommendations.append(f"Consider adopting {expert_domain} expert patterns for domain knowledge")

    # Generate optimized prompt (simplified approach)
    optimized_prompt = _apply_optimization_recommendations(base_prompt, recommendations, improvement_areas)

    # Calculate confidence in optimization
    confidence = min(0.9, len(recommendations) * 0.2 + 0.1)  # Simple heuristic

    return PromptOptimizationReport(
        original_prompt=base_prompt.system_prompt[:300] + "...",
        optimized_prompt=optimized_prompt.system_prompt[:300] + "...",
        improvement_areas=improvement_areas,
        performance_metrics=current_metrics,
        recommendations=recommendations,
        confidence_in_optimization=confidence,
    )


def validate_prompt(
    prompt_template: PromptTemplate, validation_criteria: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Validate a prompt template against quality criteria.

    Args:
        prompt_template: The prompt template to validate
        validation_criteria: Custom validation criteria

    Returns:
        Validation report with pass/fail status and recommendations
    """
    validation_criteria = validation_criteria or {
        "min_system_prompt_length": 100,
        "max_system_prompt_length": 3000,
        "requires_confidence_guidance": True,
        "requires_evaluation_criteria": True,
        "requires_json_format": True,
    }

    validation_results = {"is_valid": True, "issues": [], "warnings": [], "recommendations": [], "scores": {}}

    system_prompt = prompt_template.system_prompt
    # user_template = prompt_template.user_prompt_template  # Unused variable

    # Length validation
    if len(system_prompt) < validation_criteria.get("min_system_prompt_length", 100):
        validation_results["issues"].append("System prompt too short - may lack necessary context")
        validation_results["is_valid"] = False

    if len(system_prompt) > validation_criteria.get("max_system_prompt_length", 3000):
        validation_results["warnings"].append("System prompt very long - consider reducing for efficiency")

    # Content validation
    if validation_criteria.get("requires_confidence_guidance", True) and "confidence" not in system_prompt.lower():
        validation_results["issues"].append("Missing confidence guidance in system prompt")
        validation_results["is_valid"] = False

    if validation_criteria.get("requires_evaluation_criteria", True) and not prompt_template.evaluation_criteria:
        validation_results["warnings"].append("No evaluation criteria specified")

    if validation_criteria.get("requires_json_format", True) and "json" not in system_prompt.lower():
        validation_results["issues"].append("Missing JSON format specification")
        validation_results["is_valid"] = False

    # Quality scores
    validation_results["scores"] = {
        "clarity_score": _calculate_clarity_score(system_prompt),
        "completeness_score": _calculate_completeness_score(prompt_template),
        "specificity_score": _calculate_specificity_score(system_prompt),
    }

    # Generate recommendations
    if validation_results["scores"]["clarity_score"] < 0.7:
        validation_results["recommendations"].append("Improve prompt clarity with more structured language")

    if validation_results["scores"]["completeness_score"] < 0.8:
        validation_results["recommendations"].append("Add missing prompt components (criteria, calibration)")

    return validation_results


def _evaluate_prompt_quality(system_prompt: str, user_prompt: str, query: str) -> dict[str, float]:
    """Evaluate prompt quality using heuristic analysis."""
    scores = {}

    # Overall prompt quality (simplified heuristic)
    total_length = len(system_prompt) + len(user_prompt)
    has_structure = any(keyword in system_prompt.lower() for keyword in ["criteria", "framework", "evaluate"])
    has_guidance = "confidence" in system_prompt.lower() and "json" in system_prompt.lower()

    scores["overall"] = min(
        1.0,
        (0.5 if has_structure else 0.0)
        + (0.3 if has_guidance else 0.0)
        + (0.2 if 500 <= total_length <= 2000 else 0.1),
    )

    # Confidence guidance score
    scores["confidence_guidance"] = 1.0 if "confidence" in system_prompt.lower() else 0.3

    # Actionability score (looks for action words and implementation guidance)
    action_words = ["implement", "recommend", "improve", "fix", "optimize", "specific"]
    action_count = sum(1 for word in action_words if word in system_prompt.lower())
    scores["actionability"] = min(1.0, action_count * 0.2)

    # Specificity score (looks for specific criteria and examples)
    specific_words = ["specific", "criteria", "standard", "guideline", "example", "measure"]
    specific_count = sum(1 for word in specific_words if word in system_prompt.lower())
    scores["specificity"] = min(1.0, specific_count * 0.15)

    return scores


def _aggregate_test_metrics(results: list[PromptTestResult]) -> dict[str, float]:
    """Aggregate metrics from test results."""
    if not results:
        return {}

    return {
        "avg_response_quality": sum(r.response_quality for r in results) / len(results),
        "avg_confidence": sum(r.confidence_score for r in results) / len(results),
        "avg_actionability": sum(r.actionability_score for r in results) / len(results),
        "avg_specificity": sum(r.specificity_score for r in results) / len(results),
        "avg_response_time": sum(r.response_time for r in results) / len(results),
        "avg_prompt_length": sum(r.metadata.get("prompt_length", 0) for r in results) / len(results),
    }


def _apply_optimization_recommendations(
    base_prompt: PromptTemplate, recommendations: list[str], improvement_areas: list[str]
) -> PromptTemplate:
    """Apply optimization recommendations to create improved prompt."""
    # Simplified optimization - in practice this would be more sophisticated
    optimized_system = base_prompt.system_prompt

    if "specificity" in improvement_areas:
        optimized_system += "\n\nProvide specific, measurable recommendations with concrete examples."

    if "actionability" in improvement_areas:
        optimized_system += "\n\nInclude implementation steps and priority levels for each recommendation."

    return PromptTemplate(
        name=f"{base_prompt.name}_optimized",
        description=f"{base_prompt.description} (optimized)",
        system_prompt=optimized_system,
        user_prompt_template=base_prompt.user_prompt_template,
        variables=base_prompt.variables,
        evaluation_criteria=base_prompt.evaluation_criteria,
        confidence_calibration=base_prompt.confidence_calibration,
    )


def _calculate_clarity_score(system_prompt: str) -> float:
    """Calculate clarity score for a system prompt."""
    # Simple heuristic based on structure and clarity indicators
    clarity_indicators = ["clear", "specific", "structured", "framework", "criteria"]
    indicator_count = sum(1 for indicator in clarity_indicators if indicator in system_prompt.lower())
    return min(1.0, indicator_count * 0.2)


def _calculate_completeness_score(prompt_template: PromptTemplate) -> float:
    """Calculate completeness score for a prompt template."""
    components = [
        bool(prompt_template.system_prompt),
        bool(prompt_template.user_prompt_template),
        bool(prompt_template.evaluation_criteria),
        bool(prompt_template.confidence_calibration),
        "json" in prompt_template.system_prompt.lower(),
    ]
    return sum(components) / len(components)


def _calculate_specificity_score(system_prompt: str) -> float:
    """Calculate specificity score for a system prompt."""
    specific_elements = ["criteria", "standard", "guideline", "example", "specific", "measure", "evaluate"]
    element_count = sum(1 for element in specific_elements if element in system_prompt.lower())
    return min(1.0, element_count * 0.12)


# Convenience functions for common operations


def quick_accessibility_test(test_queries: list[str]) -> list[PromptTestResult]:
    """Quick test of accessibility expert prompts."""
    expert = AccessibilityExpert()
    template = expert.get_template()
    return test_prompt(template, test_queries)


def quick_conversion_test(test_queries: list[str]) -> list[PromptTestResult]:
    """Quick test of conversion expert prompts."""
    expert = ConversionExpert()
    template = expert.get_template()
    return test_prompt(template, test_queries)


def compare_expert_prompts(
    test_queries: list[str], expert_names: list[str] = None
) -> dict[str, list[PromptTestResult]]:
    """Compare performance of different expert prompts on the same queries."""
    expert_names = expert_names or list(EXPERT_REGISTRY.keys())
    results = {}

    for expert_name in expert_names:
        if expert_name in EXPERT_REGISTRY:
            expert = EXPERT_REGISTRY[expert_name]
            template = expert.get_template()
            results[expert_name] = test_prompt(template, test_queries)

    return results
