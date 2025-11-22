"""Async command-line interface for LayoutLens framework.

This module provides high-performance async CLI commands for the LayoutLens UI testing system.
"""

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Optional, cast

from .api.core import LayoutLens
from .api.test_suite import UITestCase, UITestResult, UITestSuite
from .config import Config, create_default_config


async def cmd_test_async(args) -> None:
    """Execute test command with async processing."""
    # Initialize LayoutLens
    try:
        tester = LayoutLens(
            api_key=args.api_key,
            model=getattr(args, "model", "gpt-4o-mini"),
            provider=getattr(args, "provider", "openrouter"),
            output_dir=args.output,
        )
    except Exception as e:
        print(f"Error initializing LayoutLens: {e}")
        sys.exit(1)

    if args.page:
        # Test single page with async processing
        queries = args.queries.split(",") if args.queries else ["Is this page well-designed and user-friendly?"]
        viewports = args.viewports.split(",") if args.viewports else ["desktop"]

        print(f"Analyzing page: {args.page}")
        print(f"Queries: {len(queries)}, Viewports: {len(viewports)}")
        print("Using async processing for better performance...")

        try:
            start_time = time.time()

            # Use async batch processing for multiple queries/viewports
            all_results = []
            for viewport in viewports:
                print(f"Processing viewport: {viewport}")

                # Process all queries for this viewport concurrently
                batch_result = await tester.analyze_batch_async(
                    sources=[args.page],
                    queries=queries,
                    viewport=viewport,
                    max_concurrent=getattr(args, "max_concurrent", 3),
                )

                all_results.extend(batch_result.results)

            # Display results
            for i, result in enumerate(all_results):
                viewport_idx = i // len(queries)
                _ = i % len(queries)
                viewport = viewports[viewport_idx] if viewport_idx < len(viewports) else "desktop"

                print(f"\nViewport: {viewport}")
                print(f"Query: {result.query}")
                print(f"Answer: {result.answer}")
                print(f"Confidence: {result.confidence:.1%}")
                print("-" * 50)

            # Performance summary
            total_time = time.time() - start_time
            avg_confidence = sum(r.confidence for r in all_results) / len(all_results)
            print(f"\nAnalysis complete in {total_time:.2f}s")
            print(f"Average confidence: {avg_confidence:.1%}")
            print(f"Processed {len(all_results)} analyses concurrently")

        except Exception as e:
            print(f"Analysis failed: {e}")
            sys.exit(1)

    elif args.suite:
        # Load and run test suite with async processing
        try:
            suite = UITestSuite.load(Path(args.suite))
            print(f"Running test suite: {suite.name}")
            print(f"Description: {suite.description}")
            print(f"Test cases: {len(suite.test_cases)}")
            print("Using async processing for better performance...")
            print("-" * 50)

            start_time = time.time()

            # Run the test suite with async processing
            results = cast(list[UITestResult], await run_test_suite_async(tester, suite, args))

            # Display results
            total_tests = 0
            total_passed = 0
            total_time = time.time() - start_time

            for ui_test_result in results:
                # Type check for safety
                if not isinstance(ui_test_result, UITestResult):
                    print(f"Warning: Expected UITestResult, got {type(ui_test_result)}")
                    continue

                print(f"\nTest Case: {ui_test_result.test_case_name}")
                print(f"  Tests: {ui_test_result.total_tests}")
                print(f"  Passed: {ui_test_result.passed_tests}")
                print(f"  Failed: {ui_test_result.failed_tests}")
                print(f"  Success Rate: {ui_test_result.success_rate:.1%}")
                print(f"  Duration: {ui_test_result.duration_seconds:.2f}s")

                total_tests += ui_test_result.total_tests
                total_passed += ui_test_result.passed_tests

            # Overall summary
            overall_rate = total_passed / total_tests if total_tests > 0 else 0
            print("\n" + "=" * 50)
            print(f"Overall Results:")
            print(f"  Total Tests: {total_tests}")
            print(f"  Total Passed: {total_passed}")
            print(f"  Success Rate: {overall_rate:.1%}")
            print(f"  Total Duration: {total_time:.2f}s")
            print(f"  Avg per Test: {total_time / total_tests:.2f}s")

            # Exit with error if below threshold
            if overall_rate < 0.8:  # 80% threshold
                sys.exit(1)

        except FileNotFoundError:
            print(f"Error: Test suite file not found: {args.suite}")
            sys.exit(1)
        except Exception as e:
            print(f"Error running test suite: {e}")
            sys.exit(1)
    else:
        print("Error: Either --page or --suite must be specified")
        sys.exit(1)


async def cmd_compare_async(args) -> None:
    """Execute compare command with async processing."""
    try:
        tester = LayoutLens(api_key=args.api_key, output_dir=args.output)
    except Exception as e:
        print(f"Error initializing LayoutLens: {e}")
        sys.exit(1)

    print(f"Comparing: {args.page_a} vs {args.page_b}")
    print("Using async processing for better performance...")

    try:
        start_time = time.time()

        # Use async batch processing for comparison
        batch_result = await tester.analyze_batch_async(
            sources=[args.page_a, args.page_b], queries=[args.query], max_concurrent=2
        )

        # Process comparison results
        if len(batch_result.results) >= 2:
            result_a = batch_result.results[0]
            result_b = batch_result.results[1]

            print(f"\nPage A Analysis:")
            print(f"  Answer: {result_a.answer}")
            print(f"  Confidence: {result_a.confidence:.1%}")

            print(f"\nPage B Analysis:")
            print(f"  Answer: {result_b.answer}")
            print(f"  Confidence: {result_b.confidence:.1%}")

            # Simple comparison logic
            if result_a.confidence > result_b.confidence:
                winner = args.page_a
                confidence_diff = result_a.confidence - result_b.confidence
            elif result_b.confidence > result_a.confidence:
                winner = args.page_b
                confidence_diff = result_b.confidence - result_a.confidence
            else:
                winner = "tie"
                confidence_diff = 0.0

            print(f"\nComparison Summary:")
            if winner != "tie":
                print(f"  Better page: {winner}")
                print(f"  Confidence difference: {confidence_diff:.1%}")
            else:
                print(f"  Result: Tie")

            total_time = time.time() - start_time
            print(f"  Completed in: {total_time:.2f}s")

        else:
            print("Error: Not enough results for comparison")
            sys.exit(1)

    except Exception as e:
        print(f"Comparison failed: {e}")
        sys.exit(1)


async def cmd_batch_async(args) -> None:
    """Execute batch command for processing multiple sources."""
    try:
        tester = LayoutLens(api_key=args.api_key, output_dir=args.output)
    except Exception as e:
        print(f"Error initializing LayoutLens: {e}")
        sys.exit(1)

    # Parse sources and queries
    sources = []
    if args.sources:
        sources = args.sources.split(",")
    elif args.sources_file:
        with open(args.sources_file) as f:
            sources = [line.strip() for line in f if line.strip()]
    else:
        print("Error: Either --sources or --sources-file must be specified")
        sys.exit(1)

    queries = args.queries.split(",") if args.queries else ["Is this UI well-designed?"]

    print(f"Batch processing:")
    print(f"  Sources: {len(sources)}")
    print(f"  Queries: {len(queries)}")
    print(f"  Total analyses: {len(sources) * len(queries)}")
    print(f"  Max concurrent: {getattr(args, 'max_concurrent', 5)}")
    print("Starting async batch processing...")

    try:
        start_time = time.time()

        # Run batch analysis with async processing
        batch_result = await tester.analyze_batch_async(
            sources=sources,
            queries=queries,
            viewport=getattr(args, "viewport", "desktop"),
            max_concurrent=getattr(args, "max_concurrent", 5),
        )

        # Display results
        print(f"\nBatch Analysis Results:")
        print("=" * 60)

        for i, result in enumerate(batch_result.results):
            source_idx = i // len(queries)
            _ = i % len(queries)
            source = sources[source_idx]

            print(f"\nSource: {source}")
            print(f"Query: {result.query}")
            print(f"Answer: {result.answer}")
            print(f"Confidence: {result.confidence:.1%}")
            if result.confidence == 0.0:
                print(f"Error: {result.metadata.get('error', 'Unknown error')}")
            print("-" * 40)

        # Summary
        total_time = time.time() - start_time
        successful = batch_result.successful_queries
        total = batch_result.total_queries

        print(f"\nBatch Processing Summary:")
        print(f"  Total Analyses: {total}")
        print(f"  Successful: {successful}")
        print(f"  Failed: {total - successful}")
        print(f"  Success Rate: {successful / total:.1%}")
        print(f"  Average Confidence: {batch_result.average_confidence:.1%}")
        print(f"  Total Time: {total_time:.2f}s")
        print(f"  Avg per Analysis: {total_time / total:.2f}s")
        print(f"  Performance Gain: ~{len(sources) * len(queries) / total_time:.1f}x")

    except Exception as e:
        print(f"Batch processing failed: {e}")
        sys.exit(1)


async def run_test_suite_async(tester: LayoutLens, suite: UITestSuite, args) -> list[UITestResult]:
    """Run test suite with async processing."""
    results = []

    for test_case in suite.test_cases:
        print(f"Running test case: {test_case.name}")
        case_start_time = time.time()

        try:
            # Run all queries for this test case concurrently
            batch_result = await tester.analyze_batch_async(
                sources=[test_case.html_path],
                queries=test_case.queries,
                max_concurrent=getattr(args, "max_concurrent", 3),
            )

            # Process results
            passed = sum(1 for r in batch_result.results if r.confidence >= test_case.expected_confidence)
            failed = len(batch_result.results) - passed

            case_duration = time.time() - case_start_time

            result = UITestResult(
                suite_name=suite.name,
                test_case_name=test_case.name,
                total_tests=len(test_case.queries),
                passed_tests=passed,
                failed_tests=failed,
                results=batch_result.results,
                duration_seconds=case_duration,
                metadata={
                    "async_processing": True,
                    "batch_results": batch_result.results,
                },
            )

            results.append(result)

        except Exception as e:
            # Create failed result
            case_duration = time.time() - case_start_time
            result = UITestResult(
                suite_name=suite.name,
                test_case_name=test_case.name,
                total_tests=len(test_case.queries),
                passed_tests=0,
                failed_tests=len(test_case.queries),
                results=[],  # Empty results for failed case
                duration_seconds=case_duration,
                metadata={"error": str(e), "async_processing": True},
            )
            results.append(result)
            print(f"Test case failed: {e}")

    return results


def add_async_args(parser: argparse.ArgumentParser) -> None:
    """Add async-specific arguments to parser."""
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=5,
        help="Maximum number of concurrent analyses (default: 5)",
    )
    parser.add_argument(
        "--async",
        action="store_true",
        help="Use async processing for better performance",
    )


def create_async_cli() -> argparse.ArgumentParser:
    """Create the async CLI parser."""
    parser = argparse.ArgumentParser(
        description="LayoutLens Async CLI - High-performance UI testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Async single page analysis
  layoutlens-async test --page https://example.com --queries "Is it accessible?,Is it mobile-friendly?" --max-concurrent 3

  # Async batch processing
  layoutlens-async batch --sources "page1.html,page2.html,page3.html" --queries "Good design?,User friendly?" --max-concurrent 5

  # Async test suite
  layoutlens-async test --suite my_suite.yaml --max-concurrent 4
        """,
    )

    parser.add_argument(
        "--api-key",
        default=os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY"),
        help="API key (or set OPENAI_API_KEY/OPENROUTER_API_KEY env var)",
    )
    parser.add_argument(
        "--provider",
        choices=["openrouter", "openai", "anthropic", "google", "gemini"],
        default="openrouter",
        help="AI provider to use (default: openrouter)",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="Model to use for analysis (default: gpt-4o-mini)",
    )
    parser.add_argument(
        "--output",
        default="layoutlens_output",
        help="Output directory (default: layoutlens_output)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Test command
    test_parser = subparsers.add_parser("test", help="Analyze pages or run test suites")
    test_parser.add_argument("--page", help="Single page to analyze")
    test_parser.add_argument("--suite", help="Test suite file to run")
    test_parser.add_argument("--queries", help="Comma-separated queries")
    test_parser.add_argument("--viewports", help="Comma-separated viewports")
    add_async_args(test_parser)

    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare two pages")
    compare_parser.add_argument("page_a", help="First page to compare")
    compare_parser.add_argument("page_b", help="Second page to compare")
    compare_parser.add_argument("--query", default="Which design is better?", help="Comparison query")
    add_async_args(compare_parser)

    # Batch command
    batch_parser = subparsers.add_parser("batch", help="Process multiple sources")
    batch_parser.add_argument("--sources", help="Comma-separated list of sources")
    batch_parser.add_argument("--sources-file", help="File containing list of sources")
    batch_parser.add_argument("--queries", help="Comma-separated queries")
    batch_parser.add_argument("--viewport", default="desktop", help="Viewport for analysis")
    add_async_args(batch_parser)

    return parser


async def main_async():
    """Main async CLI entry point."""
    parser = create_async_cli()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Route to appropriate async command
    if args.command == "test":
        await cmd_test_async(args)
    elif args.command == "compare":
        await cmd_compare_async(args)
    elif args.command == "batch":
        await cmd_batch_async(args)
    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)


def main():
    """Entry point for async CLI."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
