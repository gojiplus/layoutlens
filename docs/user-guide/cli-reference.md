# CLI Reference

The LayoutLens command-line interface provides comprehensive tools for AI-powered UI testing, configuration management, and test suite execution.

## Global Options

These options are available for all commands:

```bash
layoutlens [GLOBAL OPTIONS] COMMAND [COMMAND OPTIONS]
```

### Global Options

- `--config PATH` - Path to configuration file (default: `.layoutlens.yaml`)
- `--verbose, -v` - Enable verbose output  
- `--quiet, -q` - Suppress non-essential output
- `--help, -h` - Show help message
- `--version` - Show version information

### Configuration Sources

Configuration is loaded from (in order of precedence):
1. Command-line arguments
2. Environment variables (`LAYOUTLENS_*`)
3. Config file specified by `--config`
4. `.layoutlens.yaml` in current directory
5. `~/.layoutlens/config.yaml` (user config)
6. Built-in defaults

## Commands

### `test` - Run UI Tests

Execute visual tests on HTML pages using AI analysis.

```bash
layoutlens test [OPTIONS] [FILES...]
```

#### Options

**Input Sources:**
- `--page PATH` - Test a single HTML page
- `--pages PATTERN` - Test multiple pages using glob pattern
- `--suite PATH` - Run tests from YAML test suite file
- `--stdin` - Read HTML content from stdin

**Test Configuration:**
- `--queries TEXT` - Comma-separated list of test queries
- `--auto-queries / --no-auto-queries` - Enable/disable automatic query generation (default: enabled)
- `--viewports NAMES` - Comma-separated viewport names (default: desktop,mobile_portrait)
- `--parallel / --no-parallel` - Enable/disable parallel execution (default: enabled)
- `--max-workers N` - Number of parallel workers (default: auto)

**Output Options:**
- `--output-dir PATH` - Results output directory (default: ./results)
- `--format FORMAT` - Output format: json,html,junit,xml (default: json,html)
- `--save-screenshots / --no-save-screenshots` - Save screenshots with results (default: enabled)
- `--report-title TEXT` - Custom title for HTML reports

**Advanced Options:**
- `--retry N` - Retry failed tests N times (default: 1)
- `--fail-fast` - Stop on first test failure
- `--timeout SECONDS` - Test timeout in seconds (default: 300)
- `--tags TAGS` - Run only tests with specific tags

#### Examples

```bash
# Test a single page
layoutlens test --page homepage.html --queries "Is the navigation visible?"

# Test multiple pages with pattern
layoutlens test --pages "pages/*.html" --viewports desktop,tablet,mobile

# Run a comprehensive test suite
layoutlens test --suite tests/ui-tests.yaml --parallel --max-workers 4

# Test with custom output
layoutlens test --page app.html --output-dir ./results --format json,html,junit

# Quick mobile test
layoutlens test --page mobile.html --viewports mobile_portrait --no-save-screenshots

# Continuous integration mode
layoutlens test --suite ci-tests.yaml --fail-fast --quiet --format junit
```

### `compare` - Compare Pages

Visually compare two HTML pages to detect differences.

```bash
layoutlens compare [OPTIONS] PAGE_A PAGE_B
```

#### Options

- `--viewport NAME` - Viewport for comparison (default: desktop)
- `--query TEXT` - Custom comparison query (default: "Do these layouts look the same?")
- `--output PATH` - Save comparison result to file
- `--format FORMAT` - Output format: json,html (default: json)
- `--save-screenshots` - Save comparison screenshots

#### Examples

```bash
# Basic comparison
layoutlens compare old-design.html new-design.html

# Mobile comparison with custom query  
layoutlens compare --viewport mobile_portrait \
  --query "Are the mobile layouts functionally equivalent?" \
  before.html after.html

# Save detailed comparison report
layoutlens compare --format html --output comparison-report.html \
  --save-screenshots version1.html version2.html
```

### `generate` - Generate Configurations and Tests

Create configuration files, test suites, and benchmark data.

```bash
layoutlens generate [SUBCOMMAND] [OPTIONS]
```

#### Subcommands

**`config` - Generate Configuration File**

```bash
layoutlens generate config [OPTIONS]
```

Options:
- `--output PATH` - Output file path (default: layoutlens.yaml)
- `--minimal` - Generate minimal configuration
- `--with-examples` - Include example values and comments
- `--template TEMPLATE` - Use specific template: default,ci,development,production

Examples:
```bash
# Generate default configuration
layoutlens generate config --output my-config.yaml

# Generate minimal CI configuration
layoutlens generate config --minimal --template ci --output ci-config.yaml

# Generate with examples and comments
layoutlens generate config --with-examples --output documented-config.yaml
```

**`suite` - Generate Test Suite**

```bash
layoutlens generate suite [OPTIONS]
```

Options:
- `--output PATH` - Output file path (default: test-suite.yaml)
- `--pages PATTERN` - HTML files to include using glob pattern
- `--template TEMPLATE` - Suite template: basic,comprehensive,accessibility,responsive
- `--queries TEXT` - Default queries for all tests

Examples:
```bash
# Generate basic test suite
layoutlens generate suite --output tests.yaml --pages "src/*.html"

# Generate comprehensive accessibility suite
layoutlens generate suite --template accessibility --output a11y-tests.yaml

# Generate with custom queries
layoutlens generate suite --queries "Is the layout responsive?,Are colors accessible?" \
  --output custom-tests.yaml
```

**`benchmarks` - Generate Benchmark Data**

```bash
layoutlens generate benchmarks [OPTIONS]
```

Options:
- `--output-dir PATH` - Output directory for benchmark files (default: ./benchmarks)
- `--categories LIST` - Benchmark categories: typography,layout,color,accessibility
- `--format FORMAT` - Output format: csv,yaml,json (default: csv)
- `--count N` - Number of test cases per category (default: 50)

Examples:
```bash
# Generate comprehensive benchmarks
layoutlens generate benchmarks --categories typography,layout,accessibility

# Generate focused typography benchmarks
layoutlens generate benchmarks --categories typography --count 100 --format yaml
```

### `validate` - Validate Configurations

Validate configuration files, test suites, and project setup.

```bash
layoutlens validate [OPTIONS] [FILES...]
```

#### Options

- `--config PATH` - Configuration file to validate
- `--suite PATH` - Test suite file to validate  
- `--strict` - Enable strict validation mode
- `--fix` - Attempt to fix common issues automatically

#### Examples

```bash
# Validate current project configuration
layoutlens validate

# Validate specific files
layoutlens validate --config my-config.yaml --suite test-suite.yaml

# Strict validation with auto-fix
layoutlens validate --strict --fix
```

### `info` - Show System Information

Display system information, configuration details, and diagnostics.

```bash
layoutlens info [OPTIONS]
```

#### Options

- `--config` - Show current configuration
- `--system` - Show system information
- `--api` - Test API connectivity
- `--dependencies` - Check dependencies
- `--all` - Show all information

#### Examples

```bash
# Show all information
layoutlens info --all

# Check API connectivity
layoutlens info --api

# Debug configuration issues
layoutlens info --config --system
```

### `init` - Initialize Project

Set up a new LayoutLens project with configuration and examples.

```bash
layoutlens init [OPTIONS] [DIRECTORY]
```

#### Options

- `--template TEMPLATE` - Project template: basic,advanced,ci,comprehensive
- `--force` - Overwrite existing files
- `--no-examples` - Skip creating example files
- `--git` - Initialize git repository

#### Examples

```bash
# Initialize in current directory
layoutlens init --template basic

# Initialize new project directory
layoutlens init --template comprehensive my-ui-tests --git

# Minimal setup without examples
layoutlens init --template ci --no-examples
```

## Environment Variables

Override configuration and command options using environment variables:

### API Configuration
```bash
export OPENAI_API_KEY="your-api-key-here"
export LAYOUTLENS_LLM_MODEL="gpt-4o-mini"
export LAYOUTLENS_LLM_TEMPERATURE="0.1"
```

### Execution Settings
```bash
export LAYOUTLENS_TESTING_PARALLEL="true"
export LAYOUTLENS_TESTING_MAX_WORKERS="4"
export LAYOUTLENS_TESTING_TIMEOUT="300"
```

### Output Settings
```bash
export LAYOUTLENS_OUTPUT_FORMAT="json,html"
export LAYOUTLENS_OUTPUT_VERBOSE="true"
export LAYOUTLENS_SCREENSHOTS_SAVE="true"
```

## Exit Codes

The CLI returns standard exit codes:

- `0` - Success
- `1` - General error
- `2` - Configuration error  
- `3` - Test failures detected
- `4` - API/network error
- `5` - File/permission error

Use these in scripts and CI/CD pipelines:

```bash
# Exit on test failures in CI
layoutlens test --suite ci-tests.yaml --fail-fast
if [ $? -ne 0 ]; then
    echo "Tests failed, exiting"
    exit 1
fi

# Continue on test failures but capture exit code
layoutlens test --suite all-tests.yaml
TEST_RESULT=$?
echo "Test exit code: $TEST_RESULT"
```

## Output Formats

### JSON Format

Structured data format for programmatic processing:

```json
{
  "summary": {
    "total_tests": 10,
    "passed_tests": 8,
    "failed_tests": 2,
    "success_rate": 0.8,
    "execution_time": 45.2
  },
  "test_results": [
    {
      "query": "Is the navigation visible?",
      "answer": "Yes, the navigation is clearly visible...",
      "passed": true,
      "confidence": 0.95,
      "viewport": "desktop",
      "execution_time": 2.1
    }
  ]
}
```

### HTML Format

Human-readable report with visual elements:
- Test summary with pass/fail statistics
- Individual test results with screenshots
- Interactive filtering and sorting
- Responsive design for mobile viewing

### JUnit XML Format

Compatible with CI/CD systems and test reporting tools:

```xml
<testsuite tests="10" failures="2" time="45.2" name="LayoutLens Tests">
  <testcase classname="ui.homepage" name="navigation_visibility" time="2.1">
    <system-out>LLM Response: Yes, the navigation is clearly visible...</system-out>
  </testcase>
  <testcase classname="ui.homepage" name="responsive_layout" time="3.5">
    <failure message="Layout not responsive">
      LLM Response: The layout does not adapt properly to mobile...
    </failure>
  </testcase>
</testsuite>
```

## Configuration Files

### Test Suite Format

YAML format for organizing multiple tests:

```yaml
name: "Homepage Test Suite"
description: "Comprehensive testing for homepage layouts"
version: "1.0"

defaults:
  viewports: ["desktop", "mobile_portrait"]
  queries: ["Is the layout visually appealing?"]
  
test_cases:
  - name: "Desktop Navigation"
    html_path: "pages/homepage.html"
    viewports: ["desktop"]
    queries:
      - "Is the navigation menu clearly visible?"
      - "Is the logo positioned correctly?"
    tags: ["navigation", "desktop"]
    
  - name: "Mobile Responsive"
    html_path: "pages/homepage.html"
    viewports: ["mobile_portrait"]
    queries:
      - "Is the mobile menu accessible?"
      - "Is the content readable without scrolling?"
    tags: ["responsive", "mobile"]
    
  - name: "Cross-browser Compatibility"
    html_path: "pages/homepage.html"
    browsers: ["chromium", "firefox", "webkit"]
    queries: ["Does the layout appear consistent?"]
    tags: ["compatibility"]
```

## Usage Patterns

### Development Workflow

```bash
# Initialize new project
layoutlens init --template development my-tests
cd my-tests

# Generate configuration
layoutlens generate config --with-examples

# Create test suite
layoutlens generate suite --pages "src/*.html" --template comprehensive

# Run tests during development
layoutlens test --suite test-suite.yaml --no-parallel --verbose

# Compare before/after changes
layoutlens compare before.html after.html --save-screenshots
```

### CI/CD Integration

```bash
# In CI pipeline (.github/workflows/ui-tests.yml)
- name: Run UI Tests
  run: |
    layoutlens test --suite ci-tests.yaml \
      --fail-fast \
      --format junit \
      --output-dir test-results \
      --quiet
    
- name: Publish Test Results
  uses: dorny/test-reporter@v1
  if: always()
  with:
    name: UI Test Results
    path: test-results/*.xml
    reporter: java-junit
```

### Batch Processing

```bash
# Test all pages in directory
find pages/ -name "*.html" -exec layoutlens test --page {} \;

# Generate reports for multiple suites
for suite in tests/*.yaml; do
  layoutlens test --suite "$suite" --output-dir "results/$(basename "$suite" .yaml)"
done

# Compare multiple versions
for version in v1 v2 v3; do
  layoutlens compare baseline.html "${version}/page.html" \
    --output "comparison-${version}.json"
done
```

## Troubleshooting

### Common Issues

**Command not found:**
```bash
# Ensure LayoutLens is installed and in PATH
pip install layoutlens
which layoutlens
```

**Configuration errors:**
```bash
# Validate configuration file
layoutlens validate --config my-config.yaml

# Check for YAML syntax errors
python -c "import yaml; yaml.safe_load(open('my-config.yaml'))"
```

**API connection issues:**
```bash
# Test API connectivity
layoutlens info --api

# Check API key
echo $OPENAI_API_KEY
```

**Permission errors:**
```bash
# Check file permissions
ls -la .layoutlens.yaml

# Run with appropriate permissions
sudo layoutlens test --page page.html  # if needed
```

### Debug Mode

Enable debug output for troubleshooting:

```bash
# Maximum verbosity
layoutlens --verbose test --page page.html

# Debug configuration loading
LAYOUTLENS_LOGGING_LEVEL=DEBUG layoutlens info --config

# Debug API calls
LAYOUTLENS_LLM_TIMEOUT=60 layoutlens test --page page.html --verbose
```

## Getting Help

### Built-in Help

```bash
# General help
layoutlens --help

# Command-specific help
layoutlens test --help
layoutlens generate --help

# Subcommand help
layoutlens generate config --help
```

### Documentation and Support

- [User Guide](../user-guide/) - Comprehensive usage documentation
- [Examples](../../examples/) - Sample configurations and scripts
- [GitHub Issues](https://github.com/matmulai/layoutlens/issues) - Bug reports and feature requests
- [GitHub Discussions](https://github.com/matmulai/layoutlens/discussions) - Community support