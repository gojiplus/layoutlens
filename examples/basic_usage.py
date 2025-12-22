"""Basic usage examples for LayoutLens framework."""

import asyncio
import os

from layoutlens import LayoutLens


# Example 1: Basic page analysis
async def basic_page_analysis():
    """Analyze a single HTML page with a natural language query."""

    # Initialize LayoutLens
    tester = LayoutLens()

    # Analyze a page with a custom query
    result = await tester.analyze(
        source="benchmarks/test_data/layout_alignment/nav_centered.html",
        query="Is the navigation menu properly centered and professional-looking?",
    )

    print(f"Analysis result: {result.answer}")
    print(f"Confidence: {result.confidence:.1%}")
    print(f"Reasoning: {result.reasoning[:200]}...")


# Example 2: Website analysis
async def website_analysis():
    """Analyze a live website."""

    tester = LayoutLens()

    # Analyze a live website (replace with actual URL)
    result = await tester.analyze(
        source="https://example.com",
        query="Is this homepage user-friendly and accessible?",
        viewport="desktop",
    )

    print(f"Website analysis: {result.answer}")
    print(f"Confidence: {result.confidence:.1%}")


# Example 3: Compare two designs
async def compare_designs():
    """Compare two versions of a page."""

    tester = LayoutLens()

    # Compare two different layouts
    result = await tester.compare(
        sources=[
            "benchmarks/test_data/layout_alignment/nav_centered.html",
            "benchmarks/test_data/layout_alignment/nav_misaligned.html",
        ],
        query="Which layout has better navigation alignment?",
    )

    print(f"Comparison result: {result.answer}")
    print(f"Confidence: {result.confidence:.1%}")


# Example 4: Batch analysis
async def batch_analysis():
    """Analyze multiple pages at once."""

    tester = LayoutLens()

    # Analyze multiple pages with the same query
    pages = [
        "benchmarks/test_data/layout_alignment/nav_centered.html",
        "benchmarks/test_data/ui_components/form_well_designed.html",
    ]

    results = await tester.analyze(sources=pages, query="Is this page well-designed and user-friendly?")

    for i, result in enumerate(results.results):
        print(f"Page {i + 1}: {result.answer} (confidence: {result.confidence:.1%})")


# Example 5: Built-in accessibility check
async def accessibility_check():
    """Check accessibility compliance."""

    tester = LayoutLens()

    # Check accessibility of a page
    result = await tester.check_accessibility(source="benchmarks/test_data/accessibility/good_contrast.html")

    print(f"Accessibility assessment: {result.answer}")
    print(f"Confidence: {result.confidence:.1%}")


# Example 6: Mobile-friendly check
async def mobile_check():
    """Check mobile-friendliness."""

    tester = LayoutLens()

    # Check if page is mobile-friendly
    result = await tester.check_mobile_friendly(source="benchmarks/test_data/responsive_design/mobile_optimized.html")

    print(f"Mobile-friendly assessment: {result.answer}")
    print(f"Confidence: {result.confidence:.1%}")


async def run_all_examples():
    """Run all examples asynchronously."""
    print("LayoutLens Basic Usage Examples")
    print("=" * 40)

    # Make sure to set your OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Please set OPENAI_API_KEY environment variable")
        print("Example: export OPENAI_API_KEY='sk-your-key-here'")
        exit(1)

    examples = [
        ("Basic page analysis", basic_page_analysis),
        ("Website analysis", website_analysis),
        ("Compare designs", compare_designs),
        ("Batch analysis", batch_analysis),
        ("Accessibility check", accessibility_check),
        ("Mobile-friendly check", mobile_check),
    ]

    for i, (name, func) in enumerate(examples, 1):
        print(f"\n{i}. {name}...")
        try:
            await func()
        except Exception as e:
            print(f"Example failed: {e}")
            print("Note: Some examples require benchmark files to exist")


if __name__ == "__main__":
    asyncio.run(run_all_examples())
