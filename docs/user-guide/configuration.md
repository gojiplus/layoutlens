# Configuration Guide

LayoutLens provides flexible configuration options to customize behavior for your specific testing needs. Configuration can be specified through files, environment variables, or programmatically.

## Configuration Hierarchy

Configuration is loaded in the following order (later values override earlier ones):

1. **Default values** - Built-in sensible defaults
2. **User-level config** - `~/.layoutlens/config.yaml`
3. **Project-level config** - `.layoutlens.yaml` in project root
4. **Environment variables** - `LAYOUTLENS_*` prefixed variables
5. **Constructor parameters** - Direct programmatic configuration
6. **Command-line arguments** - CLI flags and options

## Configuration File Format

Configuration files use YAML format with hierarchical structure:

```yaml
# Basic project information
project:
  name: "My UI Test Suite"
  version: "1.0"
  description: "Automated UI testing for my application"
  base_dir: "./tests/ui"

# LLM provider settings
llm:
  provider: "openai"          # Currently only "openai" supported
  api_key: "${OPENAI_API_KEY}" # Use environment variable
  model: "gpt-4o-mini"        # or "gpt-4o", "gpt-4-turbo", etc.
  temperature: 0.1            # Lower = more consistent
  max_tokens: 1000            # Response length limit
  timeout: 30                 # API timeout in seconds

# Screenshot capture settings
screenshots:
  base_dir: "./screenshots"
  format: "png"               # "png" or "jpeg"
  quality: 90                 # JPEG quality (0-100)
  full_page: true            # Capture full page or viewport only
  wait_for_load: 3           # Seconds to wait after page load
  device_scale_factor: 1     # For high-DPI displays

# Viewport configurations  
viewports:
  desktop:
    width: 1920
    height: 1080
    device_scale_factor: 1
  tablet_portrait:
    width: 768
    height: 1024
    device_scale_factor: 2
  tablet_landscape:
    width: 1024
    height: 768
    device_scale_factor: 2
  mobile_portrait:
    width: 375
    height: 667
    device_scale_factor: 3
  mobile_landscape:
    width: 667
    height: 375
    device_scale_factor: 3

# Test execution settings
testing:
  parallel: true             # Run tests in parallel
  max_workers: 4             # Number of parallel workers
  retry_failed: 1            # Retry failed tests N times
  fail_fast: false          # Stop on first failure
  auto_generate_queries: true # Generate queries from HTML
  query_categories: ["layout", "typography", "accessibility"]

# Output and reporting
output:
  base_dir: "./results"
  formats: ["json", "html"]  # Output formats
  verbose: true              # Detailed logging
  save_screenshots: true     # Keep screenshots in results
  generate_summary: true     # Create summary report

# Logging configuration
logging:
  level: "INFO"              # DEBUG, INFO, WARNING, ERROR
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "./logs/layoutlens.log"
  max_size: "10MB"
  backup_count: 5
```

## Generating Configuration Files

### Generate Default Configuration

Create a configuration file with all default values:

```bash
layoutlens generate config --output my-config.yaml
```

### Generate Minimal Configuration

Create a minimal configuration with only essential settings:

```bash
layoutlens generate config --minimal --output minimal-config.yaml
```

### Generate with Examples

Include example values and comments:

```bash
layoutlens generate config --with-examples --output example-config.yaml
```

## Environment Variables

Override any configuration value using environment variables with the `LAYOUTLENS_` prefix:

```bash
# LLM settings
export LAYOUTLENS_LLM_API_KEY="your-key-here"
export LAYOUTLENS_LLM_MODEL="gpt-4o"
export LAYOUTLENS_LLM_TEMPERATURE="0.0"

# Screenshot settings
export LAYOUTLENS_SCREENSHOTS_FORMAT="jpeg"
export LAYOUTLENS_SCREENSHOTS_QUALITY="95"

# Output settings
export LAYOUTLENS_OUTPUT_VERBOSE="true"
export LAYOUTLENS_OUTPUT_FORMATS="json,html,xml"

# Testing settings
export LAYOUTLENS_TESTING_PARALLEL="false"
export LAYOUTLENS_TESTING_MAX_WORKERS="2"
```

Variable names follow the pattern: `LAYOUTLENS_SECTION_KEY` where:
- `SECTION` is the YAML section (uppercase)
- `KEY` is the setting name (uppercase)
- Nested keys use underscores: `LAYOUTLENS_LLM_API_KEY`

## Programmatic Configuration

### Using Config Class

```python
from layoutlens import Config, LayoutLens

# Create configuration programmatically
config = Config()
config.llm.api_key = "your-api-key"
config.llm.model = "gpt-4o-mini"
config.screenshots.base_dir = "./my-screenshots"
config.output.verbose = True

# Use configuration
tester = LayoutLens(config=config)
```

### Loading from File

```python
from layoutlens import Config, LayoutLens

# Load configuration from file
config = Config.from_file("my-config.yaml")

# Override specific settings
config.testing.parallel = False
config.output.formats = ["json"]

# Use configuration
tester = LayoutLens(config=config)
```

### Direct Constructor Parameters

```python
from layoutlens import LayoutLens

# Pass configuration directly
tester = LayoutLens(
    api_key="your-api-key",
    model="gpt-4o-mini", 
    screenshot_dir="./screenshots",
    results_dir="./results",
    parallel=True
)
```

## Configuration Sections

### Project Section

```yaml
project:
  name: "Project Name"          # Display name for reports
  version: "1.0.0"             # Project version  
  description: "Description"    # Project description
  base_dir: "./tests"          # Base directory for relative paths
  tags: ["ui", "regression"]   # Tags for organization
```

### LLM Section

```yaml
llm:
  provider: "openai"           # LLM provider (currently only OpenAI)
  api_key: "sk-..."           # API key (use environment variable)
  model: "gpt-4o-mini"        # Model name
  temperature: 0.1            # Randomness (0.0-2.0)
  max_tokens: 1000            # Max response length
  timeout: 30                 # Request timeout (seconds)
  retries: 3                  # Retry failed requests
  base_url: null              # Custom API base URL
  organization: null          # OpenAI organization ID
```

### Screenshots Section

```yaml
screenshots:
  base_dir: "./screenshots"   # Directory for screenshots
  format: "png"               # Image format: "png", "jpeg"
  quality: 90                 # JPEG quality (0-100)
  full_page: true            # Full page vs viewport only
  wait_for_load: 3           # Wait after page load (seconds)
  device_scale_factor: 1     # Display scaling
  animations: "disabled"      # Animation handling
  timeout: 30000             # Page load timeout (milliseconds)
```

### Viewports Section

Define custom viewport configurations:

```yaml
viewports:
  # Desktop configurations
  desktop_hd:
    width: 1920
    height: 1080
    device_scale_factor: 1
    user_agent: "Mozilla/5.0 ..."
    
  desktop_4k:
    width: 3840
    height: 2160
    device_scale_factor: 2
    
  # Tablet configurations
  ipad:
    width: 768
    height: 1024
    device_scale_factor: 2
    user_agent: "Mozilla/5.0 (iPad; ...)"
    
  # Mobile configurations
  iphone_13:
    width: 390
    height: 844
    device_scale_factor: 3
    user_agent: "Mozilla/5.0 (iPhone; ...)"
```

### Testing Section

```yaml
testing:
  parallel: true              # Enable parallel execution
  max_workers: 4              # Number of parallel workers (null = auto)
  retry_failed: 1             # Retry failed tests N times
  fail_fast: false           # Stop on first failure
  timeout: 300               # Test timeout (seconds)
  
  # Query generation
  auto_generate_queries: true
  query_categories: 
    - "layout"
    - "typography" 
    - "accessibility"
    - "responsive"
  max_queries_per_page: 10
  
  # Test selection
  include_patterns: ["*.html"]
  exclude_patterns: ["*temp*", "*draft*"]
  tags: []                   # Run only tests with these tags
```

### Output Section

```yaml
output:
  base_dir: "./results"       # Results directory
  formats: ["json", "html"]   # Output formats
  verbose: true              # Verbose logging
  save_screenshots: true     # Include screenshots in results
  generate_summary: true     # Generate summary report
  
  # Report customization
  template: "default"        # Report template
  title: "UI Test Results"   # Report title
  include_metadata: true     # Include test metadata
  
  # File naming
  timestamp_format: "%Y%m%d_%H%M%S"
  result_filename: "results_{timestamp}.{format}"
```

### Logging Section

```yaml
logging:
  level: "INFO"              # Log level: DEBUG, INFO, WARNING, ERROR
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  
  # File logging
  file: "./logs/layoutlens.log"
  max_size: "10MB"           # Log rotation size
  backup_count: 5            # Number of backup files
  
  # Console logging
  console: true              # Log to console
  colors: true               # Colored console output
```

## Validation

### Validate Configuration

Check if your configuration is valid:

```bash
layoutlens validate --config my-config.yaml
```

### Configuration Checking in Code

```python
from layoutlens import Config

try:
    config = Config.from_file("my-config.yaml")
    config.validate()
    print("Configuration is valid!")
except Exception as e:
    print(f"Configuration error: {e}")
```

## Common Configurations

### CI/CD Configuration

Optimized for continuous integration:

```yaml
project:
  name: "CI Test Suite"
  
llm:
  model: "gpt-4o-mini"  # Faster and cheaper
  temperature: 0.0      # Consistent results
  timeout: 15           # Shorter timeout

screenshots:
  format: "jpeg"        # Smaller file size
  quality: 80
  
testing:
  parallel: true
  max_workers: 2        # Conservative for CI
  fail_fast: true       # Stop on first failure
  retry_failed: 0       # No retries in CI

output:
  formats: ["json"]     # Minimal output
  verbose: false
  save_screenshots: false  # Save space

logging:
  level: "WARNING"      # Less verbose
  console: true
  file: null           # No file logging
```

### Development Configuration

Optimized for development and debugging:

```yaml
project:
  name: "Development Tests"
  
llm:
  model: "gpt-4o-mini"
  temperature: 0.1
  timeout: 60           # Longer timeout for debugging

screenshots:
  format: "png"         # Better quality for analysis
  quality: 100
  
testing:
  parallel: false       # Sequential for debugging  
  max_workers: 1
  fail_fast: false      # See all failures
  retry_failed: 0

output:
  formats: ["json", "html"]  # Full reporting
  verbose: true
  save_screenshots: true

logging:
  level: "DEBUG"        # Detailed logging
  console: true
  file: "./debug.log"
```

### Production Configuration

Optimized for production testing:

```yaml
project:
  name: "Production Test Suite"
  
llm:
  model: "gpt-4o"       # Best accuracy
  temperature: 0.05     # Very consistent
  timeout: 30
  retries: 3            # Retry on failures

screenshots:
  format: "png"
  quality: 95
  
testing:
  parallel: true
  max_workers: 8        # Higher parallelism
  retry_failed: 2       # Retry failed tests
  
output:
  formats: ["json", "html", "junit"]  # Multiple formats
  verbose: true
  save_screenshots: true
  generate_summary: true

logging:
  level: "INFO"
  file: "./logs/production.log"
  max_size: "50MB"
  backup_count: 10
```

## Advanced Configuration

### Custom Viewport Presets

Create reusable viewport configurations:

```yaml
viewport_presets:
  # Company standard viewports
  company_desktop: &company_desktop
    width: 1440
    height: 900
    device_scale_factor: 2
    
  company_mobile: &company_mobile
    width: 375
    height: 812
    device_scale_factor: 3

# Use presets in viewport definitions
viewports:
  desktop: *company_desktop
  mobile: *company_mobile
  
  # Override specific properties
  desktop_large:
    <<: *company_desktop
    width: 1920
    height: 1080
```

### Environment-Specific Overrides

```yaml
# Base configuration
base_config: &base
  llm:
    model: "gpt-4o-mini"
    temperature: 0.1
  testing:
    parallel: true

# Environment-specific configurations
environments:
  development:
    <<: *base
    logging:
      level: "DEBUG"
    testing:
      parallel: false
      
  staging:
    <<: *base
    llm:
      model: "gpt-4o"
      
  production:
    <<: *base
    llm:
      model: "gpt-4o"
      retries: 3
    output:
      save_screenshots: false
```

## Configuration Best Practices

### Security

- **Never commit API keys** to version control
- Use environment variables for sensitive information
- Use separate API keys for different environments
- Rotate API keys regularly

### Performance

- Use `gpt-4o-mini` for development and CI
- Use `gpt-4o` for production and critical tests
- Enable parallel testing when possible
- Adjust `max_workers` based on your system capabilities

### Maintainability

- Use configuration files for project settings
- Document custom configurations
- Use consistent naming conventions
- Group related settings logically

### Testing

- Validate configurations in CI/CD
- Test with minimal configurations
- Use different configs for different test suites
- Version your configuration files

## Troubleshooting Configuration

### Common Issues

**Configuration not found:**
```bash
# Check file path and permissions
ls -la .layoutlens.yaml
layoutlens validate --config .layoutlens.yaml
```

**Environment variables not working:**
```bash
# Check variable names and values
env | grep LAYOUTLENS
```

**Invalid YAML syntax:**
```bash
# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('config.yaml'))"
```

**API key issues:**
```bash
# Test API key separately
python -c "import openai; print(openai.OpenAI(api_key='$OPENAI_API_KEY').models.list())"
```

## Getting Help

For configuration questions:

1. Check the [examples directory](../../examples/) for sample configurations
2. Review the [CLI reference](cli-reference.md) for command-line options
3. See the [FAQ](faq.md) for common configuration questions
4. Ask in [GitHub Discussions](https://github.com/matmulai/layoutlens/discussions)