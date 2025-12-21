"""Command-line interface for LayoutLens framework.

This module provides the main CLI entry point for the LayoutLens UI testing system.
All command implementations are async-by-default for optimal performance.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from .logger import get_logger, setup_logging


def create_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser with all subcommands and options.

    Returns:
        Configured ArgumentParser with all LayoutLens CLI commands and options.
    """
    parser = argparse.ArgumentParser(
        description="LayoutLens - AI-Enabled UI Test System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test a single page
  layoutlens test --page homepage.html --queries "Is the logo centered?"

  # Run a test suite
  layoutlens test --suite regression_tests.yaml

  # Compare two pages
  layoutlens compare before.html after.html

  # Generate configuration
  layoutlens generate config

  # Batch process multiple sources
  layoutlens batch --sources "page1.html,page2.html" --queries "Good design?"

  # Start interactive session
  layoutlens interactive
        """,
    )

    # Global options
    parser.add_argument("--config", "-c", help="Configuration file path")
    parser.add_argument("--api-key", help="API key (or set OPENAI_API_KEY env var)")
    parser.add_argument("--output", "-o", help="Output directory", default="layoutlens_output")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--provider",
        choices=["openai", "anthropic", "google", "gemini", "litellm"],
        default="openai",
        help="AI provider to use (default: openai)",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="Model to use for analysis (default: gpt-4o-mini)",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=3,
        help="Maximum concurrent operations (default: 3)",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Test command
    test_parser = subparsers.add_parser("test", help="Run UI tests")
    test_group = test_parser.add_mutually_exclusive_group(required=True)
    test_group.add_argument("--page", help="Test single HTML page or URL")
    test_group.add_argument("--suite", help="Test suite YAML file")
    test_parser.add_argument("--queries", help="Comma-separated list of test queries")
    test_parser.add_argument("--viewports", help="Comma-separated list of viewport names")

    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare two pages")
    compare_parser.add_argument("page_a", help="First HTML page")
    compare_parser.add_argument("page_b", help="Second HTML page")
    compare_parser.add_argument("--viewport", default="desktop", help="Viewport for comparison")
    compare_parser.add_argument(
        "--query",
        default="Which page has a better layout design?",
        help="Comparison query",
    )

    # Batch command
    batch_parser = subparsers.add_parser("batch", help="Process multiple sources")
    batch_parser.add_argument("--sources", help="Comma-separated list of sources")
    batch_parser.add_argument("--sources-file", help="File containing list of sources")
    batch_parser.add_argument("--queries", help="Comma-separated queries")
    batch_parser.add_argument("--viewport", default="desktop", help="Viewport for analysis")

    # Generate command
    generate_parser = subparsers.add_parser("generate", help="Generate files")
    generate_parser.add_argument(
        "type",
        choices=["config", "suite"],
        help="Type of file to generate",
    )

    # Info command
    _ = subparsers.add_parser("info", help="Show system information and check setup")

    # Interactive command
    _ = subparsers.add_parser("interactive", help="Start interactive analysis session")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate configuration or test suite")
    validate_group = validate_parser.add_mutually_exclusive_group(required=True)
    validate_group.add_argument("--config", help="Validate configuration file")
    validate_group.add_argument("--suite", help="Validate test suite file")

    # Pipeline commands for 2-stage processing

    # Capture command - Stage 1 of pipeline
    capture_parser = subparsers.add_parser("capture", help="Capture screenshots (Stage 1 of 2-stage pipeline)")
    capture_group = capture_parser.add_mutually_exclusive_group(required=True)
    capture_group.add_argument("--url", help="Single URL to capture")
    capture_group.add_argument("--urls", help="Comma-separated list of URLs to capture")
    capture_group.add_argument("--urls-file", help="File containing list of URLs (one per line)")
    capture_parser.add_argument("--viewport", default="desktop", help="Viewport for capture")
    capture_parser.add_argument("--wait-for", help="CSS selector to wait for before capturing")
    capture_parser.add_argument("--wait-time", type=int, help="Additional wait time in milliseconds")

    # Analyze command - Stage 2 of pipeline
    analyze_parser = subparsers.add_parser("analyze", help="Analyze screenshots (Stage 2 of 2-stage pipeline)")
    analyze_group = analyze_parser.add_mutually_exclusive_group(required=True)
    analyze_group.add_argument("--screenshot", help="Single screenshot to analyze")
    analyze_group.add_argument("--screenshots", help="Comma-separated list of screenshots to analyze")
    analyze_group.add_argument("--screenshots-dir", help="Directory containing screenshots to analyze")
    analyze_parser.add_argument("--queries", required=True, help="Comma-separated list of analysis queries")
    analyze_parser.add_argument("--viewport", default="desktop", help="Viewport that was used for capture")

    # Pipeline command - Complete 2-stage processing
    pipeline_parser = subparsers.add_parser("pipeline", help="Complete 2-stage pipeline (capture + analyze)")
    pipeline_group = pipeline_parser.add_mutually_exclusive_group(required=True)
    pipeline_group.add_argument("--url", help="Single URL to process")
    pipeline_group.add_argument("--urls", help="Comma-separated list of URLs to process")
    pipeline_group.add_argument("--urls-file", help="File containing list of URLs (one per line)")
    pipeline_parser.add_argument("--queries", required=True, help="Comma-separated list of analysis queries")
    pipeline_parser.add_argument("--viewport", default="desktop", help="Viewport for capture and analysis")
    pipeline_parser.add_argument("--wait-for", help="CSS selector to wait for before capturing")
    pipeline_parser.add_argument("--wait-time", type=int, help="Additional wait time in milliseconds")

    # Screenshots management command
    screenshots_parser = subparsers.add_parser("screenshots", help="Manage captured screenshots")
    screenshots_parser.add_argument("action", choices=["list", "info", "cleanup", "stats"], help="Action to perform")
    screenshots_parser.add_argument("--detailed", action="store_true", help="Show detailed information")
    screenshots_parser.add_argument("--max-age", type=int, default=30, help="Max age in days for cleanup")
    screenshots_parser.add_argument("--screenshot-path", help="Path to specific screenshot for info")

    return parser


async def main_async() -> None:
    """Main async CLI entry point with command routing and error handling.

    Parses command line arguments, configures logging, and routes to appropriate
    command handlers. All commands use async-by-default for optimal performance.

    Raises:
        SystemExit: If command parsing fails or command execution fails.
    """
    parser = create_parser()
    args = parser.parse_args()

    # Configure logging based on verbosity
    if getattr(args, "verbose", False):
        setup_logging(
            level="DEBUG",
            console=True,
            file_path=str(Path(args.output) / "cli.log"),
            format_type="debug",
        )
    else:
        setup_logging(
            level="WARNING",
            console=False,
            file_path=str(Path(args.output) / "cli.log"),
            format_type="default",
        )

    logger = get_logger("cli.main")
    logger.debug(f"CLI started with command: {args.command}")

    # Set up API key from environment if not provided
    if not args.api_key:
        import os

        args.api_key = os.getenv("OPENAI_API_KEY")

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Import command implementations
    from . import cli_commands

    # Route to appropriate command
    try:
        match args.command:
            case "test":
                await cli_commands.cmd_test(args)
            case "compare":
                await cli_commands.cmd_compare(args)
            case "batch":
                await cli_commands.cmd_batch(args)
            case "generate":
                cli_commands.cmd_generate(args)
            case "info":
                cli_commands.cmd_info(args)
            case "interactive":
                await cli_commands.cmd_interactive(args)
            case "validate":
                cli_commands.cmd_validate(args)
            case "capture":
                await cli_commands.cmd_capture(args)
            case "analyze":
                await cli_commands.cmd_analyze(args)
            case "pipeline":
                await cli_commands.cmd_pipeline(args)
            case "screenshots":
                cli_commands.cmd_screenshots(args)
            case _:
                logger.warning(f"Unknown command: {args.command}")
                parser.print_help()
                sys.exit(1)

    except KeyboardInterrupt:
        logger.debug("Operation cancelled by user")
        print("\nOperation cancelled by user.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Command execution failed: {e}", exc_info=True)
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main CLI entry point that wraps async execution.

    Provides the main entry point for the layoutlens command, handling
    async execution and top-level error catching.

    Raises:
        SystemExit: If execution fails or is interrupted.
    """
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
