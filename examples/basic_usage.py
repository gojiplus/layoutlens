"""Basic usage examples for LayoutLens framework."""

from layoutlens import LayoutLens

# Example 1: Basic page testing
def basic_page_test():
    """Test a single HTML page with custom queries."""
    
    # Initialize LayoutLens
    tester = LayoutLens()
    
    # Test a page with custom queries
    result = tester.test_page(
        html_path="examples/sample_page.html",
        queries=[
            "Is the navigation menu visible?",
            "Is the logo properly positioned?",
            "Are the buttons clearly visible?"
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
    
    # Compare before and after versions
    result = tester.compare_pages(
        page_a_path="examples/before.html",
        page_b_path="examples/after.html",
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
        html_path="examples/sample_page.html",
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
                "name": "Desktop Homepage",
                "html_path": "examples/homepage.html",
                "queries": [
                    "Is the header navigation clearly visible?",
                    "Is the hero section prominent?",
                    "Are the call-to-action buttons visible?"
                ],
                "viewports": ["desktop"]
            },
            {
                "name": "Mobile Homepage",
                "html_path": "examples/homepage.html",
                "queries": [
                    "Is the mobile menu accessible?",
                    "Is the content readable on mobile?",
                    "Are touch targets appropriately sized?"
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