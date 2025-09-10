"""Advanced usage examples for LayoutLens framework.

This module demonstrates advanced features and patterns for
comprehensive UI testing scenarios.
"""

import os
import time
from layoutlens import LayoutLens, Config
from layoutlens.config import ViewportConfig


def custom_configuration_example():
    """Demonstrate custom configuration setup."""
    
    # Create custom configuration
    config = Config()
    
    # Customize LLM settings
    config.llm.model = "gpt-4o"  # Use more powerful model
    config.llm.temperature = 0.05  # More deterministic responses
    
    # Customize screenshot settings
    config.screenshot.format = "jpeg"
    config.screenshot.quality = 95
    config.screenshot.full_page = False  # Viewport only
    config.screenshot.animations = "allow"
    
    # Enable parallel execution
    config.test.parallel_execution = True
    config.test.max_workers = 6
    config.test.focus_areas = ["layout", "accessibility"]  # Focus on specific areas
    
    # Add custom viewport
    ultrawide_viewport = ViewportConfig(
        name="ultrawide",
        width=3440,
        height=1440,
        device_scale_factor=1.0,
        is_mobile=False,
        has_touch=False
    )
    config.viewports.append(ultrawide_viewport)
    
    # Note: Custom query libraries can be handled in test logic
    # as the current API doesn't have add_custom_queries method
    print("Custom viewport added: ultrawide (3440x1440)")
    
    # Configuration can be saved manually to YAML
    print("Configuration customized successfully")
    
    # Use the custom configuration
    tester = LayoutLens(config=config)
    print("Custom configuration loaded successfully")


def multi_page_testing_workflow():
    """Demonstrate testing multiple related pages."""
    
    tester = LayoutLens()
    
    # Define a comprehensive test workflow
    pages_to_test = [
        {
            "path": "examples/homepage.html",
            "queries": [
                "Is the hero section compelling and visible?",
                "Are the main navigation links clear?",
                "Is the call-to-action prominent?"
            ],
            "viewports": ["desktop", "mobile_portrait", "tablet_portrait"]
        },
        {
            "path": "examples/product_listing.html", 
            "queries": [
                "Are products displayed in a clear grid?",
                "Are product images consistent in size?",
                "Is the filtering interface intuitive?"
            ],
            "viewports": ["desktop", "tablet_landscape"]
        },
        {
            "path": "examples/product_detail.html",
            "queries": [
                "Is the product image gallery functional?",
                "Is the product information well organized?",
                "Is the 'Add to Cart' button prominent?"
            ],
            "viewports": ["desktop", "mobile_portrait"]
        },
        {
            "path": "examples/checkout.html",
            "queries": [
                "Is the checkout form clearly laid out?",
                "Are form validation messages visible?",
                "Is the payment section secure-looking?"
            ],
            "viewports": ["desktop", "tablet_portrait"]
        }
    ]
    
    # Test each page and collect results
    all_results = []
    for page_config in pages_to_test:
        print(f"\nTesting: {page_config['path']}")
        
        result = tester.test_page(
            html_path=page_config["path"],
            queries=page_config["queries"],
            viewports=page_config["viewports"]
        )
        
        if result:
            all_results.append(result)
            print(f"  Success rate: {result.success_rate:.2%}")
        
    # Calculate overall metrics
    if all_results:
        overall_tests = sum(r.total_tests for r in all_results)
        overall_passed = sum(r.passed_tests for r in all_results)
        overall_rate = overall_passed / overall_tests
        
        print(f"\nOverall Results:")
        print(f"  Total tests: {overall_tests}")
        print(f"  Overall success rate: {overall_rate:.2%}")
        
        # Identify problematic pages
        poor_performers = [r for r in all_results if r.success_rate < 0.7]
        if poor_performers:
            print(f"  Pages needing attention: {len(poor_performers)}")
            for result in poor_performers:
                print(f"    - {result.html_path}: {result.success_rate:.2%}")


def accessibility_focused_testing():
    """Demonstrate accessibility-focused testing approach."""
    
    # Configure for accessibility testing
    config = Config()
    config.test.focus_areas = ["accessibility"]
    config.test.auto_generate_queries = True
    
    # Add accessibility-specific queries
    config.add_custom_queries("accessibility", [
        "Are all images provided with appropriate alt text?",
        "Is the color contrast sufficient for readability?",
        "Are form fields properly labeled and associated?",
        "Is the focus indicator visible and clear?",
        "Are headings used in a logical hierarchy?",
        "Is the page usable with keyboard navigation only?",
        "Are ARIA landmarks properly implemented?",
        "Is text resizable without loss of functionality?"
    ])
    
    tester = LayoutLens(config=config)
    
    # Test a form-heavy page for accessibility
    result = tester.test_page(
        html_path="examples/contact_form.html",
        viewports=["desktop"],
        auto_generate_queries=True
    )
    
    if result:
        print("Accessibility Test Results:")
        print(f"  Total tests: {result.total_tests}")
        print(f"  Accessibility score: {result.success_rate:.2%}")
        
        # Analyze specific accessibility issues
        accessibility_tests = [tr for tr in result.test_results 
                             if tr.category in ["accessibility", "semantic_markup"]]
        
        if accessibility_tests:
            failed_a11y = [tr for tr in accessibility_tests 
                          if "no" in tr.answer.lower() or "not" in tr.answer.lower()]
            
            if failed_a11y:
                print(f"  Accessibility issues found: {len(failed_a11y)}")
                for test in failed_a11y[:3]:  # Show first 3 issues
                    print(f"    - {test.query}: {test.answer}")


def responsive_design_validation():
    """Demonstrate comprehensive responsive design testing."""
    
    # Define comprehensive viewport set
    responsive_viewports = [
        "mobile_portrait",   # 375x667
        "mobile_landscape",  # 667x375
        "tablet_portrait",   # 768x1024  
        "tablet_landscape",  # 1024x768
        "desktop",          # 1440x900
        "desktop_large",    # 1920x1080
        "desktop_xl"        # 2560x1440
    ]
    
    tester = LayoutLens()
    
    # Responsive-specific queries
    responsive_queries = [
        "Does the layout adapt appropriately to this screen size?",
        "Are all interactive elements accessible and appropriately sized?",
        "Is the content readable without horizontal scrolling?",
        "Are images and media properly scaled for this viewport?",
        "Is the navigation appropriate for this device type?",
        "Are touch targets at least 44px for mobile devices?",
        "Is the text size appropriate for this screen resolution?"
    ]
    
    print("Running comprehensive responsive design validation...")
    
    result = tester.test_page(
        html_path="examples/responsive_page.html",
        queries=responsive_queries,
        viewports=responsive_viewports
    )
    
    if result:
        # Analyze results by viewport
        viewport_results = {}
        for test_result in result.test_results:
            viewport = test_result.viewport
            if viewport not in viewport_results:
                viewport_results[viewport] = {"passed": 0, "total": 0}
            
            viewport_results[viewport]["total"] += 1
            if "yes" in test_result.answer.lower():
                viewport_results[viewport]["passed"] += 1
        
        print("\nResponsive Design Results by Viewport:")
        for viewport, stats in viewport_results.items():
            rate = stats["passed"] / stats["total"] if stats["total"] > 0 else 0
            print(f"  {viewport}: {rate:.2%} ({stats['passed']}/{stats['total']})")
        
        # Identify viewport-specific issues
        problematic_viewports = {vp: stats for vp, stats in viewport_results.items() 
                               if (stats["passed"] / stats["total"]) < 0.8}
        
        if problematic_viewports:
            print(f"\nViewports needing attention: {len(problematic_viewports)}")
            for viewport in problematic_viewports:
                print(f"  - {viewport}")


def performance_oriented_testing():
    """Demonstrate performance-aware visual testing."""
    
    # Configure for performance testing
    config = Config()
    config.screenshot.wait_timeout = 10000  # Shorter timeout
    config.screenshot.animations = "disabled"  # No animations for consistency
    config.test.parallel_execution = True  # Faster execution
    
    # Performance-focused queries
    performance_queries = [
        "Do images appear to load quickly and crisply?",
        "Are there any visible layout shifts or reflows?",
        "Do animations and transitions appear smooth?",
        "Are loading states handled appropriately?",
        "Does the page appear to render progressively?",
        "Are there any visual artifacts or rendering issues?"
    ]
    
    tester = LayoutLens(config=config)
    
    # Test multiple pages quickly
    pages = [
        "examples/homepage.html",
        "examples/product_page.html", 
        "examples/search_results.html"
    ]
    
    print("Running performance-oriented visual tests...")
    
    for page in pages:
        print(f"\nTesting: {page}")
        start_time = time.time()
        
        result = tester.test_page(
            html_path=page,
            queries=performance_queries,
            viewports=["desktop"],
            auto_generate_queries=False
        )
        
        duration = time.time() - start_time
        
        if result:
            print(f"  Test duration: {duration:.2f}s")
            print(f"  Visual performance score: {result.success_rate:.2%}")
            
            # Look for performance-related issues
            perf_issues = [tr for tr in result.test_results 
                          if "slow" in tr.answer.lower() or "shift" in tr.answer.lower()]
            
            if perf_issues:
                print(f"  Performance issues detected: {len(perf_issues)}")


def brand_consistency_testing():
    """Demonstrate brand guideline compliance testing."""
    
    # Brand-specific configuration
    brand_queries = [
        "Is the brand logo displayed prominently and correctly?",
        "Are the brand colors used consistently throughout?",
        "Is the typography consistent with brand guidelines?",
        "Are brand elements properly positioned and sized?",
        "Is the overall design consistent with the brand identity?",
        "Are brand-specific UI components used appropriately?"
    ]
    
    tester = LayoutLens()
    
    # Test multiple brand touchpoints
    brand_pages = [
        "examples/homepage.html",
        "examples/about.html",
        "examples/contact.html",
        "examples/product_page.html"
    ]
    
    print("Running brand consistency validation...")
    
    brand_results = []
    for page in brand_pages:
        result = tester.test_page(
            html_path=page,
            queries=brand_queries,
            viewports=["desktop"]
        )
        
        if result:
            brand_results.append({
                "page": page,
                "brand_score": result.success_rate,
                "total_tests": result.total_tests
            })
    
    # Analyze brand consistency across pages
    if brand_results:
        avg_brand_score = sum(r["brand_score"] for r in brand_results) / len(brand_results)
        
        print(f"\nBrand Consistency Results:")
        print(f"  Average brand score: {avg_brand_score:.2%}")
        
        # Identify inconsistent pages
        inconsistent = [r for r in brand_results if r["brand_score"] < avg_brand_score - 0.1]
        
        if inconsistent:
            print(f"  Pages with brand inconsistencies:")
            for result in inconsistent:
                print(f"    - {result['page']}: {result['brand_score']:.2%}")


if __name__ == "__main__":
    import time
    
    print("LayoutLens Advanced Usage Examples")
    print("=" * 50)
    
    # Make sure to set your OpenAI API key
    import os
    if not os.getenv('OPENAI_API_KEY'):
        print("Please set OPENAI_API_KEY environment variable")
        exit(1)
    
    examples = [
        ("Custom Configuration", custom_configuration_example),
        ("Multi-Page Testing", multi_page_testing_workflow),
        ("Accessibility Testing", accessibility_focused_testing),
        ("Responsive Design Validation", responsive_design_validation),
        ("Performance Testing", performance_oriented_testing),
        ("Brand Consistency", brand_consistency_testing)
    ]
    
    for name, func in examples:
        print(f"\n{name}:")
        print("-" * (len(name) + 1))
        try:
            func()
        except Exception as e:
            print(f"Example failed: {e}")
        print()  # Add spacing between examples