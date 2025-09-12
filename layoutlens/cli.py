"""Command-line interface for LayoutLens framework.

This module provides a comprehensive CLI for the LayoutLens UI testing system.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional

from .config import Config, create_default_config
from .api.core import LayoutLens


def cmd_test(args) -> None:
    """Execute test command."""
    # Initialize LayoutLens
    try:
        tester = LayoutLens(api_key=args.api_key, output_dir=args.output)
    except Exception as e:
        print(f"Error initializing LayoutLens: {e}")
        sys.exit(1)
    
    if args.page:
        # Test single page
        queries = args.queries.split(',') if args.queries else ["Is this page well-designed and user-friendly?"]
        viewport = args.viewports.split(',')[0] if args.viewports else "desktop"
        
        print(f"Analyzing page: {args.page}")
        
        try:
            results = []
            for query in queries:
                result = tester.analyze(source=args.page, query=query.strip(), viewport=viewport)
                results.append({
                    'query': query.strip(),
                    'answer': result.answer,
                    'confidence': result.confidence
                })
                print(f"Query: {query.strip()}")
                print(f"Answer: {result.answer}")
                print(f"Confidence: {result.confidence:.1%}")
                print("-" * 50)
            
            avg_confidence = sum(r['confidence'] for r in results) / len(results)
            print(f"Analysis complete. Average confidence: {avg_confidence:.1%}")
            
        except Exception as e:
            print(f"Analysis failed: {e}")
            sys.exit(1)
    
    elif args.suite:
        print("Error: Test suite functionality not yet implemented.")
        print("Use individual page analysis with --page instead.")
        sys.exit(1)
    else:
        print("Error: Either --page or --suite must be specified")
        sys.exit(1)


def cmd_compare(args) -> None:
    """Execute compare command."""
    try:
        tester = LayoutLens(api_key=args.api_key, output_dir=args.output)
    except Exception as e:
        print(f"Error initializing LayoutLens: {e}")
        sys.exit(1)
    
    print(f"Comparing: {args.page_a} vs {args.page_b}")
    
    try:
        result = tester.compare(
            sources=[args.page_a, args.page_b],
            query=args.query
        )
        
        print(f"Comparison result: {result.answer}")
        print(f"Confidence: {result.confidence:.1%}")
        if hasattr(result, 'reasoning'):
            print(f"Reasoning: {result.reasoning}")
            
    except Exception as e:
        print(f"Comparison failed: {e}")
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
    import glob
    # Test suite functionality not implemented yet
    # from .api.core import LayoutLens
    
    config_path = args.config if args.config else None
    tester = LayoutLens(config=config_path)
    
    patterns = args.patterns.split(',') if args.patterns else ["*.html"]
    viewports = args.viewports.split(',') if args.viewports else ["desktop"]
    
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
    for i, (baseline_file, current_file) in enumerate(test_pairs):
        file_name = Path(baseline_file).name
        test_case = TestCase(
            name=f"Regression_{file_name}",
            html_path=current_file,  # Test the current version
            queries=[
                f"Does this layout match the baseline design?",
                f"Are there any visual regressions compared to the baseline?",
                f"Is the layout consistent with the previous version?"
            ],
            viewports=viewports,
            metadata={
                "baseline_file": baseline_file,
                "current_file": current_file,
                "test_type": "regression"
            }
        )
        test_cases.append(test_case)
    
    # Create regression test suite
    regression_suite = TestSuite(
        name="Regression_Tests",
        description=f"Regression testing: {args.baseline} vs {args.current}",
        test_cases=test_cases,
        metadata={
            "baseline_dir": args.baseline,
            "current_dir": args.current,
            "test_patterns": patterns
        }
    )
    
    # Execute regression tests
    results = tester.run_test_suite(regression_suite)
    
    # Calculate success rate
    total_tests = sum(r.total_tests for r in results)
    total_passed = sum(r.passed_tests for r in results)
    success_rate = total_passed / total_tests if total_tests > 0 else 0
    
    print(f"Regression testing completed: {success_rate:.2%} success rate")
    if success_rate < args.threshold:
        print(f"Regression test failed: success rate {success_rate:.2%} below threshold {args.threshold:.2%}")
        sys.exit(1)


def cmd_info(args) -> None:
    """Execute info command."""
    from . import __version__
    import sys
    
    print(f"LayoutLens v{__version__}")
    print(f"Python: {sys.version.split()[0]}")
    
    # Check dependencies
    try:
        import openai
        print(f"OpenAI: {openai.__version__}")
    except ImportError:
        print("OpenAI: Not installed")
    
    try:
        import playwright
        # Playwright doesn't expose __version__ at top level
        print("Playwright: Installed")
    except ImportError:
        print("Playwright: Not installed")
    
    # Check API key
    import os
    api_key = os.getenv('OPENAI_API_KEY')
    if api_key:
        print("API Key: Set")
    else:
        print("API Key: Not set (set OPENAI_API_KEY environment variable)")
    
    # Test basic functionality
    try:
        from .api.core import LayoutLens
        tester = LayoutLens()
        print("✓ LayoutLens initialization: OK")
    except Exception as e:
        print(f"✗ LayoutLens initialization: Failed ({e})")


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
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Show system information and check setup')
    
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
    elif args.command == 'info':
        cmd_info(args)
    elif args.command == 'validate':
        cmd_validate(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()