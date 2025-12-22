#!/usr/bin/env python3
"""
Simple LayoutLens API Usage Examples

This file demonstrates the simplified LayoutLens API for
common UI testing scenarios.
"""

import asyncio
import os

from layoutlens import LayoutLens


async def basic_url_analysis():
    """Basic URL analysis example."""
    print("🔍 Basic URL Analysis")
    print("-" * 40)

    try:
        # Initialize LayoutLens
        lens = LayoutLens(api_key=os.getenv("OPENAI_API_KEY"))

        # Analyze a URL
        result = await lens.analyze(
            source="https://example.com",
            query="Is the page layout clean and professional?",
        )

        print(f"Answer: {result.answer[:100]}...")
        print(f"Confidence: {result.confidence:.1%}")

    except Exception as e:
        print(f"Error: {e}")
    print()


async def mobile_analysis():
    """Mobile-specific analysis example."""
    print("📱 Mobile Analysis")
    print("-" * 40)

    try:
        lens = LayoutLens(api_key=os.getenv("OPENAI_API_KEY"))

        # Check mobile usability
        result = await lens.check_mobile_friendly("https://example.com")

        print(f"Mobile Analysis: {result.answer[:100]}...")
        print(f"Confidence: {result.confidence:.1%}")

    except Exception as e:
        print(f"Error: {e}")
    print()


async def accessibility_check():
    """Accessibility analysis example."""
    print("♿ Accessibility Check")
    print("-" * 40)

    try:
        lens = LayoutLens(api_key=os.getenv("OPENAI_API_KEY"))

        # Check accessibility
        result = await lens.check_accessibility("https://example.com")

        print(f"Accessibility Analysis: {result.answer[:100]}...")
        print(f"Confidence: {result.confidence:.1%}")

    except Exception as e:
        print(f"Error: {e}")
    print()


async def before_after_comparison():
    """Before/after comparison example."""
    print("🔄 Before/After Comparison")
    print("-" * 40)

    try:
        lens = LayoutLens(api_key=os.getenv("OPENAI_API_KEY"))

        # Compare two designs
        result = await lens.compare(
            sources=["https://example.com", "https://httpbin.org"],
            query="Which page has a cleaner, more professional design?",
        )

        print(f"Comparison: {result.answer[:100]}...")
        print(f"Confidence: {result.confidence:.1%}")

    except Exception as e:
        print(f"Error: {e}")
    print()


async def batch_analysis():
    """Batch analysis example."""
    print("📊 Batch Analysis")
    print("-" * 40)

    try:
        lens = LayoutLens()

        # Analyze multiple pages with a single query
        sources = ["https://github.com", "https://docs.github.com"]

        queries = ["Is the navigation clear and user-friendly?"]

        results = await lens.analyze(sources=sources, queries=queries)

        print(f"Analyzed {len(sources)} sources with {len(queries)} queries")
        for i, result in enumerate(results.results):
            print(f"Source {i + 1}: {result.answer[:80]}... (confidence: {result.confidence:.1%})")

    except Exception as e:
        print(f"Error: {e}")
    print()


async def viewport_analysis():
    """Different viewport analysis."""
    print("📱💻 Viewport Analysis")
    print("-" * 40)

    try:
        lens = LayoutLens()

        viewports = ["desktop", "mobile_portrait"]

        for viewport in viewports:
            result = await lens.analyze(
                source="https://example.com",
                query=f"How well does this page work on {viewport}?",
                viewport=viewport,
            )
            print(f"{viewport.capitalize()}: {result.answer[:60]}... ({result.confidence:.1%})")

    except Exception as e:
        print(f"Error: {e}")
    print()


def screenshot_analysis():
    """Analyze local screenshot files."""
    print("🖼️ Screenshot Analysis")
    print("-" * 40)

    # Example with local files (would work if files exist)
    print("Example usage:")
    print("lens.analyze('screenshot.png', 'Is this layout accessible?')")
    print("lens.analyze('mobile_screenshot.png', 'Are touch targets large enough?')")
    print()


async def conversion_optimization():
    """Conversion-focused analysis."""
    print("💰 Conversion Optimization")
    print("-" * 40)

    try:
        lens = LayoutLens()

        # Check for conversion optimization
        result = await lens.check_conversion_optimization("https://stripe.com")

        print(f"Conversion Analysis: {result.answer[:100]}...")
        print(f"Confidence: {result.confidence:.1%}")

    except Exception as e:
        print(f"Error: {e}")
    print()


async def context_aware_analysis():
    """Analysis with context information."""
    print("🎯 Context-Aware Analysis")
    print("-" * 40)

    try:
        lens = LayoutLens()

        # Provide context for more targeted analysis
        context = {"user_type": "elderly_users", "purpose": "accessibility_audit"}

        result = await lens.analyze(
            source="https://example.com",
            query="Is this website suitable for elderly users?",
            context=context,
        )

        print(f"Context-aware analysis: {result.answer[:100]}...")
        print(f"Confidence: {result.confidence:.1%}")

    except Exception as e:
        print(f"Error: {e}")
    print()


async def main():
    """Run all examples."""
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️ Please set OPENAI_API_KEY environment variable")
        print("Example: export OPENAI_API_KEY='sk-your-key-here'")
        return

    examples = [
        basic_url_analysis,
        mobile_analysis,
        accessibility_check,
        before_after_comparison,
        batch_analysis,
        viewport_analysis,
        screenshot_analysis,
        conversion_optimization,
        context_aware_analysis,
    ]

    print("🚀 LayoutLens Simple API Examples")
    print("=" * 50)
    print()

    for example in examples:
        try:
            if example.__name__ == "screenshot_analysis":
                example()  # This one is sync - just shows examples
            else:
                await example()
        except Exception as e:
            print(f"❌ Error in {example.__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
