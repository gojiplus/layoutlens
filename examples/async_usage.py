"""Example demonstrating async LayoutLens functionality for improved performance."""

import asyncio
import time

from layoutlens import LayoutLens


async def async_single_analysis():
    """Demonstrate async single page analysis."""
    print("=== Async Single Page Analysis ===")

    lens = LayoutLens()  # Uses OPENAI_API_KEY env var

    try:
        result = await lens.analyze(
            source="https://example.com",
            query="Is this page accessible and user-friendly?",
            viewport="desktop",
        )

        print("Analysis Result:")
        print(f"  Answer: {result.answer}")
        print(f"  Confidence: {result.confidence:.1%}")
        print(f"  Source: {result.source}")

    except Exception as e:
        print(f"Analysis failed: {e}")


async def async_batch_analysis():
    """Demonstrate async batch processing for better performance."""
    print("\n=== Async Batch Analysis ===")

    lens = LayoutLens()

    # Multiple pages to analyze
    sources = [
        "https://example.com",
        "https://httpbin.org/html",
        "https://httpstat.us/200",
    ]

    # Multiple queries per page
    queries = [
        "Is this page well-designed?",
        "Is the navigation clear?",
        "Are the colors accessible?",
    ]

    print(f"Analyzing {len(sources)} pages with {len(queries)} queries each")
    print(f"Total analyses: {len(sources) * len(queries)}")
    print("Using async processing with max 3 concurrent requests...")

    try:
        start_time = time.time()

        # Use async batch processing
        result = await lens.analyze(
            sources=sources,
            queries=queries,
            viewport="desktop",
            max_concurrent=3,  # Limit concurrent API calls
        )

        async_time = time.time() - start_time

        print("\nBatch Results:")
        print(f"  Total Queries: {result.total_queries}")
        print(f"  Successful: {result.successful_queries}")
        print(f"  Failed: {result.total_queries - result.successful_queries}")
        print(f"  Average Confidence: {result.average_confidence:.1%}")
        print(f"  Total Time: {async_time:.2f}s")
        print(f"  Avg per Analysis: {async_time / result.total_queries:.2f}s")

        # Show individual results
        print("\nIndividual Results:")
        for i, analysis_result in enumerate(result.results):
            source_idx = i // len(queries)
            query_idx = i % len(queries)
            print(f"  {sources[source_idx]} - {queries[query_idx]}")
            print(f"    Answer: {analysis_result.answer[:100]}...")
            print(f"    Confidence: {analysis_result.confidence:.1%}")

    except Exception as e:
        print(f"Batch analysis failed: {e}")


async def compare_sync_vs_async():
    """Compare sync vs async performance."""
    print("\n=== Sync vs Async Performance Comparison ===")

    lens = LayoutLens()

    sources = ["https://example.com", "https://httpbin.org/html"]
    queries = ["Is this well-designed?", "Is it accessible?"]

    try:
        # Simulate synchronous batch processing (sequential calls)
        print("Testing sequential processing...")
        start_time = time.time()
        for source in sources:
            for query in queries:
                await lens.analyze(source=source, query=query)
        sync_time = time.time() - start_time

        # Time asynchronous batch processing
        print("Testing asynchronous batch processing...")
        start_time = time.time()
        await lens.analyze(sources=sources, queries=queries, max_concurrent=2)
        async_time = time.time() - start_time

        print("\nPerformance Comparison:")
        print(f"  Synchronous Time: {sync_time:.2f}s")
        print(f"  Asynchronous Time: {async_time:.2f}s")
        print(f"  Performance Improvement: {sync_time / async_time:.1f}x faster")
        print(f"  Time Saved: {sync_time - async_time:.2f}s ({(sync_time - async_time) / sync_time:.1%})")

    except Exception as e:
        print(f"Performance comparison failed: {e}")


async def async_test_suite_simulation():
    """Simulate running a test suite with async processing."""
    print("\n=== Async Test Suite Simulation ===")

    lens = LayoutLens()

    # Simulate a test suite with multiple test cases
    test_cases = [
        {
            "name": "Homepage Tests",
            "source": "https://example.com",
            "queries": [
                "Is the logo prominently displayed?",
                "Is the navigation intuitive?",
                "Are call-to-action buttons visible?",
            ],
        },
        {
            "name": "Contact Page Tests",
            "source": "https://httpbin.org/html",
            "queries": [
                "Is the contact form easy to find?",
                "Are form fields clearly labeled?",
                "Is there a clear submit button?",
            ],
        },
    ]

    print(f"Running test suite with {len(test_cases)} test cases")

    try:
        overall_start = time.time()
        all_results = []

        for test_case in test_cases:
            print(f"\nRunning: {test_case['name']}")

            start_time = time.time()
            result = await lens.analyze(
                sources=[test_case["source"]],
                queries=test_case["queries"],
                max_concurrent=3,
            )
            test_time = time.time() - start_time

            all_results.extend(result.results)

            passed = sum(1 for r in result.results if r.confidence >= 0.7)
            total = len(result.results)

            print(f"  Completed in {test_time:.2f}s")
            print(f"  Passed: {passed}/{total} ({passed / total:.1%})")

        overall_time = time.time() - overall_start
        total_analyses = len(all_results)
        overall_passed = sum(1 for r in all_results if r.confidence >= 0.7)

        print("\nTest Suite Summary:")
        print(f"  Total Analyses: {total_analyses}")
        print(f"  Overall Passed: {overall_passed}/{total_analyses} ({overall_passed / total_analyses:.1%})")
        print(f"  Total Time: {overall_time:.2f}s")
        print(f"  Avg per Analysis: {overall_time / total_analyses:.2f}s")

    except Exception as e:
        print(f"Test suite failed: {e}")


async def main():
    """Run all async examples."""
    print("LayoutLens Async Functionality Examples")
    print("=" * 50)

    # Check for API key
    import os

    if not os.getenv("OPENAI_API_KEY"):
        print("Warning: OPENAI_API_KEY not set. Examples will fail.")
        print("Set your API key: export OPENAI_API_KEY='your-key-here'")
        return

    # Run examples
    await async_single_analysis()
    await async_batch_analysis()
    await compare_sync_vs_async()
    await async_test_suite_simulation()

    print("\n" + "=" * 50)
    print("Async examples completed!")
    print("\nKey Benefits of Async Processing:")
    print("• Concurrent API calls for faster batch processing")
    print("• Better resource utilization")
    print("• Scalable to larger test suites")
    print("• Configurable concurrency limits")


if __name__ == "__main__":
    asyncio.run(main())
