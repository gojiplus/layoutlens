"""Command-line interface for LayoutLens framework.

This module provides a comprehensive CLI for the LayoutLens UI testing system.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional

from .config import Config, create_default_config
from .core import LayoutLens
from .test_runner import TestRunner


def cmd_test(args) -> None:
    """Execute test command."""
    # Initialize LayoutLens
    config_path = args.config if args.config else None
    tester = LayoutLens(config=config_path, api_key=args.api_key, output_dir=args.output)
    
    if args.page:
        # Test single page
        queries = args.queries.split(',') if args.queries else None
        viewports = args.viewports.split(',') if args.viewports else None
        
        print(f"Testing page: {args.page}")
        result = tester.test_page(
            html_path=args.page,
            queries=queries,
            viewports=viewports,
            auto_generate_queries=not args.no_auto_queries
        )
        
        if result:
            print(f"Result: {result.passed_tests}/{result.total_tests} tests passed ({result.success_rate:.2%})")
        else:
            print("Test execution failed")
            sys.exit(1)
    
    elif args.suite:
        # Test suite
        runner = TestRunner(tester.config)
        session = runner.run_test_suite(
            test_suite=args.suite,
            parallel=args.parallel,
            max_workers=args.workers
        )
        
        print(f"Session completed: {session.success_rate:.2%} success rate")
        if session.success_rate < 0.8:
            sys.exit(1)
    
    else:
        print("Error: Either --page or --suite must be specified")
        sys.exit(1)


def cmd_compare(args) -> None:
    """Execute compare command."""
    config_path = args.config if args.config else None
    tester = LayoutLens(config=config_path, api_key=args.api_key, output_dir=args.output)
    
    print(f"Comparing: {args.page_a} vs {args.page_b}")
    result = tester.compare_pages(
        page_a_path=args.page_a,
        page_b_path=args.page_b,
        viewport=args.viewport,
        query=args.query
    )
    
    if result:
        print(f"Comparison result: {result['answer']}")
    else:
        print("Comparison failed")
        sys.exit(1)


def cmd_generate(args) -> None:
    """Execute generate command."""
    if args.type == "config":
        # Generate config file
        config_path = args.output if args.output else "layoutlens.yaml"
        config = create_default_config(config_path)
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
                        "Is the layout responsive?"
                    ],
                    "viewports": ["mobile_portrait", "desktop"],
                    "expected_results": {},
                    "metadata": {"priority": "high"}
                }
            ],
            "metadata": {"version": "1.0"}
        }
        
        import yaml
        with open(suite_path, 'w') as f:
            yaml.dump(template, f, default_flow_style=False, indent=2)
        
        print(f"Test suite template created: {suite_path}")
    
    elif args.type == "benchmarks":
        # Generate benchmark data
        config_path = args.config if args.config else None
        tester = LayoutLens(config=config_path, api_key=args.api_key)
        output_dir = args.output if args.output else "benchmarks"
        
        print("Generating benchmark data...")
        tester.generate_benchmark_data(output_dir)
        print(f"Benchmark data generated in: {output_dir}")
    
    else:
        print(f"Unknown generate type: {args.type}")
        sys.exit(1)


def cmd_regression(args) -> None:
    """Execute regression testing command."""
    config_path = args.config if args.config else None
    runner = TestRunner(Config(config_path) if config_path else None)
    
    patterns = args.patterns.split(',') if args.patterns else ["*.html"]
    viewports = args.viewports.split(',') if args.viewports else None
    
    print(f"Running regression tests:")
    print(f"  Baseline: {args.baseline}")
    print(f"  Current: {args.current}")
    print(f"  Patterns: {patterns}")
    
    session = runner.run_regression_tests(
        baseline_dir=args.baseline,
        current_dir=args.current,
        test_patterns=patterns,
        viewports=viewports
    )
    
    print(f"Regression testing completed: {session.success_rate:.2%} success rate")
    if session.success_rate < args.threshold:
        print(f"Regression test failed: success rate {session.success_rate:.2%} below threshold {args.threshold:.2%}")
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
            with open(args.suite, 'r') as f:
                data = yaml.safe_load(f)
            
            # Basic validation
            required_fields = ['name', 'test_cases']
            for field in required_fields:
                if field not in data:
                    print(f"Missing required field: {field}")
                    sys.exit(1)
            
            # Validate test cases
            test_cases = data.get('test_cases', [])
            if not test_cases:
                print("No test cases found")
                sys.exit(1)
            
            for i, case in enumerate(test_cases):
                if 'name' not in case:
                    print(f"Test case {i} missing name")
                    sys.exit(1)
                if 'html_path' not in case:
                    print(f"Test case {i} missing html_path")
                    sys.exit(1)
                
                # Check if HTML file exists
                if not Path(case['html_path']).exists():
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
  
  # Run a test suite
  layoutlens test --suite regression_tests.yaml --parallel
  
  # Compare two pages
  layoutlens compare before.html after.html
  
  # Generate configuration
  layoutlens generate config
  
  # Run regression tests
  layoutlens regression --baseline v1/ --current v2/ --patterns "*.html,pages/*.html"
        """
    )
    
    # Global options
    parser.add_argument('--config', '-c', help='Configuration file path')
    parser.add_argument('--api-key', help='OpenAI API key (or set OPENAI_API_KEY)')
    parser.add_argument('--output', '-o', help='Output directory')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Run UI tests')
    test_group = test_parser.add_mutually_exclusive_group(required=True)
    test_group.add_argument('--page', help='Test single HTML page')
    test_group.add_argument('--suite', help='Test suite YAML file')
    test_parser.add_argument('--queries', help='Comma-separated list of test queries')
    test_parser.add_argument('--viewports', help='Comma-separated list of viewport names')
    test_parser.add_argument('--no-auto-queries', action='store_true', help='Disable automatic query generation')
    test_parser.add_argument('--parallel', action='store_true', help='Run tests in parallel')
    test_parser.add_argument('--workers', type=int, help='Number of parallel workers')
    
    # Compare command
    compare_parser = subparsers.add_parser('compare', help='Compare two pages')
    compare_parser.add_argument('page_a', help='First HTML page')
    compare_parser.add_argument('page_b', help='Second HTML page')
    compare_parser.add_argument('--viewport', default='desktop', help='Viewport for comparison')
    compare_parser.add_argument('--query', default='Do these two layouts look the same?', help='Comparison query')
    
    # Generate command
    generate_parser = subparsers.add_parser('generate', help='Generate files')
    generate_parser.add_argument('type', choices=['config', 'suite', 'benchmarks'], help='Type of file to generate')
    
    # Regression command
    regression_parser = subparsers.add_parser('regression', help='Run regression tests')
    regression_parser.add_argument('--baseline', required=True, help='Baseline directory')
    regression_parser.add_argument('--current', required=True, help='Current version directory')
    regression_parser.add_argument('--patterns', default='*.html', help='Comma-separated file patterns')
    regression_parser.add_argument('--viewports', help='Comma-separated viewport names')
    regression_parser.add_argument('--threshold', type=float, default=0.8, help='Success rate threshold')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate configuration or test suite')
    validate_group = validate_parser.add_mutually_exclusive_group(required=True)
    validate_group.add_argument('--config', help='Validate configuration file')
    validate_group.add_argument('--suite', help='Validate test suite file')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Set up API key from environment if not provided
    if not args.api_key:
        args.api_key = os.getenv('OPENAI_API_KEY')
    
    # Handle commands
    if args.command == 'test':
        cmd_test(args)
    elif args.command == 'compare':
        cmd_compare(args)
    elif args.command == 'generate':
        cmd_generate(args)
    elif args.command == 'regression':
        cmd_regression(args)
    elif args.command == 'validate':
        cmd_validate(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()