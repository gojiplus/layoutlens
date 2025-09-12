"""Advanced usage examples for LayoutLens framework.

This module demonstrates advanced features and patterns for
comprehensive UI testing scenarios.
"""

import os
import time
from pathlib import Path
from layoutlens import LayoutLens


def advanced_analysis_with_context():
    """Demonstrate analysis with detailed context information."""
    
    # Initialize with custom model and output directory
    tester = LayoutLens(
        model="gpt-4o",  # Use more powerful model
        output_dir="advanced_analysis_output"
    )
    
    # Analyze with rich context
    context = {
        "user_type": "senior_citizens",
        "browser": "chrome",
        "purpose": "accessibility_audit",
        "business_context": "healthcare_website"
    }
    
    result = tester.analyze(
        source="https://example.com",
        query="Is this website accessible for elderly users with limited tech experience?",
        viewport="desktop",
        context=context
    )
    
    print(f"Advanced analysis result: {result.answer}")
    print(f"Confidence: {result.confidence:.1%}")
    print(f"Context-aware reasoning: {result.reasoning[:300]}...")


def comprehensive_comparison_workflow():
    """Demonstrate advanced comparison scenarios."""
    
    tester = LayoutLens(output_dir="comparison_analysis")
    
    # Before/after comparison with specific focus
    before_after_context = {
        "focus_areas": "navigation, accessibility, mobile_experience",
        "comparison_type": "redesign_evaluation"
    }
    
    result = tester.compare(
        sources=[
            "benchmarks/test_data/layout_alignment/nav_misaligned.html",
            "benchmarks/test_data/layout_alignment/nav_centered.html"
        ],
        query="How does the redesigned navigation improve the user experience?",
        context=before_after_context
    )
    
    print(f"\nDesign comparison: {result.answer}")
    print(f"Analysis confidence: {result.confidence:.1%}")


def batch_analysis_workflow():
    """Demonstrate efficient batch processing of multiple pages."""
    
    tester = LayoutLens(output_dir="batch_analysis")
    
    # Define pages to analyze
    pages = [
        "benchmarks/test_data/layout_alignment/nav_centered.html",
        "benchmarks/test_data/accessibility/good_contrast.html",
        "benchmarks/test_data/responsive_design/mobile_optimized.html"
    ]
    
    # Run batch analysis
    results = tester.analyze_batch(
        sources=pages,
        query="Does this page follow modern web design best practices?",
        context={"evaluation_focus": "ux_principles"}
    )
    
    print(f"\nBatch analysis completed for {len(results)} pages:")
    for i, result in enumerate(results):
        page_name = Path(pages[i]).stem
        print(f"  {page_name}: {result.answer[:100]}... (confidence: {result.confidence:.1%})")


def specialized_checks_workflow():
    """Demonstrate specialized built-in checks."""
    
    tester = LayoutLens(output_dir="specialized_checks")
    
    # Comprehensive accessibility audit
    print("\n=== Accessibility Analysis ===")
    accessibility_result = tester.check_accessibility(
        source="benchmarks/test_data/accessibility/good_contrast.html"
    )
    print(f"Accessibility: {accessibility_result.answer}")
    print(f"Confidence: {accessibility_result.confidence:.1%}")
    
    # Mobile experience evaluation
    print("\n=== Mobile-Friendly Analysis ===")
    mobile_result = tester.check_mobile_friendly(
        source="benchmarks/test_data/responsive_design/mobile_optimized.html"
    )
    print(f"Mobile-friendly: {mobile_result.answer}")
    print(f"Confidence: {mobile_result.confidence:.1%}")
    
    # Conversion optimization check
    print("\n=== Conversion Optimization Analysis ===")
    conversion_result = tester.check_conversion_optimization(
        source="https://example.com"
    )
    print(f"Conversion optimization: {conversion_result.answer}")
    print(f"Confidence: {conversion_result.confidence:.1%}")


def multi_viewport_analysis():
    """Demonstrate analysis across different viewports."""
    
    tester = LayoutLens(output_dir="viewport_analysis")
    
    viewports = ["desktop", "mobile_portrait", "tablet_landscape"]
    source_page = "https://example.com"
    
    print(f"\n=== Multi-Viewport Analysis ===")
    for viewport in viewports:
        print(f"\nAnalyzing {viewport} viewport...")
        
        result = tester.analyze(
            source=source_page,
            query="How well does the layout adapt to this screen size?",
            viewport=viewport,
            context={"viewport_focus": viewport}
        )
        
        print(f"{viewport.title()}: {result.answer[:150]}...")
        print(f"Confidence: {result.confidence:.1%}")


def performance_optimized_workflow():
    """Demonstrate performance considerations for large-scale testing."""
    
    # Initialize with performance settings
    tester = LayoutLens(
        model="gpt-4o-mini",  # Faster, cost-effective model
        output_dir="performance_testing"
    )
    
    # Process multiple pages efficiently
    test_pages = [
        "benchmarks/test_data/layout_alignment/nav_centered.html",
        "benchmarks/test_data/ui_components/form_well_designed.html"
    ]
    
    # Use batch processing for efficiency
    start_time = time.time()
    
    results = tester.analyze_batch(
        sources=test_pages,
        query="Rate the overall design quality on a scale of 1-10 and explain why."
    )
    
    elapsed_time = time.time() - start_time
    
    print(f"\n=== Performance Analysis ===")
    print(f"Processed {len(test_pages)} pages in {elapsed_time:.2f} seconds")
    print(f"Average time per page: {elapsed_time/len(test_pages):.2f} seconds")
    
    for i, result in enumerate(results):
        print(f"Page {i+1}: {result.answer[:100]}...")


def error_handling_patterns():
    """Demonstrate robust error handling patterns."""
    
    tester = LayoutLens()
    
    print("\n=== Error Handling Examples ===")
    
    # Handle invalid URLs gracefully
    try:
        result = tester.analyze(
            source="https://nonexistent-website-12345.com",
            query="Is this page accessible?"
        )
        print(f"Result: {result.answer}")
    except Exception as e:
        print(f"Handled URL error: {type(e).__name__}")
    
    # Handle missing files gracefully
    try:
        result = tester.analyze(
            source="nonexistent_file.html",
            query="How is the layout?"
        )
        print(f"Result: {result.answer}")
    except Exception as e:
        print(f"Handled file error: {type(e).__name__}")
    
    # Handle API errors gracefully
    try:
        # This would fail with invalid API key
        invalid_tester = LayoutLens(api_key="invalid_key")
        result = invalid_tester.analyze("https://example.com", "Test query")
    except ValueError as e:
        print(f"Handled API key error: {e}")


def main():
    """Run all advanced examples."""
    
    print("LayoutLens Advanced Usage Examples")
    print("=" * 50)
    
    # Check API key
    if not os.getenv('OPENAI_API_KEY'):
        print("Please set OPENAI_API_KEY environment variable")
        print("Example: export OPENAI_API_KEY='sk-your-key-here'")
        return
    
    examples = [
        ("Advanced Analysis with Context", advanced_analysis_with_context),
        ("Comprehensive Comparison", comprehensive_comparison_workflow),
        ("Batch Analysis", batch_analysis_workflow),
        ("Specialized Checks", specialized_checks_workflow),
        ("Multi-Viewport Analysis", multi_viewport_analysis),
        ("Performance Optimized", performance_optimized_workflow),
        ("Error Handling", error_handling_patterns)
    ]
    
    for i, (name, func) in enumerate(examples, 1):
        print(f"\n{i}. {name}")
        print("-" * 40)
        try:
            func()
        except Exception as e:
            print(f"Example failed: {e}")
            print("Note: Some examples require network access or specific files")


if __name__ == "__main__":
    main()