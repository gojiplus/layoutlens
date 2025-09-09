# CLI API Reference

The CLI module provides the command-line interface implementation for LayoutLens, enabling automation, scripting, and integration with development workflows.

## Main Function

### main()

The primary entry point for the CLI application.

```python
def main(args: Optional[List[str]] = None) -> int
```

**Parameters:**
- `args` (List[str], optional): Command-line arguments. If None, uses sys.argv

**Returns:**
- `int`: Exit code (0 for success, non-zero for errors)

**Example:**
```python
from layoutlens.cli import main

# Programmatic CLI usage
exit_code = main(["test", "--page", "homepage.html"])
if exit_code == 0:
    print("CLI command succeeded")
```

## Command Classes

### BaseCommand

Abstract base class for all CLI commands.

```python
class BaseCommand:
    def __init__(self, config: Config):
        self.config = config
    
    @abstractmethod
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add command-specific arguments to parser."""
        
    @abstractmethod
    def execute(self, args: argparse.Namespace) -> int:
        """Execute the command with parsed arguments."""
```

All CLI commands inherit from this base class and implement the argument parsing and execution logic.

### TestCommand

Execute visual tests on HTML pages.

```python
class TestCommand(BaseCommand):
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add test command arguments."""
        
    def execute(self, args: argparse.Namespace) -> int:
        """Execute test command."""
```

**Command:** `layoutlens test`

**Arguments:**
- `--page PATH` - Test a single HTML page
- `--pages PATTERN` - Test multiple pages using glob pattern
- `--suite PATH` - Run tests from YAML test suite file
- `--queries TEXT` - Comma-separated list of test queries
- `--viewports NAMES` - Comma-separated viewport names
- `--parallel` / `--no-parallel` - Enable/disable parallel execution
- `--output-dir PATH` - Results output directory
- `--format FORMAT` - Output format (json, html, junit, xml)
- `--fail-fast` - Stop on first test failure

**Example Usage:**
```python
from layoutlens.cli import TestCommand
from layoutlens import Config
import argparse

# Create command
config = Config()
command = TestCommand(config)

# Simulate argument parsing
parser = argparse.ArgumentParser()
command.add_arguments(parser)
args = parser.parse_args([
    "--page", "homepage.html",
    "--queries", "Is the navigation visible?,Is the layout responsive?",
    "--format", "json,html"
])

# Execute command
exit_code = command.execute(args)
```

### CompareCommand

Compare two HTML pages visually.

```python
class CompareCommand(BaseCommand):
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add compare command arguments."""
        
    def execute(self, args: argparse.Namespace) -> int:
        """Execute compare command."""
```

**Command:** `layoutlens compare`

**Arguments:**
- `page_a` - Path to first HTML page (positional)
- `page_b` - Path to second HTML page (positional)
- `--viewport NAME` - Viewport for comparison
- `--query TEXT` - Custom comparison query
- `--output PATH` - Save comparison result to file
- `--format FORMAT` - Output format (json, html)

**Example:**
```python
from layoutlens.cli import CompareCommand

command = CompareCommand(config)
args = parser.parse_args([
    "old-design.html",
    "new-design.html",
    "--viewport", "desktop",
    "--format", "html"
])
exit_code = command.execute(args)
```

### GenerateCommand

Generate configuration files and test suites.

```python
class GenerateCommand(BaseCommand):
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add generate command arguments with subcommands."""
        
    def execute(self, args: argparse.Namespace) -> int:
        """Execute generate command based on subcommand."""
```

**Command:** `layoutlens generate`

**Subcommands:**
- `config` - Generate configuration file
- `suite` - Generate test suite
- `benchmarks` - Generate benchmark data

#### GenerateConfigCommand

```python
class GenerateConfigCommand:
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        # --output PATH - Output file path
        # --minimal - Generate minimal configuration
        # --with-examples - Include example values
        # --template TEMPLATE - Use specific template
        
    def execute(self, args: argparse.Namespace) -> int:
        # Generate configuration file
```

#### GenerateSuiteCommand

```python
class GenerateSuiteCommand:
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        # --output PATH - Output file path
        # --pages PATTERN - HTML files to include
        # --template TEMPLATE - Suite template
        # --queries TEXT - Default queries
        
    def execute(self, args: argparse.Namespace) -> int:
        # Generate test suite file
```

### ValidateCommand

Validate configuration files and test suites.

```python
class ValidateCommand(BaseCommand):
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add validate command arguments."""
        
    def execute(self, args: argparse.Namespace) -> int:
        """Execute validate command."""
```

**Command:** `layoutlens validate`

**Arguments:**
- `--config PATH` - Configuration file to validate
- `--suite PATH` - Test suite file to validate
- `--strict` - Enable strict validation mode
- `--fix` - Attempt to fix common issues

### InfoCommand

Display system information and diagnostics.

```python
class InfoCommand(BaseCommand):
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add info command arguments."""
        
    def execute(self, args: argparse.Namespace) -> int:
        """Execute info command."""
```

**Command:** `layoutlens info`

**Arguments:**
- `--config` - Show current configuration
- `--system` - Show system information
- `--api` - Test API connectivity
- `--dependencies` - Check dependencies
- `--all` - Show all information

### InitCommand

Initialize a new LayoutLens project.

```python
class InitCommand(BaseCommand):
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add init command arguments."""
        
    def execute(self, args: argparse.Namespace) -> int:
        """Execute init command."""
```

**Command:** `layoutlens init`

**Arguments:**
- `directory` - Project directory (positional, optional)
- `--template TEMPLATE` - Project template
- `--force` - Overwrite existing files
- `--no-examples` - Skip creating example files
- `--git` - Initialize git repository

## Utility Functions

### parse_queries()

Parse comma-separated query string into list.

```python
def parse_queries(queries_str: str) -> List[str]
```

**Parameters:**
- `queries_str` (str): Comma-separated queries string

**Returns:**
- `List[str]`: List of individual queries

**Example:**
```python
from layoutlens.cli import parse_queries

queries = parse_queries("Is the nav visible?, Are buttons clickable?")
# Returns: ["Is the nav visible?", "Are buttons clickable?"]
```

### parse_viewports()

Parse comma-separated viewport names.

```python
def parse_viewports(viewports_str: str) -> List[str]
```

**Parameters:**
- `viewports_str` (str): Comma-separated viewport names

**Returns:**
- `List[str]`: List of viewport names

**Example:**
```python
from layoutlens.cli import parse_viewports

viewports = parse_viewports("desktop,mobile_portrait,tablet")
# Returns: ["desktop", "mobile_portrait", "tablet"]
```

### parse_formats()

Parse comma-separated output formats.

```python
def parse_formats(formats_str: str) -> List[str]
```

**Parameters:**
- `formats_str` (str): Comma-separated format names

**Returns:**
- `List[str]`: List of format names

**Example:**
```python
from layoutlens.cli import parse_formats

formats = parse_formats("json,html,junit")
# Returns: ["json", "html", "junit"]
```

### validate_file_path()

Validate that a file path exists and is readable.

```python
def validate_file_path(path: str) -> str
```

**Parameters:**
- `path` (str): File path to validate

**Returns:**
- `str`: Validated absolute path

**Raises:**
- `argparse.ArgumentTypeError`: If file doesn't exist or isn't readable

**Example:**
```python
from layoutlens.cli import validate_file_path

try:
    validated_path = validate_file_path("homepage.html")
    print(f"Valid file: {validated_path}")
except argparse.ArgumentTypeError as e:
    print(f"Invalid file: {e}")
```

### setup_logging()

Configure logging for CLI usage.

```python
def setup_logging(
    level: str = "INFO",
    verbose: bool = False,
    quiet: bool = False
) -> None
```

**Parameters:**
- `level` (str): Base logging level
- `verbose` (bool): Enable verbose output
- `quiet` (bool): Suppress non-essential output

**Example:**
```python
from layoutlens.cli import setup_logging

# Configure verbose logging
setup_logging(level="DEBUG", verbose=True)

# Configure quiet logging
setup_logging(level="WARNING", quiet=True)
```

## Output Formatting

### OutputFormatter

Base class for formatting CLI output.

```python
class OutputFormatter:
    def __init__(self, format_type: str):
        self.format_type = format_type
    
    @abstractmethod
    def format_results(self, results: Any) -> str:
        """Format results for output."""
```

### JSONOutputFormatter

Format output as JSON.

```python
class JSONOutputFormatter(OutputFormatter):
    def format_results(self, results: Any) -> str:
        """Format results as JSON."""
```

### TableOutputFormatter

Format output as ASCII tables.

```python
class TableOutputFormatter(OutputFormatter):
    def format_results(self, results: Any) -> str:
        """Format results as ASCII table."""
```

### HTMLOutputFormatter

Generate HTML reports.

```python
class HTMLOutputFormatter(OutputFormatter):
    def format_results(self, results: Any) -> str:
        """Format results as HTML report."""
```

## Error Handling

### CLIError

Base exception for CLI-related errors.

```python
class CLIError(Exception):
    """Base exception for CLI errors."""
    pass
```

### CommandError

Exception for command execution errors.

```python
class CommandError(CLIError):
    """Exception for command execution errors."""
    pass
```

### ArgumentError

Exception for argument parsing errors.

```python
class ArgumentError(CLIError):
    """Exception for argument parsing errors."""
    pass
```

## Exit Codes

The CLI uses standard exit codes:

```python
class ExitCode:
    SUCCESS = 0
    GENERAL_ERROR = 1
    CONFIG_ERROR = 2
    TEST_FAILURE = 3
    API_ERROR = 4
    FILE_ERROR = 5
```

**Usage in commands:**
```python
from layoutlens.cli import ExitCode

def execute(self, args) -> int:
    try:
        # Command logic
        return ExitCode.SUCCESS
    except ConfigurationError:
        return ExitCode.CONFIG_ERROR
    except APIError:
        return ExitCode.API_ERROR
    except FileNotFoundError:
        return ExitCode.FILE_ERROR
    except Exception:
        return ExitCode.GENERAL_ERROR
```

## Advanced Usage Examples

### Custom Command Implementation

Create a custom CLI command:

```python
from layoutlens.cli import BaseCommand
from layoutlens import LayoutLens
import argparse

class AnalyzeCommand(BaseCommand):
    """Custom command to analyze HTML files."""
    
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "html_files",
            nargs="+",
            help="HTML files to analyze"
        )
        parser.add_argument(
            "--depth",
            type=str,
            choices=["shallow", "deep"],
            default="shallow",
            help="Analysis depth"
        )
        parser.add_argument(
            "--output",
            type=str,
            help="Output file for analysis results"
        )
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute analysis command."""
        try:
            tester = LayoutLens(config=self.config)
            results = []
            
            for html_file in args.html_files:
                if args.depth == "deep":
                    queries = [
                        "Is the page structure semantically correct?",
                        "Are accessibility guidelines followed?",
                        "Is the visual hierarchy clear?",
                        "Are interactive elements properly styled?"
                    ]
                else:
                    queries = ["Is the page layout functional?"]
                
                result = tester.test_page(html_file, queries=queries)
                results.append(result)
                
                print(f"Analyzed {html_file}: {result.success_rate:.2%} score")
            
            if args.output:
                self._save_analysis(results, args.output)
            
            return 0
            
        except Exception as e:
            print(f"Analysis failed: {e}")
            return 1
    
    def _save_analysis(self, results, output_file):
        """Save analysis results to file."""
        # Implementation details...
        pass

# Register custom command
from layoutlens.cli import register_command
register_command("analyze", AnalyzeCommand)
```

### Programmatic CLI Usage

Use CLI functionality programmatically:

```python
from layoutlens.cli import main, TestCommand
from layoutlens import Config
import io
import sys

def run_tests_programmatically(html_files, queries):
    """Run tests programmatically using CLI infrastructure."""
    
    # Capture output
    old_stdout = sys.stdout
    sys.stdout = captured_output = io.StringIO()
    
    try:
        # Prepare arguments
        args = ["test"]
        for html_file in html_files:
            args.extend(["--page", html_file])
        
        args.extend(["--queries", ",".join(queries)])
        args.extend(["--format", "json"])
        
        # Run CLI
        exit_code = main(args)
        
        # Get output
        output = captured_output.getvalue()
        
        return {
            "exit_code": exit_code,
            "output": output,
            "success": exit_code == 0
        }
        
    finally:
        sys.stdout = old_stdout

# Usage
result = run_tests_programmatically(
    html_files=["homepage.html", "about.html"],
    queries=["Is the layout responsive?", "Are buttons visible?"]
)

if result["success"]:
    print("Tests completed successfully")
    print(result["output"])
else:
    print("Tests failed")
```

### CLI Plugin System

Extend CLI with custom plugins:

```python
from layoutlens.cli import BaseCommand, register_command

class PluginCommand(BaseCommand):
    """Base class for CLI plugins."""
    
    @classmethod
    def register(cls, name: str):
        """Register plugin command."""
        register_command(name, cls)
        return cls

# Example plugin
@PluginCommand.register("accessibility-audit")
class AccessibilityAuditCommand(PluginCommand):
    """Accessibility audit command plugin."""
    
    def add_arguments(self, parser):
        parser.add_argument("html_file", help="HTML file to audit")
        parser.add_argument("--level", choices=["A", "AA", "AAA"], default="AA")
        parser.add_argument("--report", help="Generate detailed report")
    
    def execute(self, args):
        # Accessibility audit implementation
        tester = LayoutLens(config=self.config)
        
        accessibility_queries = [
            "Are headings properly structured (h1, h2, h3, etc.)?",
            "Are form inputs properly labeled?",
            "Is color contrast sufficient for readability?",
            "Are interactive elements keyboard accessible?",
            "Are images provided with alt text?"
        ]
        
        if args.level == "AAA":
            accessibility_queries.extend([
                "Is the text resizable up to 200% without horizontal scrolling?",
                "Are focus indicators clearly visible?",
                "Is the page usable with high contrast mode?"
            ])
        
        result = tester.test_page(args.html_file, queries=accessibility_queries)
        
        print(f"Accessibility Audit Results ({args.level} Level)")
        print(f"Overall Score: {result.success_rate:.2%}")
        
        for test in result.test_results:
            status = "✓" if test.passed else "✗"
            print(f"{status} {test.query}")
        
        if args.report:
            self._generate_accessibility_report(result, args.report)
        
        return 0 if result.success_rate >= 0.8 else 1

# Plugin is automatically available as:
# layoutlens accessibility-audit page.html --level AA --report audit.html
```

### Batch Processing with CLI

Process multiple files efficiently:

```python
import subprocess
import json
import concurrent.futures
from pathlib import Path

def batch_test_with_cli(html_dir, output_dir, max_workers=4):
    """Batch process HTML files using CLI."""
    
    html_files = list(Path(html_dir).glob("**/*.html"))
    results = {}
    
    def test_single_file(html_file):
        """Test a single file using CLI."""
        cmd = [
            "layoutlens", "test",
            "--page", str(html_file),
            "--format", "json",
            "--output-dir", str(output_dir),
            "--quiet"
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                # Parse JSON output
                output_file = output_dir / f"{html_file.stem}_results.json"
                if output_file.exists():
                    with open(output_file) as f:
                        data = json.load(f)
                    return {
                        "file": str(html_file),
                        "success": True,
                        "results": data
                    }
            
            return {
                "file": str(html_file),
                "success": False,
                "error": result.stderr
            }
            
        except subprocess.TimeoutExpired:
            return {
                "file": str(html_file),
                "success": False,
                "error": "Timeout"
            }
    
    # Process files in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {
            executor.submit(test_single_file, html_file): html_file
            for html_file in html_files
        }
        
        for future in concurrent.futures.as_completed(future_to_file):
            result = future.result()
            results[result["file"]] = result
            
            if result["success"]:
                success_rate = result["results"]["summary"]["success_rate"]
                print(f"✓ {result['file']}: {success_rate:.2%}")
            else:
                print(f"✗ {result['file']}: {result['error']}")
    
    return results

# Usage
results = batch_test_with_cli(
    html_dir="./website/pages",
    output_dir="./test-results",
    max_workers=6
)

# Summary
total_files = len(results)
successful_files = sum(1 for r in results.values() if r["success"])
print(f"Processed {successful_files}/{total_files} files successfully")
```

## See Also

- [Core API](core.md) - Main LayoutLens class
- [Configuration API](config.md) - Configuration management
- [Test Runner API](test-runner.md) - Test execution engine
- [CLI Reference](../user-guide/cli-reference.md) - Command-line usage guide