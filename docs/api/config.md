# Configuration API Reference

The configuration module provides flexible configuration management for LayoutLens, supporting multiple configuration sources and hierarchical settings.

## Config Class

The main configuration class that manages all LayoutLens settings.

### Constructor

```python
class Config:
    def __init__(
        self,
        config_file: Optional[str] = None,
        **kwargs: Any
    )
```

**Parameters:**
- `config_file` (str, optional): Path to YAML configuration file
- `**kwargs`: Additional configuration overrides

**Example:**
```python
from layoutlens import Config

# Load from default locations
config = Config()

# Load from specific file
config = Config("my-config.yaml")

# Load with overrides
config = Config(
    config_file="base-config.yaml",
    llm_model="gpt-4o",
    testing_parallel=True
)
```

### Class Methods

#### from_file()

Load configuration from a YAML file.

```python
@classmethod
def from_file(cls, config_file: str) -> 'Config'
```

**Parameters:**
- `config_file` (str): Path to YAML configuration file

**Returns:**
- `Config`: Configuration instance loaded from file

**Example:**
```python
config = Config.from_file("production-config.yaml")
```

#### from_dict()

Create configuration from a dictionary.

```python
@classmethod
def from_dict(cls, config_dict: Dict[str, Any]) -> 'Config'
```

**Parameters:**
- `config_dict` (Dict): Configuration dictionary

**Returns:**
- `Config`: Configuration instance

**Example:**
```python
config_dict = {
    "llm": {
        "model": "gpt-4o-mini",
        "temperature": 0.1
    },
    "testing": {
        "parallel": True,
        "max_workers": 4
    }
}
config = Config.from_dict(config_dict)
```

#### generate_default()

Generate a default configuration file.

```python
@classmethod
def generate_default(
    cls,
    output_path: str = "layoutlens.yaml",
    minimal: bool = False,
    with_examples: bool = False
) -> str
```

**Parameters:**
- `output_path` (str): Path for generated configuration file
- `minimal` (bool): Generate minimal configuration
- `with_examples` (bool): Include example values and comments

**Returns:**
- `str`: Path to generated configuration file

**Example:**
```python
# Generate full configuration with examples
Config.generate_default(
    output_path="my-config.yaml",
    with_examples=True
)

# Generate minimal configuration
Config.generate_default(
    output_path="minimal-config.yaml",
    minimal=True
)
```

### Instance Methods

#### save_to_file()

Save current configuration to a YAML file.

```python
def save_to_file(self, file_path: str) -> None
```

**Parameters:**
- `file_path` (str): Path to save configuration file

**Example:**
```python
config = Config()
config.llm.model = "gpt-4o"
config.testing.parallel = True
config.save_to_file("updated-config.yaml")
```

#### validate()

Validate the current configuration.

```python
def validate(self) -> None
```

**Raises:**
- `ConfigurationError`: If configuration is invalid

**Example:**
```python
try:
    config.validate()
    print("Configuration is valid")
except ConfigurationError as e:
    print(f"Configuration error: {e}")
```

#### merge()

Merge another configuration into this one.

```python
def merge(self, other: 'Config') -> 'Config'
```

**Parameters:**
- `other` (Config): Configuration to merge

**Returns:**
- `Config`: New merged configuration

**Example:**
```python
base_config = Config.from_file("base.yaml")
override_config = Config.from_file("overrides.yaml")
final_config = base_config.merge(override_config)
```

#### to_dict()

Convert configuration to dictionary.

```python
def to_dict(self) -> Dict[str, Any]
```

**Returns:**
- `Dict[str, Any]`: Configuration as dictionary

**Example:**
```python
config = Config()
config_dict = config.to_dict()
print(config_dict["llm"]["model"])
```

## Configuration Sections

### ProjectConfig

Project-level configuration settings.

```python
@dataclass
class ProjectConfig:
    name: str = "LayoutLens Project"
    version: str = "1.0"
    description: str = ""
    base_dir: str = "."
    tags: List[str] = field(default_factory=list)
```

**Attributes:**
- `name`: Project display name
- `version`: Project version
- `description`: Project description
- `base_dir`: Base directory for relative paths
- `tags`: Project tags for organization

**Example:**
```python
config.project.name = "E-commerce UI Tests"
config.project.version = "2.1"
config.project.description = "Comprehensive UI testing for online store"
config.project.base_dir = "./tests"
config.project.tags = ["ui", "regression", "accessibility"]
```

### LLMConfig

Language model configuration.

```python
@dataclass
class LLMConfig:
    provider: str = "openai"
    api_key: Optional[str] = None
    model: str = "gpt-4o-mini"
    temperature: float = 0.1
    max_tokens: int = 1000
    timeout: int = 30
    retries: int = 3
    base_url: Optional[str] = None
    organization: Optional[str] = None
```

**Attributes:**
- `provider`: LLM provider ("openai")
- `api_key`: API key (loaded from environment if None)
- `model`: Model name
- `temperature`: Response randomness (0.0-2.0)
- `max_tokens`: Maximum response length
- `timeout`: Request timeout in seconds
- `retries`: Number of retry attempts
- `base_url`: Custom API base URL
- `organization`: OpenAI organization ID

**Example:**
```python
config.llm.model = "gpt-4o"
config.llm.temperature = 0.05  # More consistent
config.llm.max_tokens = 1500
config.llm.timeout = 60
config.llm.retries = 5
```

### ScreenshotConfig

Screenshot capture configuration.

```python
@dataclass
class ScreenshotConfig:
    base_dir: str = "screenshots"
    format: str = "png"
    quality: int = 90
    full_page: bool = True
    wait_for_load: int = 3
    device_scale_factor: int = 1
    animations: str = "disabled"
    timeout: int = 30000
```

**Attributes:**
- `base_dir`: Directory for screenshots
- `format`: Image format ("png" or "jpeg")
- `quality`: JPEG quality (0-100)
- `full_page`: Capture full page vs viewport only
- `wait_for_load`: Wait time after page load (seconds)
- `device_scale_factor`: Display scaling factor
- `animations`: Animation handling ("disabled", "allow")
- `timeout`: Page load timeout (milliseconds)

**Example:**
```python
config.screenshots.base_dir = "./test-screenshots"
config.screenshots.format = "jpeg"
config.screenshots.quality = 85
config.screenshots.wait_for_load = 5
config.screenshots.device_scale_factor = 2
```

### ViewportConfig

Individual viewport configuration.

```python
@dataclass
class ViewportConfig:
    name: str
    width: int
    height: int
    device_scale_factor: int = 1
    is_mobile: bool = False
    has_touch: bool = False
    user_agent: Optional[str] = None
```

**Attributes:**
- `name`: Viewport identifier
- `width`: Screen width in pixels
- `height`: Screen height in pixels
- `device_scale_factor`: Display scaling factor
- `is_mobile`: Whether this is a mobile viewport
- `has_touch`: Whether touch events are enabled
- `user_agent`: Custom user agent string

**Example:**
```python
from layoutlens.config import ViewportConfig

# Define custom viewport
custom_viewport = ViewportConfig(
    name="tablet_landscape",
    width=1024,
    height=768,
    device_scale_factor=2,
    is_mobile=True,
    has_touch=True
)

# Add to configuration
config.viewports["tablet_landscape"] = custom_viewport
```

### TestingConfig

Test execution configuration.

```python
@dataclass
class TestingConfig:
    parallel: bool = True
    max_workers: Optional[int] = None
    retry_failed: int = 1
    fail_fast: bool = False
    timeout: int = 300
    auto_generate_queries: bool = True
    query_categories: List[str] = field(default_factory=lambda: ["layout", "typography", "accessibility"])
    max_queries_per_page: int = 10
    include_patterns: List[str] = field(default_factory=lambda: ["*.html"])
    exclude_patterns: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
```

**Attributes:**
- `parallel`: Enable parallel execution
- `max_workers`: Number of parallel workers (None = auto)
- `retry_failed`: Retry failed tests N times
- `fail_fast`: Stop on first failure
- `timeout`: Test timeout in seconds
- `auto_generate_queries`: Generate queries from HTML analysis
- `query_categories`: Categories for auto-generated queries
- `max_queries_per_page`: Limit auto-generated queries
- `include_patterns`: File patterns to include
- `exclude_patterns`: File patterns to exclude
- `tags`: Only run tests with these tags

**Example:**
```python
config.testing.parallel = True
config.testing.max_workers = 6
config.testing.retry_failed = 2
config.testing.fail_fast = True
config.testing.timeout = 600
config.testing.query_categories = ["layout", "accessibility", "responsive"]
config.testing.exclude_patterns = ["*temp*", "*draft*"]
```

### OutputConfig

Output and reporting configuration.

```python
@dataclass
class OutputConfig:
    base_dir: str = "results"
    formats: List[str] = field(default_factory=lambda: ["json", "html"])
    verbose: bool = True
    save_screenshots: bool = True
    generate_summary: bool = True
    template: str = "default"
    title: str = "LayoutLens Test Results"
    include_metadata: bool = True
    timestamp_format: str = "%Y%m%d_%H%M%S"
    result_filename: str = "results_{timestamp}.{format}"
```

**Attributes:**
- `base_dir`: Results output directory
- `formats`: Output formats (json, html, junit, xml)
- `verbose`: Verbose logging
- `save_screenshots`: Include screenshots in results
- `generate_summary`: Generate summary report
- `template`: Report template name
- `title`: Report title
- `include_metadata`: Include test metadata
- `timestamp_format`: Timestamp format for filenames
- `result_filename`: Result filename template

**Example:**
```python
config.output.base_dir = "./test-results"
config.output.formats = ["json", "html", "junit"]
config.output.verbose = False
config.output.title = "E-commerce UI Test Results"
config.output.result_filename = "{title}_{timestamp}.{format}"
```

### LoggingConfig

Logging configuration.

```python
@dataclass
class LoggingConfig:
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: Optional[str] = None
    max_size: str = "10MB"
    backup_count: int = 5
    console: bool = True
    colors: bool = True
```

**Attributes:**
- `level`: Log level (DEBUG, INFO, WARNING, ERROR)
- `format`: Log message format
- `file`: Log file path (None = no file logging)
- `max_size`: Log rotation size
- `backup_count`: Number of backup log files
- `console`: Enable console logging
- `colors`: Enable colored console output

**Example:**
```python
config.logging.level = "DEBUG"
config.logging.file = "./logs/layoutlens.log"
config.logging.max_size = "50MB"
config.logging.backup_count = 10
config.logging.colors = False
```

## Viewport Presets

The configuration includes several built-in viewport presets:

```python
VIEWPORT_PRESETS = {
    "desktop": ViewportConfig(
        name="desktop",
        width=1920,
        height=1080,
        device_scale_factor=1
    ),
    "desktop_small": ViewportConfig(
        name="desktop_small", 
        width=1366,
        height=768,
        device_scale_factor=1
    ),
    "tablet_portrait": ViewportConfig(
        name="tablet_portrait",
        width=768,
        height=1024,
        device_scale_factor=2,
        is_mobile=True,
        has_touch=True
    ),
    "tablet_landscape": ViewportConfig(
        name="tablet_landscape",
        width=1024,
        height=768,
        device_scale_factor=2,
        is_mobile=True,
        has_touch=True
    ),
    "mobile_portrait": ViewportConfig(
        name="mobile_portrait",
        width=375,
        height=667,
        device_scale_factor=3,
        is_mobile=True,
        has_touch=True
    ),
    "mobile_landscape": ViewportConfig(
        name="mobile_landscape",
        width=667,
        height=375,
        device_scale_factor=3,
        is_mobile=True,
        has_touch=True
    )
}
```

Access viewport presets:

```python
from layoutlens.config import VIEWPORT_PRESETS

# Use preset viewport
config.viewports = {
    "desktop": VIEWPORT_PRESETS["desktop"],
    "mobile": VIEWPORT_PRESETS["mobile_portrait"]
}

# Customize preset
custom_desktop = VIEWPORT_PRESETS["desktop"]
custom_desktop.width = 2560
custom_desktop.height = 1440
config.viewports["desktop_4k"] = custom_desktop
```

## Environment Variable Loading

Configuration automatically loads from environment variables with the `LAYOUTLENS_` prefix:

```python
# Environment variable mappings
LAYOUTLENS_LLM_API_KEY -> config.llm.api_key
LAYOUTLENS_LLM_MODEL -> config.llm.model
LAYOUTLENS_LLM_TEMPERATURE -> config.llm.temperature
LAYOUTLENS_SCREENSHOTS_FORMAT -> config.screenshots.format
LAYOUTLENS_TESTING_PARALLEL -> config.testing.parallel
LAYOUTLENS_OUTPUT_VERBOSE -> config.output.verbose
```

**Example:**
```bash
# Set via environment
export LAYOUTLENS_LLM_MODEL="gpt-4o"
export LAYOUTLENS_TESTING_MAX_WORKERS="8"
export LAYOUTLENS_OUTPUT_FORMATS="json,junit"

# Configuration will automatically load these values
python -c "
from layoutlens import Config
config = Config()
print(config.llm.model)  # gpt-4o
print(config.testing.max_workers)  # 8
print(config.output.formats)  # ['json', 'junit']
"
```

## Configuration File Examples

### Basic Configuration

```yaml
# basic-config.yaml
project:
  name: "Website UI Tests"
  
llm:
  model: "gpt-4o-mini"
  temperature: 0.1
  
screenshots:
  format: "png"
  wait_for_load: 3
  
testing:
  parallel: true
  auto_generate_queries: true
  
output:
  formats: ["json", "html"]
  verbose: true
```

### Production Configuration

```yaml
# production-config.yaml
project:
  name: "Production UI Testing"
  version: "2.0"
  description: "Automated visual testing for production website"
  
llm:
  provider: "openai"
  model: "gpt-4o"
  temperature: 0.05
  max_tokens: 1500
  timeout: 60
  retries: 5
  
screenshots:
  base_dir: "./production-screenshots"
  format: "png"
  quality: 95
  full_page: true
  wait_for_load: 5
  device_scale_factor: 1
  
viewports:
  desktop_hd:
    width: 1920
    height: 1080
    device_scale_factor: 1
  mobile_iphone:
    width: 375
    height: 812
    device_scale_factor: 3
    is_mobile: true
    has_touch: true
    
testing:
  parallel: true
  max_workers: 4
  retry_failed: 2
  timeout: 600
  auto_generate_queries: true
  query_categories: ["layout", "typography", "accessibility", "responsive"]
  max_queries_per_page: 15
  
output:
  base_dir: "./production-results"
  formats: ["json", "html", "junit"]
  verbose: true
  save_screenshots: true
  generate_summary: true
  title: "Production UI Test Results"
  
logging:
  level: "INFO"
  file: "./logs/production-tests.log"
  max_size: "100MB"
  backup_count: 10
```

### Development Configuration

```yaml
# development-config.yaml
project:
  name: "Development UI Tests"
  
llm:
  model: "gpt-4o-mini"
  temperature: 0.2
  timeout: 120
  
screenshots:
  base_dir: "./dev-screenshots"
  format: "jpeg"
  quality: 80
  wait_for_load: 2
  
testing:
  parallel: false  # Easier debugging
  retry_failed: 0
  fail_fast: false
  auto_generate_queries: true
  query_categories: ["layout", "typography"]
  
output:
  formats: ["json"]
  verbose: true
  save_screenshots: true
  
logging:
  level: "DEBUG"
  console: true
  colors: true
```

## Usage Examples

### Basic Configuration Usage

```python
from layoutlens import Config, LayoutLens

# Load configuration
config = Config.from_file("my-config.yaml")

# Modify settings
config.llm.model = "gpt-4o"
config.testing.max_workers = 6

# Use with LayoutLens
tester = LayoutLens(config=config)
result = tester.test_page("homepage.html")
```

### Dynamic Configuration

```python
from layoutlens import Config
import os

# Create configuration based on environment
environment = os.getenv("ENVIRONMENT", "development")

if environment == "production":
    config = Config.from_file("production-config.yaml")
    config.llm.model = "gpt-4o"  # Higher accuracy
    config.testing.retry_failed = 3
elif environment == "ci":
    config = Config()
    config.llm.model = "gpt-4o-mini"  # Faster/cheaper
    config.testing.parallel = True
    config.testing.fail_fast = True
    config.output.formats = ["junit"]
else:  # development
    config = Config()
    config.testing.parallel = False
    config.logging.level = "DEBUG"
    config.output.verbose = True

# Use configuration
tester = LayoutLens(config=config)
```

### Configuration Validation

```python
from layoutlens import Config, ConfigurationError

def load_and_validate_config(config_path: str) -> Config:
    """Load and validate configuration with error handling."""
    try:
        config = Config.from_file(config_path)
        config.validate()
        return config
    except FileNotFoundError:
        print(f"Configuration file not found: {config_path}")
        print("Using default configuration")
        return Config()
    except ConfigurationError as e:
        print(f"Configuration error: {e}")
        print("Please fix the configuration file")
        raise
    except Exception as e:
        print(f"Unexpected error loading configuration: {e}")
        raise

# Usage
config = load_and_validate_config("my-config.yaml")
tester = LayoutLens(config=config)
```

## See Also

- [Core API](core.md) - Main LayoutLens class
- [Test Runner API](test-runner.md) - Test execution engine
- [User Guide - Configuration](../user-guide/configuration.md) - Configuration guide
- [CLI Reference](../user-guide/cli-reference.md) - Command-line configuration