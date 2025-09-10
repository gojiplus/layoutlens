"""Basic usage examples for LayoutLens framework."""

import os
from layoutlens import LayoutLens

# Example 1: Basic page testing
def basic_page_test():
    """Test a single HTML page with custom queries."""
    
    # Initialize LayoutLens
    tester = LayoutLens()
    
    # Test a page with custom queries using real benchmark file
    result = tester.test_page(
        html_path="benchmarks/test_data/layout_alignment/nav_centered.html",
        queries=[
            "Is the navigation menu properly centered?",
            "Does the layout look professional?", 
            "Are the navigation links evenly spaced?"
        ],
        viewports=["desktop", "mobile_portrait"]
    )
    
    if result:
        print(f"Test completed: {result.success_rate:.2%} success rate")
        print(f"Passed: {result.passed_tests}/{result.total_tests} tests")
    else:
        print("Test failed")


# Example 2: Page comparison
def compare_pages_example():
    """Compare two versions of a page."""
    
    tester = LayoutLens()
    
    # Compare two real benchmark pages
    result = tester.compare_pages(
        page_a_path="benchmarks/test_data/layout_alignment/nav_centered.html",
        page_b_path="benchmarks/test_data/layout_alignment/nav_misaligned.html", 
        query="Are the layouts visually consistent?"
    )
    
    if result:
        print("Comparison result:", result['answer'])
    else:
        print("Comparison failed")


# Example 3: Automated query generation
def auto_query_test():
    """Test with automatically generated queries."""
    
    tester = LayoutLens()
    
    # Let LayoutLens analyze the page and generate appropriate queries
    result = tester.test_page(
        html_path="benchmarks/test_data/ui_components/form_well_designed.html",
        auto_generate_queries=True,  # This is the default
        viewports=["desktop"]
    )
    
    if result:
        print("Auto-generated test results:")
        print(f"Total tests: {result.total_tests}")
        print(f"Success rate: {result.success_rate:.2%}")


# Example 4: Test suite execution
def test_suite_example():
    """Run a complete test suite."""
    
    tester = LayoutLens()
    
    # Create a simple test suite
    test_suite = tester.create_test_suite(
        name="Homepage Test Suite",
        description="Comprehensive homepage testing",
        test_cases=[
            {
                "name": "Desktop Navigation",
                "html_path": "benchmarks/test_data/layout_alignment/nav_centered.html",
                "queries": [
                    "Is the navigation properly centered?",
                    "Does the layout look professional?",
                    "Are navigation elements well-spaced?"
                ],
                "viewports": ["desktop"]
            },
            {
                "name": "Mobile Form",
                "html_path": "benchmarks/test_data/ui_components/form_well_designed.html", 
                "queries": [
                    "Is the form mobile-friendly?",
                    "Are touch targets appropriately sized?",
                    "Is the content readable on mobile?"
                ],
                "viewports": ["mobile_portrait"]
            }
        ]
    )
    
    # Run the test suite
    results = tester.run_test_suite(test_suite)
    
    print(f"Test suite completed: {len(results)} test cases")
    overall_success = sum(r.success_rate for r in results) / len(results)
    print(f"Overall success rate: {overall_success:.2%}")


if __name__ == "__main__":
    print("LayoutLens Basic Usage Examples")
    print("=" * 40)
    
    # Make sure to set your OpenAI API key
    import os
    if not os.getenv('OPENAI_API_KEY'):
        print("Please set OPENAI_API_KEY environment variable")
        exit(1)
    
    print("\n1. Basic page testing...")
    try:
        basic_page_test()
    except Exception as e:
        print(f"Example 1 failed: {e}")
    
    print("\n2. Page comparison...")
    try:
        compare_pages_example()
    except Exception as e:
        print(f"Example 2 failed: {e}")
    
    print("\n3. Auto-generated queries...")
    try:
        auto_query_test()
    except Exception as e:
        print(f"Example 3 failed: {e}")
    
    print("\n4. Test suite execution...")
    try:
        test_suite_example()
    except Exception as e:
        print(f"Example 4 failed: {e}")