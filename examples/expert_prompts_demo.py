"""
Expert Prompt System Demonstration

This example showcases LayoutLens's enhanced prompt engineering system with
domain expert personas and rich instruction capabilities.
"""

import asyncio
import os

from layoutlens import LayoutLens
from layoutlens.prompts import Instructions, UserContext


async def basic_expert_usage():
    """Demonstrate basic expert persona usage."""
    print("🎯 Basic Expert Persona Usage")
    print("-" * 40)

    lens = LayoutLens()

    # Use accessibility expert for WCAG compliance
    result = await lens.audit_accessibility(
        source="https://example.com", compliance_level="AA", standards=["WCAG_2.1", "Section_508"]
    )

    print(f"Accessibility Audit: {result.answer[:200]}...")
    print(f"Confidence: {result.confidence:.1%}")
    print()

    # Use conversion expert for CRO analysis
    result = await lens.optimize_conversions(
        source="https://example.com",
        business_goals=["increase_signups", "reduce_bounce_rate"],
        industry="saas",
        target_audience="developers",
    )

    print(f"Conversion Optimization: {result.answer[:200]}...")
    print(f"Confidence: {result.confidence:.1%}")
    print()


async def rich_context_usage():
    """Demonstrate rich context and instruction capabilities."""
    print("🔧 Rich Context & Instructions")
    print("-" * 40)

    lens = LayoutLens()

    # Create rich user context for targeted analysis
    user_context = UserContext(
        target_audience="senior_citizens",
        device_usage="mobile_primary",
        business_goals=["improve_accessibility", "reduce_support_calls"],
        accessibility_needs=["large_text", "high_contrast", "simple_navigation"],
        technical_constraints=["slow_internet", "older_devices"],
    )

    # Use comprehensive instructions
    instructions = Instructions(
        expert_persona="accessibility_expert",
        focus_areas=["cognitive_load", "visual_clarity", "navigation_simplicity"],
        evaluation_criteria="Optimize for users 65+ with limited tech experience",
        user_context=user_context,
        output_style="actionable_recommendations",
        depth_level="comprehensive",
    )

    result = await lens.analyze(
        source="https://healthcare.gov",
        query="How can we make this easier for elderly users to navigate?",
        instructions=instructions,
    )

    print(f"Senior-Focused Analysis: {result.answer[:300]}...")
    print(f"Confidence: {result.confidence:.1%}")
    print()


async def domain_specific_workflows():
    """Demonstrate domain-specific analysis workflows."""
    print("🏥 Domain-Specific Workflows")
    print("-" * 40)

    lens = LayoutLens()

    # E-commerce product page audit
    ecommerce_result = await lens.audit_ecommerce(
        source="https://stripe.com/pricing", page_type="product_page", business_model="b2b"
    )

    print(f"E-commerce Audit: {ecommerce_result.answer[:200]}...")
    print(f"Confidence: {ecommerce_result.confidence:.1%}")
    print()

    # Mobile UX analysis
    mobile_result = await lens.analyze_mobile_ux(
        source="https://example.com", device_types=["smartphone"], performance_focus=True
    )

    print(f"Mobile UX Analysis: {mobile_result.answer[:200]}...")
    print(f"Confidence: {mobile_result.confidence:.1%}")
    print()


async def custom_expert_analysis():
    """Demonstrate flexible expert persona usage."""
    print("⚡ Custom Expert Analysis")
    print("-" * 40)

    lens = LayoutLens()

    # Use specific expert with custom focus
    result = await lens.analyze_with_expert(
        source="https://github.com",
        query="How can we optimize this for developer productivity?",
        expert_persona="conversion_expert",
        focus_areas=["developer_workflow", "tool_integration", "documentation_access"],
        user_context={
            "target_audience": "software_developers",
            "technical_constraints": ["time_pressure", "context_switching"],
            "business_goals": ["increase_tool_adoption", "improve_developer_experience"],
        },
    )

    print(f"Developer Experience Analysis: {result.answer[:300]}...")
    print(f"Confidence: {result.confidence:.1%}")
    print()


async def expert_comparison():
    """Demonstrate expert-based comparison analysis."""
    print("🔄 Expert-Based Comparison")
    print("-" * 40)

    lens = LayoutLens()

    # Compare designs using conversion expert knowledge
    result = await lens.compare_with_expert(
        sources=["https://tailwindcss.com", "https://getbootstrap.com"],
        query="Which framework site better converts developers to try the tool?",
        expert_persona="conversion_expert",
        focus_areas=["developer_onboarding", "clear_value_proposition", "getting_started_flow"],
    )

    print(f"Framework Comparison: {result.answer[:300]}...")
    print(f"Confidence: {result.confidence:.1%}")
    print()


async def structured_json_output():
    """Demonstrate structured JSON output with expert analysis."""
    print("📊 Structured JSON Output")
    print("-" * 40)

    lens = LayoutLens()

    # Get expert analysis with structured output
    instructions = Instructions.for_accessibility_audit(compliance_level="AA")
    instructions.output_style = "checklist_format"

    result = await lens.analyze(
        source="https://example.com", query="Provide a WCAG AA compliance checklist", instructions=instructions
    )

    # Export to clean JSON
    json_output = result.to_json()
    print("JSON Output Structure:")
    print(f"  Answer: {result.answer[:100]}...")
    print(f"  Confidence: {result.confidence}")
    print(f"  Reasoning: {result.reasoning[:100]}...")
    print(f"  JSON Length: {len(json_output)} characters")
    print()


async def prompt_testing_demo():
    """Demonstrate prompt testing and optimization."""
    print("🧪 Prompt Testing & Optimization")
    print("-" * 40)

    from layoutlens.prompts import compare_expert_prompts, get_expert, list_available_experts, test_prompt

    # List available experts
    experts = list_available_experts()
    print(f"Available experts: {', '.join(experts)}")
    print()

    # Test accessibility expert prompts
    test_queries = [
        "Is this page accessible for screen readers?",
        "Does this design meet WCAG AA standards?",
        "Are the color contrasts sufficient?",
    ]

    accessibility_expert = get_expert("accessibility_expert")
    template = accessibility_expert.get_template()

    # Run prompt tests (this is synchronous prompt evaluation)
    try:
        test_results = test_prompt(template, test_queries[:1])  # Just test one to avoid complexity
        print(f"Prompt test results: {len(test_results)} tests completed")
        if test_results:
            result = test_results[0]
            print(f"  Quality Score: {result.response_quality:.2f}")
            print(f"  Specificity: {result.specificity_score:.2f}")
            print(f"  Actionability: {result.actionability_score:.2f}")
    except Exception as e:
        print(f"Prompt testing demo skipped: {e}")

    print()


async def advanced_instruction_patterns():
    """Demonstrate advanced instruction patterns and customization."""
    print("🚀 Advanced Instruction Patterns")
    print("-" * 40)

    lens = LayoutLens()

    # Multi-expert perspective analysis
    print("Multi-Expert Analysis:")

    # Get accessibility perspective
    accessibility_instructions = Instructions.for_accessibility_audit()
    accessibility_result = await lens.analyze(
        source="https://example.com",
        query="What are the main accessibility issues?",
        instructions=accessibility_instructions,
    )
    print(f"  Accessibility Expert: {accessibility_result.answer[:150]}...")

    # Get conversion perspective
    conversion_instructions = Instructions.for_conversion_optimization()
    conversion_result = await lens.analyze(
        source="https://example.com", query="What are the main conversion issues?", instructions=conversion_instructions
    )
    print(f"  Conversion Expert: {conversion_result.answer[:150]}...")

    # Merge perspectives with custom instructions
    merged_instructions = conversion_instructions.merge_with_context(
        {
            "focus_areas": ["accessibility_impact_on_conversion"],
            "custom_instructions": "Consider how accessibility improvements affect conversion rates",
        }
    )

    merged_result = await lens.analyze(
        source="https://example.com",
        query="How do accessibility and conversion optimization intersect?",
        instructions=merged_instructions,
    )
    print(f"  Combined Perspective: {merged_result.answer[:150]}...")
    print()


async def main():
    """Run all expert prompt demonstrations."""
    print("LayoutLens Expert Prompt System Demo")
    print("=" * 50)

    # Check API key
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  OPENAI_API_KEY not set. Please set your API key to run examples.")
        print("   export OPENAI_API_KEY='your-key-here'")
        return

    print("🤖 Demonstrating expert-powered UI analysis with LayoutLens")
    print()

    try:
        # Run demonstrations
        await basic_expert_usage()
        await rich_context_usage()
        await domain_specific_workflows()
        await custom_expert_analysis()
        await expert_comparison()
        await structured_json_output()
        await prompt_testing_demo()
        await advanced_instruction_patterns()

    except Exception as e:
        print(f"❌ Demo failed: {e}")
        print("Note: Some examples require network access and may fail in test environments")

    print("✅ Expert prompt system demonstration completed!")
    print()
    print("🎯 Key Benefits:")
    print("  • Domain expert knowledge built into prompts")
    print("  • Rich context and instruction capabilities")
    print("  • Specialized analysis workflows")
    print("  • Structured JSON output with type safety")
    print("  • Prompt testing and optimization tools")
    print("  • Flexible expert persona system")


if __name__ == "__main__":
    asyncio.run(main())
