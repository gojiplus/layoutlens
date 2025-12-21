"""Unified CLI commands for LayoutLens framework.

This module provides all CLI command implementations with async-by-default execution
for optimal performance.
"""

import asyncio
import glob
import sys
import time
from pathlib import Path
from typing import Optional, cast

import yaml

from .api.core import LayoutLens
from .api.test_suite import UITestCase, UITestResult, UITestSuite
from .config import Config, create_default_config
from .logger import get_logger


async def cmd_test(args) -> None:
    """Execute test command with async processing.

    Processes either single page analysis or test suite execution based on provided arguments.
    Uses async batch processing for optimal performance when testing multiple queries or viewports.

    Args:
        args: Command line arguments containing:
            - page: URL or file path for single page testing
            - suite: Path to YAML test suite file
            - queries: Comma-separated test queries
            - viewports: Comma-separated viewport names
            - api_key: API key for AI provider
            - model: AI model to use
            - provider: AI provider name
            - output: Output directory path
            - max_concurrent: Maximum concurrent operations

    Raises:
        SystemExit: If initialization fails, analysis fails, or test suite not found.
    """
    logger = get_logger("cli.test")
    logger.debug(
        f"Starting test command with args: page={getattr(args, 'page', None)}, suite={getattr(args, 'suite', None)}"
    )

    # Initialize LayoutLens
    try:
        tester = LayoutLens(
            api_key=args.api_key,
            model=getattr(args, "model", "gpt-4o-mini"),
            provider=getattr(args, "provider", "openai"),
            output_dir=args.output,
        )
        logger.debug("LayoutLens initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize LayoutLens: {e}")
        print(f"Error initializing LayoutLens: {e}", file=sys.stderr)
        sys.exit(1)

    if args.page:
        # Test single page with async processing
        queries = args.queries.split(",") if args.queries else ["Is this page well-designed and user-friendly?"]
        viewports = args.viewports.split(",") if args.viewports else ["desktop"]

        logger.debug(f"Starting single page analysis: {args.page} with {len(queries)} queries")
        print(f"Analyzing page: {args.page}")
        print(f"Queries: {len(queries)}, Viewports: {len(viewports)}")

        try:
            start_time = time.time()
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
                viewport = viewports[viewport_idx] if viewport_idx < len(viewports) else "desktop"

                print(f"\nViewport: {viewport}")
                print(f"Query: {result.query}")
                print(f"Answer: {result.answer}")
                print(f"Confidence: {result.confidence:.1%}")
                print("-" * 50)

            # Performance summary
            total_time = time.time() - start_time
            avg_confidence = sum(r.confidence for r in all_results) / len(all_results)
            logger.debug(
                f"Single page analysis completed: {len(all_results)} queries, avg confidence: {avg_confidence:.2f}"
            )
            print(f"\nAnalysis complete in {total_time:.2f}s")
            print(f"Average confidence: {avg_confidence:.1%}")
            print(f"Processed {len(all_results)} analyses concurrently")

        except Exception as e:
            logger.error(f"Single page analysis failed: {e}")
            print(f"Analysis failed: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.suite:
        # Load and run test suite with async processing
        try:
            suite = UITestSuite.load(Path(args.suite))
            print(f"Running test suite: {suite.name}")
            print(f"Description: {suite.description}")
            print(f"Test cases: {len(suite.test_cases)}")
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
            print(f"Error: Test suite file not found: {args.suite}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error running test suite: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("Error: Either --page or --suite must be specified", file=sys.stderr)
        sys.exit(1)


async def cmd_compare(args) -> None:
    """Execute compare command with async processing.

    Compares two pages using AI analysis and provides a detailed comparison report
    including confidence scores and performance metrics.

    Args:
        args: Command line arguments containing:
            - page_a: First page URL or file path
            - page_b: Second page URL or file path
            - query: Comparison question (default: "Which page has a better layout design?")
            - api_key: API key for AI provider
            - model: AI model to use
            - provider: AI provider name
            - output: Output directory path

    Raises:
        SystemExit: If initialization fails or comparison fails.
    """
    logger = get_logger("cli.compare")
    logger.debug(f"Starting compare command: {args.page_a} vs {args.page_b}")

    try:
        tester = LayoutLens(
            api_key=args.api_key,
            model=getattr(args, "model", "gpt-4o-mini"),
            provider=getattr(args, "provider", "openai"),
            output_dir=args.output,
        )
        logger.debug("LayoutLens initialized for comparison")
    except Exception as e:
        logger.error(f"Failed to initialize LayoutLens for comparison: {e}")
        print(f"Error initializing LayoutLens: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Comparing: {args.page_a} vs {args.page_b}")

    try:
        start_time = time.time()
        logger.debug(f"Starting comparison: {args.page_a} vs {args.page_b}")

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
            logger.debug(f"Comparison completed with confidence: {result_a.confidence:.2f}, {result_b.confidence:.2f}")
            print(f"  Completed in: {total_time:.2f}s")

        else:
            print("Error: Not enough results for comparison", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        logger.error(f"Comparison failed: {e}")
        print(f"Comparison failed: {e}", file=sys.stderr)
        sys.exit(1)


async def cmd_batch(args) -> None:
    """Execute batch command for processing multiple sources.

    Processes multiple URLs or files with multiple queries using concurrent async processing
    for maximum efficiency. Sources can be provided as comma-separated list or via file.

    Args:
        args: Command line arguments containing:
            - sources: Comma-separated list of URLs or file paths
            - sources_file: File containing list of sources (one per line)
            - queries: Comma-separated list of test queries
            - viewport: Viewport size for analysis
            - api_key: API key for AI provider
            - model: AI model to use
            - provider: AI provider name
            - output: Output directory path
            - max_concurrent: Maximum concurrent operations

    Raises:
        SystemExit: If no sources provided, initialization fails, or batch processing fails.
    """
    try:
        tester = LayoutLens(
            api_key=args.api_key,
            model=getattr(args, "model", "gpt-4o-mini"),
            provider=getattr(args, "provider", "openai"),
            output_dir=args.output,
        )
    except Exception as e:
        print(f"Error initializing LayoutLens: {e}", file=sys.stderr)
        sys.exit(1)

    # Parse sources and queries
    sources = []
    if args.sources:
        sources = args.sources.split(",")
    elif args.sources_file:
        with open(args.sources_file) as f:
            sources = [line.strip() for line in f if line.strip()]
    else:
        print("Error: Either --sources or --sources-file must be specified", file=sys.stderr)
        sys.exit(1)

    queries = args.queries.split(",") if args.queries else ["Is this UI well-designed?"]

    print(f"Batch processing:")
    print(f"  Sources: {len(sources)}")
    print(f"  Queries: {len(queries)}")
    print(f"  Total analyses: {len(sources) * len(queries)}")
    print(f"  Max concurrent: {getattr(args, 'max_concurrent', 5)}")

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

    except Exception as e:
        print(f"Batch processing failed: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_generate(args) -> None:
    """Execute generate command to create configuration or test suite templates.

    Creates YAML files with sensible defaults for LayoutLens configuration or test suites.
    Output path can be a specific file or directory.

    Args:
        args: Command line arguments containing:
            - type: Type of file to generate ("config" or "suite")
            - output: Output file path or directory

    Raises:
        SystemExit: If unknown generation type is specified.
    """
    if args.type == "config":
        # Generate config file - use output as directory if it's a directory
        if hasattr(args, "output") and args.output and Path(args.output).is_dir():
            config_path = str(Path(args.output) / "layoutlens.yaml")
        elif hasattr(args, "output") and args.output:
            config_path = args.output
        else:
            config_path = "layoutlens.yaml"
        _ = create_default_config(config_path)
        print(f"Default configuration created: {config_path}")

    elif args.type == "suite":
        # Generate test suite template
        if hasattr(args, "output") and args.output and Path(args.output).is_dir():
            suite_path = str(Path(args.output) / "test_suite.yaml")
        elif hasattr(args, "output") and args.output:
            suite_path = args.output
        else:
            suite_path = "test_suite.yaml"

        # Ensure the directory exists
        Path(suite_path).parent.mkdir(parents=True, exist_ok=True)

        template = {
            "name": "Sample Test Suite",
            "description": "Template test suite for LayoutLens",
            "test_cases": [
                {
                    "name": "Homepage Test",
                    "html_path": "pages/homepage.html",
                    "queries": [
                        "Is the navigation menu visible?",
                        "Is the logo centered?",
                        "Is the layout responsive?",
                    ],
                    "viewports": ["mobile_portrait", "desktop"],
                    "expected_results": {},
                    "metadata": {"priority": "high"},
                }
            ],
            "metadata": {"version": "1.0"},
        }

        with open(suite_path, "w") as f:
            yaml.dump(template, f, default_flow_style=False, indent=2)

        print(f"Test suite template created: {suite_path}")

    else:
        print(f"Unknown generate type: {args.type}", file=sys.stderr)
        sys.exit(1)


def cmd_info(args) -> None:
    """Execute info command to display system information and configuration.

    Shows LayoutLens version, Python version, dependency status, available AI providers,
    API key configuration, and system health checks.

    Args:
        args: Command line arguments (unused for info command).
    """
    import sys

    from . import __version__

    print(f"LayoutLens v{__version__}")
    print(f"Python: {sys.version.split()[0]}")

    # Check dependencies
    try:
        import openai

        print(f"OpenAI SDK: {openai.__version__}")
    except ImportError:
        print("OpenAI SDK: Not installed")

    try:
        import playwright

        print("Playwright: Installed")
    except ImportError:
        print("Playwright: Not installed")

    # Show available providers and models
    print("\nAvailable Providers:")
    try:
        from .providers import get_provider_info

        provider_info = get_provider_info()

        for name, info in provider_info.items():
            print(f"  {name.title()}: {len(info.get('supported_models', []))} models")
            if "supported_models" in info:
                popular_models = info["supported_models"][:3]  # Show first 3
                print(f"    Popular models: {', '.join(popular_models)}")
    except Exception as e:
        print(f"  Error loading providers: {e}")

    # Check API keys
    import os

    print("\nAPI Keys:")

    openai_key = os.getenv("OPENAI_API_KEY")

    if openai_key:
        print("  OPENAI_API_KEY: Set")
    else:
        print("  OPENAI_API_KEY: Not set")
        print("  Note: Set OPENAI_API_KEY environment variable")

    # Test basic functionality
    try:
        from .api.core import LayoutLens

        _ = LayoutLens()
        print("✓ LayoutLens initialization: OK")
    except Exception as e:
        print(f"✗ LayoutLens initialization: Failed ({e})")


async def cmd_interactive(args) -> None:
    """Execute interactive mode for real-time UI analysis.

    Starts an interactive session where users can enter URLs and queries dynamically.
    Uses Rich library for enhanced terminal formatting when available.

    Args:
        args: Command line arguments containing:
            - api_key: API key for AI provider
            - model: AI model to use
            - provider: AI provider name
            - output: Output directory path

    Raises:
        SystemExit: If LayoutLens initialization fails.
    """
    from .cli_interactive import run_interactive_session

    try:
        lens = LayoutLens(
            api_key=args.api_key,
            model=getattr(args, "model", "gpt-4o-mini"),
            provider=getattr(args, "provider", "openai"),
            output_dir=args.output,
        )

        run_interactive_session(lens)

    except Exception as e:
        print(f"Error starting interactive session: {e}")
        sys.exit(1)


async def cmd_capture(args) -> None:
    """Execute capture command - Stage 1 of 2-stage pipeline.

    Captures screenshots from URLs without analysis for later processing.

    Args:
        args: Command line arguments containing:
            - url: Single URL to capture
            - urls: Comma-separated list of URLs
            - urls_file: File with URLs (one per line)
            - viewport: Viewport for capture
            - wait_for: CSS selector to wait for
            - wait_time: Additional wait time in milliseconds
            - api_key, model, provider, output: Standard LayoutLens args

    Raises:
        SystemExit: If initialization fails or capture fails.
    """
    logger = get_logger("cli.capture")
    logger.debug("Starting capture command")

    # Initialize LayoutLens
    try:
        lens = LayoutLens(
            api_key=args.api_key,
            model=getattr(args, "model", "gpt-4o-mini"),
            provider=getattr(args, "provider", "openai"),
            output_dir=args.output,
        )
        logger.debug("LayoutLens initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize LayoutLens: {e}")
        print(f"Error initializing LayoutLens: {e}", file=sys.stderr)
        sys.exit(1)

    # Collect URLs to capture
    urls = []
    if args.url:
        urls = [args.url]
    elif args.urls:
        urls = [url.strip() for url in args.urls.split(",")]
    elif args.urls_file:
        try:
            with open(args.urls_file) as f:
                urls = [line.strip() for line in f if line.strip()]
        except Exception as e:
            logger.error(f"Failed to read URLs file: {e}")
            print(f"Error reading URLs file: {e}", file=sys.stderr)
            sys.exit(1)

    if not urls:
        print("No URLs provided for capture", file=sys.stderr)
        sys.exit(1)

    print(f"Capturing screenshots from {len(urls)} URL(s)")
    print(f"Viewport: {args.viewport}")

    try:
        start_time = time.time()

        if len(urls) == 1:
            # Single URL capture using async method
            screenshot_path = await lens.capture_only_async(
                source=urls[0],
                viewport=args.viewport,
                wait_for_selector=getattr(args, "wait_for", None),
                wait_time=getattr(args, "wait_time", None),
            )
            print(f"Captured: {urls[0]} -> {Path(screenshot_path).name}")
        else:
            # Batch capture using async method
            results = await lens.capture_batch_async(
                sources=urls,
                viewport=args.viewport,
                wait_for_selector=getattr(args, "wait_for", None),
                wait_time=getattr(args, "wait_time", None),
                max_concurrent=getattr(args, "max_concurrent", 3),
            )

            # Display results
            successful = 0
            failed = 0
            for url, result in results.items():
                if result.startswith("Error:"):
                    print(f"FAILED: {url} - {result}")
                    failed += 1
                else:
                    print(f"Captured: {url} -> {Path(result).name}")
                    successful += 1

            execution_time = time.time() - start_time
            print(f"\nCapture Summary:")
            print(f"Successful: {successful}/{len(urls)}")
            print(f"Failed: {failed}/{len(urls)}")
            print(f"Total time: {execution_time:.2f}s")

            if failed > 0:
                sys.exit(1)

    except Exception as e:
        logger.error(f"Capture failed: {e}")
        print(f"Capture failed: {e}", file=sys.stderr)
        sys.exit(1)


async def cmd_analyze(args) -> None:
    """Execute analyze command - Stage 2 of 2-stage pipeline.

    Analyzes existing screenshots with natural language queries.

    Args:
        args: Command line arguments containing:
            - screenshot: Single screenshot to analyze
            - screenshots: Comma-separated list of screenshots
            - screenshots_dir: Directory containing screenshots
            - queries: Comma-separated analysis queries
            - viewport: Viewport that was used for capture
            - api_key, model, provider, output: Standard LayoutLens args

    Raises:
        SystemExit: If initialization fails or analysis fails.
    """
    logger = get_logger("cli.analyze")
    logger.debug("Starting analyze command")

    # Initialize LayoutLens
    try:
        lens = LayoutLens(
            api_key=args.api_key,
            model=getattr(args, "model", "gpt-4o-mini"),
            provider=getattr(args, "provider", "openai"),
            output_dir=args.output,
        )
        logger.debug("LayoutLens initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize LayoutLens: {e}")
        print(f"Error initializing LayoutLens: {e}", file=sys.stderr)
        sys.exit(1)

    # Collect screenshots to analyze
    screenshots = []
    if args.screenshot:
        screenshots = [args.screenshot]
    elif args.screenshots:
        screenshots = [path.strip() for path in args.screenshots.split(",")]
    elif args.screenshots_dir:
        screenshot_dir = Path(args.screenshots_dir)
        if not screenshot_dir.exists():
            print(f"Screenshots directory not found: {args.screenshots_dir}", file=sys.stderr)
            sys.exit(1)
        screenshots = [str(p) for p in screenshot_dir.glob("*.png")]

    if not screenshots:
        print("No screenshots provided for analysis", file=sys.stderr)
        sys.exit(1)

    # Parse queries
    queries = [q.strip() for q in args.queries.split(",")]

    print(f"Analyzing {len(screenshots)} screenshot(s) with {len(queries)} queries")
    print(f"Viewport: {args.viewport}")

    try:
        start_time = time.time()

        if len(screenshots) == 1 and len(queries) == 1:
            # Single screenshot, single query
            result = lens.analyze_screenshot(
                screenshot_path=screenshots[0],
                query=queries[0],
                viewport=args.viewport,
            )
            print(f"\nScreenshot: {Path(screenshots[0]).name}")
            print(f"Query: {result.query}")
            print(f"Answer: {result.answer}")
            print(f"Confidence: {result.confidence:.1%}")
        else:
            # Batch analysis
            screenshot_mapping = {Path(s).name: s for s in screenshots}
            results = lens.analyze_captured_batch(
                screenshot_mapping=screenshot_mapping,
                queries=queries,
                viewport=args.viewport,
            )

            # Display results
            successful_analyses = 0
            failed_analyses = 0

            for screenshot_name, analysis_results in results.items():
                print(f"\n{'-' * 60}")
                print(f"Screenshot: {screenshot_name}")

                for i, result in enumerate(analysis_results):
                    if result.confidence > 0:
                        successful_analyses += 1
                        print(f"\nQuery {i+1}: {result.query}")
                        print(f"Answer: {result.answer}")
                        print(f"Confidence: {result.confidence:.1%}")
                    else:
                        failed_analyses += 1
                        print(f"\nQuery {i+1}: {result.query}")
                        print(f"FAILED: {result.answer}")

            execution_time = time.time() - start_time
            total_analyses = len(screenshots) * len(queries)

            print(f"\n{'-' * 60}")
            print(f"Analysis Summary:")
            print(f"Successful: {successful_analyses}/{total_analyses}")
            print(f"Failed: {failed_analyses}/{total_analyses}")
            print(f"Total time: {execution_time:.2f}s")

            if failed_analyses > 0:
                sys.exit(1)

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        print(f"Analysis failed: {e}", file=sys.stderr)
        sys.exit(1)


async def cmd_pipeline(args) -> None:
    """Execute pipeline command - Complete 2-stage pipeline.

    Captures screenshots from URLs and then analyzes them with queries.

    Args:
        args: Command line arguments containing:
            - url: Single URL to process
            - urls: Comma-separated list of URLs
            - urls_file: File with URLs (one per line)
            - queries: Comma-separated analysis queries
            - viewport: Viewport for capture and analysis
            - wait_for: CSS selector to wait for
            - wait_time: Additional wait time in milliseconds
            - api_key, model, provider, output: Standard LayoutLens args

    Raises:
        SystemExit: If initialization fails or pipeline fails.
    """
    logger = get_logger("cli.pipeline")
    logger.debug("Starting pipeline command")

    # Initialize LayoutLens
    try:
        lens = LayoutLens(
            api_key=args.api_key,
            model=getattr(args, "model", "gpt-4o-mini"),
            provider=getattr(args, "provider", "openai"),
            output_dir=args.output,
        )
        logger.debug("LayoutLens initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize LayoutLens: {e}")
        print(f"Error initializing LayoutLens: {e}", file=sys.stderr)
        sys.exit(1)

    # Collect URLs to process
    urls = []
    if args.url:
        urls = [args.url]
    elif args.urls:
        urls = [url.strip() for url in args.urls.split(",")]
    elif args.urls_file:
        try:
            with open(args.urls_file) as f:
                urls = [line.strip() for line in f if line.strip()]
        except Exception as e:
            logger.error(f"Failed to read URLs file: {e}")
            print(f"Error reading URLs file: {e}", file=sys.stderr)
            sys.exit(1)

    if not urls:
        print("No URLs provided for pipeline processing", file=sys.stderr)
        sys.exit(1)

    # Parse queries
    queries = [q.strip() for q in args.queries.split(",")]

    print(f"Processing {len(urls)} URL(s) with {len(queries)} queries")
    print(f"Viewport: {args.viewport}")
    print(f"Total analyses: {len(urls)} × {len(queries)} = {len(urls) * len(queries)}")

    try:
        start_time = time.time()

        if len(urls) == 1 and len(queries) == 1:
            # Simple single URL, single query using one-shot mode for comparison
            result = await lens.analyze_async(
                source=urls[0],
                query=queries[0],
                viewport=args.viewport,
            )
            print(f"\nURL: {result.source}")
            print(f"Query: {result.query}")
            print(f"Answer: {result.answer}")
            print(f"Confidence: {result.confidence:.1%}")
            print(f"Pipeline Mode: {result.metadata.get('pipeline_mode', 'N/A')}")
        else:
            # Use 2-stage pipeline batch processing
            results = lens.pipeline_batch(
                sources=urls,
                queries=queries,
                viewport=args.viewport,
                wait_for_selector=getattr(args, "wait_for", None),
                wait_time=getattr(args, "wait_time", None),
                max_concurrent_capture=getattr(args, "max_concurrent", 3),
            )

            # Display results
            successful_analyses = 0
            failed_analyses = 0

            for url, analysis_results in results.items():
                print(f"\n{'-' * 60}")
                print(f"URL: {url}")

                for i, result in enumerate(analysis_results):
                    if result.confidence > 0:
                        successful_analyses += 1
                        print(f"\nQuery {i+1}: {result.query}")
                        print(f"Answer: {result.answer}")
                        print(f"Confidence: {result.confidence:.1%}")
                        print(f"Pipeline Mode: {result.metadata.get('pipeline_mode', 'N/A')}")
                    else:
                        failed_analyses += 1
                        print(f"\nQuery {i+1}: {result.query}")
                        print(f"FAILED: {result.answer}")

            execution_time = time.time() - start_time
            total_analyses = len(urls) * len(queries)

            print(f"\n{'-' * 60}")
            print(f"Pipeline Summary:")
            print(f"Successful: {successful_analyses}/{total_analyses}")
            print(f"Failed: {failed_analyses}/{total_analyses}")
            print(f"Total time: {execution_time:.2f}s")
            print(f"Average time per analysis: {execution_time/total_analyses:.2f}s")

            if failed_analyses > 0:
                sys.exit(1)

    except Exception as e:
        logger.error(f"Pipeline processing failed: {e}")
        print(f"Pipeline processing failed: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_screenshots(args) -> None:
    """Execute screenshots management command.

    Manages captured screenshots with various operations.

    Args:
        args: Command line arguments containing:
            - action: Action to perform (list, info, cleanup, stats)
            - detailed: Whether to show detailed information
            - max_age: Maximum age in days for cleanup
            - screenshot_path: Path to specific screenshot for info
            - output: Output directory

    Raises:
        SystemExit: If operation fails.
    """
    logger = get_logger("cli.screenshots")
    logger.debug(f"Starting screenshots command with action: {args.action}")

    try:
        from .utils import ScreenshotManager

        manager = ScreenshotManager(output_dir=args.output)

        if args.action == "list":
            screenshots = manager.list_screenshots(detailed=args.detailed)

            if not screenshots:
                print("No screenshots found")
                return

            print(f"Found {len(screenshots)} screenshots:")
            print(f"{'Filename':<50} {'Size (MB)':<12} {'Age (hours)':<12}")
            print("-" * 80)

            for screenshot in screenshots:
                filename = screenshot.get("filename", "Unknown")
                size_mb = screenshot.get("size_mb", 0)
                age_hours = screenshot.get("age_hours", 0)

                print(f"{filename:<50} {size_mb:<12.2f} {age_hours:<12.1f}")

                if args.detailed and "source_name" in screenshot:
                    print(f"  Source: {screenshot.get('source_name', 'Unknown')}")
                    print(f"  Viewport: {screenshot.get('viewport', 'Unknown')}")
                    if "capture_time" in screenshot:
                        print(f"  Captured: {screenshot['capture_time']}")

        elif args.action == "info":
            if not args.screenshot_path:
                print("Screenshot path required for info action", file=sys.stderr)
                sys.exit(1)

            info = manager.get_screenshot_info(Path(args.screenshot_path))

            if "error" in info:
                print(f"Error: {info['error']}", file=sys.stderr)
                sys.exit(1)

            print(f"Screenshot Information:")
            print(f"  Filename: {info.get('filename')}")
            print(f"  Size: {info.get('size_mb')} MB ({info.get('size_bytes')} bytes)")
            print(f"  Created: {info.get('created')}")
            print(f"  Modified: {info.get('modified')}")
            print(f"  Age: {info.get('age_hours')} hours")

            if "source_name" in info:
                print(f"  Source: {info.get('source_name')}")
                print(f"  Viewport: {info.get('viewport')}")
                print(f"  Hash: {info.get('source_hash')}")
                if "capture_time" in info:
                    print(f"  Capture Time: {info.get('capture_time')}")

        elif args.action == "cleanup":
            deleted_count = manager.cleanup_old_screenshots(max_age_days=args.max_age)
            print(f"Cleaned up {deleted_count} screenshots older than {args.max_age} days")

        elif args.action == "stats":
            stats = manager.get_storage_stats()

            print(f"Screenshot Storage Statistics:")
            print(f"  Directory: {stats.get('directory')}")
            print(f"  Total Screenshots: {stats.get('total_screenshots')}")
            print(f"  Total Size: {stats.get('total_size_mb')} MB")
            print(f"  Average Size: {stats.get('average_size_mb')} MB")
            print(f"  Largest Screenshot: {stats.get('largest_size_mb')} MB")
            print(f"  Smallest Screenshot: {stats.get('smallest_size_mb')} MB")
            print(f"  Oldest Screenshot: {stats.get('oldest_screenshot')}")
            print(f"  Newest Screenshot: {stats.get('newest_screenshot')}")

    except Exception as e:
        logger.error(f"Screenshots management failed: {e}")
        print(f"Screenshots management failed: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_validate(args) -> None:
    """Execute validation command for configuration files and test suites.

    Validates YAML configuration files or test suite files for syntax errors,
    required fields, and logical consistency.

    Args:
        args: Command line arguments containing:
            - config: Path to configuration YAML file to validate
            - suite: Path to test suite YAML file to validate

    Raises:
        SystemExit: If validation fails or file not found.
    """
    if args.config:
        try:
            config = Config(args.config)
            errors = config.validate()

            if errors:
                print("Configuration validation failed:", file=sys.stderr)
                for error in errors:
                    print(f"  - {error}", file=sys.stderr)
                sys.exit(1)
            else:
                print("Configuration is valid ✓")
        except Exception as e:
            print(f"Error loading configuration: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.suite:
        try:
            with open(args.suite) as f:
                data = yaml.safe_load(f)

            # Basic validation
            required_fields = ["name", "test_cases"]
            for field in required_fields:
                if field not in data:
                    print(f"Missing required field: {field}", file=sys.stderr)
                    sys.exit(1)

            # Validate test cases
            test_cases = data.get("test_cases", [])
            if not test_cases:
                print("No test cases found", file=sys.stderr)
                sys.exit(1)

            for i, case in enumerate(test_cases):
                if "name" not in case:
                    print(f"Test case {i} missing name", file=sys.stderr)
                    sys.exit(1)
                if "html_path" not in case:
                    print(f"Test case {i} missing html_path", file=sys.stderr)
                    sys.exit(1)

                # Check if HTML file exists
                if not Path(case["html_path"]).exists():
                    print(f"HTML file not found: {case['html_path']}")

            print(f"Test suite is valid ✓ ({len(test_cases)} test cases)")

        except Exception as e:
            print(f"Error validating test suite: {e}", file=sys.stderr)
            sys.exit(1)

    else:
        print("Error: Either --config or --suite must be specified", file=sys.stderr)
        sys.exit(1)


async def run_test_suite_async(tester: LayoutLens, suite: UITestSuite, args) -> list[UITestResult]:
    """Run test suite with async processing for optimal performance.

    Executes all test cases in a test suite using concurrent async processing.
    Each test case runs its queries in parallel for maximum efficiency.

    Args:
        tester: Initialized LayoutLens instance for analysis.
        suite: UITestSuite containing test cases to execute.
        args: Command line arguments containing max_concurrent setting.

    Returns:
        List of UITestResult objects containing execution results for each test case.
    """
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
