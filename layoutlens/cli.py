"""Command-line interface for LayoutLens framework.

This module provides a comprehensive CLI for the LayoutLens UI testing system.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from .api.core import LayoutLens
from .api.test_suite import UITestCase, UITestResult, UITestSuite
from .config import Config, create_default_config
from .interactive import run_interactive_session
from .logger import configure_for_development, get_logger, setup_logging


def cmd_test(args) -> None:
    """Execute test command."""
    logger = get_logger("cli.test")
    logger.debug(
        f"Starting test command with args: page={getattr(args, 'page', None)}, suite={getattr(args, 'suite', None)}"
    )

    # Initialize LayoutLens
    try:
        tester = LayoutLens(
            api_key=args.api_key,
            model=getattr(args, "model", "gpt-4o-mini"),
            provider=getattr(args, "provider", "openrouter"),
            output_dir=args.output,
        )
        logger.info("LayoutLens initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize LayoutLens: {e}")
        print(f"Error initializing LayoutLens: {e}")
        sys.exit(1)

    if args.page:
        # Test single page
        queries = args.queries.split(",") if args.queries else ["Is this page well-designed and user-friendly?"]
        viewport = args.viewports.split(",")[0] if args.viewports else "desktop"

        logger.info(f"Starting single page analysis: {args.page} with {len(queries)} queries")
        print(f"Analyzing page: {args.page}")

        try:
            results = []
            for i, query in enumerate(queries):
                logger.debug(f"Processing query {i+1}/{len(queries)}: {query.strip()[:50]}...")
                result = tester.analyze(source=args.page, query=query.strip(), viewport=viewport)
                results.append(
                    {
                        "query": query.strip(),
                        "answer": result.answer,
                        "confidence": result.confidence,
                    }
                )
                print(f"Query: {query.strip()}")
                print(f"Answer: {result.answer}")
                print(f"Confidence: {result.confidence:.1%}")
                print("-" * 50)

            avg_confidence = sum(r["confidence"] for r in results) / len(results)
            logger.info(f"Single page analysis completed: {len(results)} queries, avg confidence: {avg_confidence:.2f}")
            print(f"Analysis complete. Average confidence: {avg_confidence:.1%}")

        except Exception as e:
            logger.error(f"Single page analysis failed: {e}")
            print(f"Analysis failed: {e}")
            sys.exit(1)

    elif args.suite:
        # Load and run test suite
        try:
            suite = UITestSuite.load(Path(args.suite))
            print(f"Running test suite: {suite.name}")
            print(f"Description: {suite.description}")
            print(f"Test cases: {len(suite.test_cases)}")
            print("-" * 50)

            # NOTE: Test suite running is not yet implemented in the sync CLI
            # Use the async CLI (cli_async.py) for test suite functionality
            print("❌ Test suite execution not implemented in sync CLI")
            print("💡 Use: python -m layoutlens.cli_async test-suite --suite your_suite.yaml")
            return
            total_tests = 0
            total_passed = 0

            for result in results:
                print(f"\nTest Case: {result.test_case_name}")
                print(f"  Tests: {result.total_tests}")
                print(f"  Passed: {result.passed_tests}")
                print(f"  Failed: {result.failed_tests}")
                print(f"  Success Rate: {result.success_rate:.1%}")
                print(f"  Duration: {result.duration_seconds:.2f}s")

                total_tests += result.total_tests
                total_passed += result.passed_tests

            # Overall summary
            overall_rate = total_passed / total_tests if total_tests > 0 else 0
            print("\n" + "=" * 50)
            print(f"Overall Results:")
            print(f"  Total Tests: {total_tests}")
            print(f"  Total Passed: {total_passed}")
            print(f"  Success Rate: {overall_rate:.1%}")

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


def cmd_compare(args) -> None:
    """Execute compare command."""
    logger = get_logger("cli.compare")
    logger.debug(f"Starting compare command: {args.page_a} vs {args.page_b}")

    try:
        tester = LayoutLens(
            api_key=args.api_key,
            model=args.model,
            provider=args.provider,
            output_dir=args.output,
        )
        logger.info("LayoutLens initialized for comparison")
    except Exception as e:
        logger.error(f"Failed to initialize LayoutLens for comparison: {e}")
        print(f"Error initializing LayoutLens: {e}")
        sys.exit(1)

    print(f"Comparing: {args.page_a} vs {args.page_b}")

    try:
        logger.info(f"Starting comparison: {args.page_a} vs {args.page_b}")
        result = tester.compare(sources=[args.page_a, args.page_b], query=args.query)

        logger.info(f"Comparison completed with confidence: {result.confidence:.2f}")
        print(f"Comparison result: {result.answer}")
        print(f"Confidence: {result.confidence:.1%}")
        if hasattr(result, "reasoning"):
            print(f"Reasoning: {result.reasoning}")

    except Exception as e:
        logger.error(f"Comparison failed: {e}")
        print(f"Comparison failed: {e}")
        sys.exit(1)


def cmd_generate(args) -> None:
    """Execute generate command."""
    if args.type == "config":
        # Generate config file
        config_path = args.output if args.output else "layoutlens.yaml"
        _ = create_default_config(config_path)
        print(f"Default configuration created: {config_path}")

    elif args.type == "suite":
        # Generate test suite template
        suite_path = args.output if args.output else "test_suite.yaml"
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

        import yaml

        with open(suite_path, "w") as f:
            yaml.dump(template, f, default_flow_style=False, indent=2)

        print(f"Test suite template created: {suite_path}")

    elif args.type == "benchmarks":
        # Generate benchmark data
        output_dir = args.output if args.output else "benchmarks"

        print("❌ Benchmark data generation not yet implemented")
        print(f"💡 Output directory would be: {output_dir}")
        print(f"💡 API key provided: {bool(args.api_key)}")
        # TODO: Implement benchmark data generation

    else:
        print(f"Unknown generate type: {args.type}")
        sys.exit(1)


def cmd_regression(args) -> None:
    """Execute regression testing command."""
    import glob

    patterns = args.patterns.split(",") if args.patterns else ["*.html"]
    viewports = args.viewports.split(",") if args.viewports else ["desktop"]

    print(f"Running regression tests:")
    print(f"  Baseline: {args.baseline}")
    print(f"  Current: {args.current}")
    print(f"  Patterns: {patterns}")

    # Find matching files
    baseline_files = []
    current_files = []

    for pattern in patterns:
        baseline_matches = glob.glob(str(Path(args.baseline) / pattern))
        current_matches = glob.glob(str(Path(args.current) / pattern))

        baseline_files.extend(baseline_matches)
        current_files.extend(current_matches)

    # Match baseline and current files
    test_pairs = []
    for baseline_file in baseline_files:
        baseline_name = Path(baseline_file).name
        current_file = None

        for cf in current_files:
            if Path(cf).name == baseline_name:
                current_file = cf
                break

        if current_file:
            test_pairs.append((baseline_file, current_file))
        else:
            print(f"Warning: No current version found for {baseline_name}")

    if not test_pairs:
        print("No matching file pairs found for regression testing")
        sys.exit(1)

    # Create test cases for comparison
    test_cases = []
    for _i, (baseline_file, current_file) in enumerate(test_pairs):
        file_name = Path(baseline_file).name
        test_case = UITestCase(
            name=f"Regression_{file_name}",
            html_path=current_file,  # Test the current version
            queries=[
                f"Does this layout match the baseline design?",
                f"Are there any visual regressions compared to the baseline?",
                f"Is the layout consistent with the previous version?",
            ],
            viewports=viewports,
            metadata={
                "baseline_file": baseline_file,
                "current_file": current_file,
                "test_type": "regression",
            },
        )
        test_cases.append(test_case)

    # Create regression test suite (placeholder)
    print(f"Created regression suite with {len(test_cases)} test cases")
    print(f"  Baseline: {args.baseline}")
    print(f"  Current: {args.current}")
    print(f"  Test patterns: {patterns}")

    # Execute regression tests
    print("❌ Regression testing not yet implemented in sync CLI")
    print("💡 Use async CLI for test execution functionality")
    # TODO: Implement regression testing
    print(f"Threshold was set to: {args.threshold:.2%}")


def cmd_info(args) -> None:
    """Execute info command."""
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
    openrouter_key = os.getenv("OPENROUTER_API_KEY")

    if openai_key:
        print("  OPENAI_API_KEY: Set")
    else:
        print("  OPENAI_API_KEY: Not set")

    if openrouter_key:
        print("  OPENROUTER_API_KEY: Set")
    else:
        print("  OPENROUTER_API_KEY: Not set")

    if not openai_key and not openrouter_key:
        print("  Note: Set OPENAI_API_KEY or OPENROUTER_API_KEY environment variable")

    # Test basic functionality
    try:
        from .api.core import LayoutLens

        _ = LayoutLens()
        print("✓ LayoutLens initialization: OK")
    except Exception as e:
        print(f"✗ LayoutLens initialization: Failed ({e})")


def cmd_interactive(args) -> None:
    """Execute interactive mode."""
    try:
        lens = LayoutLens(
            api_key=args.api_key,
            model=args.model,
            provider=args.provider,
            output_dir=args.output,
        )

        run_interactive_session(lens)

    except Exception as e:
        print(f"Error starting interactive session: {e}")
        sys.exit(1)


def cmd_validate(args) -> None:
    """Execute validation command."""
    if args.config:
        try:
            config = Config(args.config)
            errors = config.validate()

            if errors:
                print("Configuration validation failed:")
                for error in errors:
                    print(f"  - {error}")
                sys.exit(1)
            else:
                print("Configuration is valid ✓")
        except Exception as e:
            print(f"Error loading configuration: {e}")
            sys.exit(1)

    elif args.suite:
        try:
            import yaml

            with open(args.suite) as f:
                data = yaml.safe_load(f)

            # Basic validation
            required_fields = ["name", "test_cases"]
            for field in required_fields:
                if field not in data:
                    print(f"Missing required field: {field}")
                    sys.exit(1)

            # Validate test cases
            test_cases = data.get("test_cases", [])
            if not test_cases:
                print("No test cases found")
                sys.exit(1)

            for i, case in enumerate(test_cases):
                if "name" not in case:
                    print(f"Test case {i} missing name")
                    sys.exit(1)
                if "html_path" not in case:
                    print(f"Test case {i} missing html_path")
                    sys.exit(1)

                # Check if HTML file exists
                if not Path(case["html_path"]).exists():
                    print(f"HTML file not found: {case['html_path']}")

            print(f"Test suite is valid ✓ ({len(test_cases)} test cases)")

        except Exception as e:
            print(f"Error validating test suite: {e}")
            sys.exit(1)

    else:
        print("Error: Either --config or --suite must be specified")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="LayoutLens - AI-Enabled UI Test System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test a single page
  layoutlens test --page homepage.html --queries "Is the logo centered?"

  # Test with async processing for better performance
  layoutlens test --page homepage.html --queries "Is it accessible?" --async --max-concurrent 3

  # Run a test suite
  layoutlens test --suite regression_tests.yaml --parallel

  # Compare two pages
  layoutlens compare before.html after.html

  # Compare with async processing
  layoutlens compare before.html after.html --async

  # Generate configuration
  layoutlens generate config

  # Run regression tests
  layoutlens regression --baseline v1/ --current v2/ --patterns "*.html,pages/*.html"

  # Use dedicated async CLI for advanced performance features
  layoutlens-async batch --sources "page1.html,page2.html" --queries "Good design?" --max-concurrent 5
        """,
    )

    # Global options
    parser.add_argument("--config", "-c", help="Configuration file path")
    parser.add_argument("--api-key", help="API key (or set OPENAI_API_KEY/OPENROUTER_API_KEY)")
    parser.add_argument("--output", "-o", help="Output directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
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
        "--async",
        action="store_true",
        help="Use async processing for better performance",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=5,
        help="Maximum concurrent operations for async mode",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Test command
    test_parser = subparsers.add_parser("test", help="Run UI tests")
    test_group = test_parser.add_mutually_exclusive_group(required=True)
    test_group.add_argument("--page", help="Test single HTML page")
    test_group.add_argument("--suite", help="Test suite YAML file")
    test_parser.add_argument("--queries", help="Comma-separated list of test queries")
    test_parser.add_argument("--viewports", help="Comma-separated list of viewport names")
    test_parser.add_argument(
        "--no-auto-queries",
        action="store_true",
        help="Disable automatic query generation",
    )
    test_parser.add_argument("--parallel", action="store_true", help="Run tests in parallel")
    test_parser.add_argument("--workers", type=int, help="Number of parallel workers")

    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare two pages")
    compare_parser.add_argument("page_a", help="First HTML page")
    compare_parser.add_argument("page_b", help="Second HTML page")
    compare_parser.add_argument("--viewport", default="desktop", help="Viewport for comparison")
    compare_parser.add_argument(
        "--query",
        default="Do these two layouts look the same?",
        help="Comparison query",
    )

    # Generate command
    generate_parser = subparsers.add_parser("generate", help="Generate files")
    generate_parser.add_argument(
        "type",
        choices=["config", "suite", "benchmarks"],
        help="Type of file to generate",
    )

    # Regression command
    regression_parser = subparsers.add_parser("regression", help="Run regression tests")
    regression_parser.add_argument("--baseline", required=True, help="Baseline directory")
    regression_parser.add_argument("--current", required=True, help="Current version directory")
    regression_parser.add_argument("--patterns", default="*.html", help="Comma-separated file patterns")
    regression_parser.add_argument("--viewports", help="Comma-separated viewport names")
    regression_parser.add_argument("--threshold", type=float, default=0.8, help="Success rate threshold")

    # Info command
    _ = subparsers.add_parser("info", help="Show system information and check setup")

    # Interactive command
    _ = subparsers.add_parser("interactive", help="Start interactive analysis session")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate configuration or test suite")
    validate_group = validate_parser.add_mutually_exclusive_group(required=True)
    validate_group.add_argument("--config", help="Validate configuration file")
    validate_group.add_argument("--suite", help="Validate test suite file")

    # Parse arguments
    args = parser.parse_args()

    # Configure logging based on verbosity
    if getattr(args, "verbose", False):
        # Enable debug logging for verbose mode
        setup_logging(
            level="DEBUG",
            console=True,
            file_path=os.path.join(getattr(args, "output", "layoutlens_output"), "cli.log"),
            format_type="debug",
        )
    else:
        # Standard logging - only warnings and errors to avoid cluttering user output
        setup_logging(
            level="WARNING",
            console=False,  # Don't output to console to avoid interfering with user output
            file_path=os.path.join(getattr(args, "output", "layoutlens_output"), "cli.log"),
            format_type="default",
        )

    logger = get_logger("cli.main")
    logger.debug(f"CLI started with command: {args.command}")

    # Set up API key from environment if not provided
    if not args.api_key:
        args.api_key = os.getenv("OPENAI_API_KEY")

    # Handle commands
    try:
        if getattr(args, "async", False):
            # Route to async commands
            logger.debug("Using async command execution")
            import asyncio

            from .cli_async import cmd_compare_async, cmd_test_async

            if args.command == "test":
                asyncio.run(cmd_test_async(args))
            elif args.command == "compare":
                asyncio.run(cmd_compare_async(args))
            else:
                logger.warning(f"Async mode not available for command: {args.command}")
                print(f"Async mode not available for command: {args.command}")
                print("Available async commands: test, compare")
                sys.exit(1)
        else:
            # Use synchronous commands
            logger.debug(f"Executing synchronous command: {args.command}")
            if args.command == "test":
                cmd_test(args)
            elif args.command == "compare":
                cmd_compare(args)
            elif args.command == "generate":
                cmd_generate(args)
            elif args.command == "regression":
                cmd_regression(args)
            elif args.command == "info":
                cmd_info(args)
            elif args.command == "interactive":
                cmd_interactive(args)
            elif args.command == "validate":
                cmd_validate(args)
            else:
                logger.warning("No command specified, showing help")
                parser.print_help()
            sys.exit(1)
    except Exception as e:
        logger.error(f"Command execution failed: {e}")
        # Don't log to console as this would clutter user output
        # The specific command functions already handle user-facing error messages
        sys.exit(1)


if __name__ == "__main__":
    main()
