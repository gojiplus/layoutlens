# Installation Guide

This guide covers different ways to install LayoutLens and set up your environment for AI-powered UI testing.

## Prerequisites

### System Requirements

- **Python 3.8 or higher** (Python 3.9+ recommended)
- **Operating System**: Windows, macOS, or Linux
- **Memory**: Minimum 4GB RAM (8GB recommended for large test suites)
- **Disk Space**: At least 500MB for installation and browsers

### Required External Services

- **OpenAI API Key** - Required for LLM-powered visual testing
  - Get your API key from [OpenAI's platform](https://platform.openai.com/api-keys)
  - Set usage limits to control costs during testing

## Installation Methods

### Method 1: PyPI Installation (Recommended)

Install the latest stable release from PyPI:

```bash
pip install layoutlens
```

### Method 2: Development Installation

For contributing or using the latest features:

```bash
# Clone the repository
git clone https://github.com/matmulai/layoutlens.git
cd layoutlens

# Install in development mode
pip install -e .
```

### Method 3: With Optional Dependencies

Install with additional development or documentation tools:

```bash
# Install with development dependencies
pip install layoutlens[dev]

# Install with documentation dependencies
pip install layoutlens[docs]

# Install with testing dependencies
pip install layoutlens[test]

# Install all optional dependencies
pip install layoutlens[dev,docs,test]
```

## Post-Installation Setup

### 1. Install Playwright Browsers

LayoutLens uses Playwright for screenshot capture. Install the required browser:

```bash
playwright install chromium
```

**Note**: You only need Chromium for most use cases, but you can install other browsers if needed:

```bash
# Install all browsers (larger download)
playwright install

# Install specific browsers
playwright install firefox webkit
```

### 2. Set Up OpenAI API Key

Configure your OpenAI API key using one of these methods:

**Option A: Environment Variable (Recommended)**
```bash
export OPENAI_API_KEY="your-api-key-here"
```

**Option B: Configuration File**
```yaml
# ~/.layoutlens/config.yaml or project config file
llm:
  provider: "openai"
  api_key: "your-api-key-here"
  model: "gpt-4o-mini"
```

**Option C: Programmatic**
```python
from layoutlens import LayoutLens

tester = LayoutLens(api_key="your-api-key-here")
```

### 3. Verify Installation

Test that everything is working correctly:

```bash
# Check CLI is available
layoutlens --help

# Generate a sample configuration
layoutlens generate config --output test-config.yaml

# Validate the installation
layoutlens validate --config test-config.yaml
```

**Python verification:**
```python
import layoutlens
print(f"LayoutLens version: {layoutlens.__version__}")

# Test basic functionality (requires API key)
tester = layoutlens.LayoutLens()
print("LayoutLens initialized successfully!")
```

## Environment Setup

### Virtual Environment (Recommended)

Always use a virtual environment to avoid dependency conflicts:

```bash
# Create virtual environment
python -m venv layoutlens-env

# Activate virtual environment
# On Windows:
layoutlens-env\Scripts\activate
# On macOS/Linux:
source layoutlens-env/bin/activate

# Install LayoutLens
pip install layoutlens
playwright install chromium
```

### Docker Setup

For containerized environments:

```dockerfile
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install LayoutLens
RUN pip install layoutlens

# Install Playwright and browsers
RUN playwright install-deps
RUN playwright install chromium

# Set working directory
WORKDIR /app

# Your application code
COPY . .

CMD ["layoutlens", "--help"]
```

### GitHub Codespaces / Dev Containers

For development in cloud environments, create `.devcontainer/devcontainer.json`:

```json
{
  "name": "LayoutLens Development",
  "image": "python:3.10",
  "features": {
    "ghcr.io/devcontainers/features/node:1": {}
  },
  "postCreateCommand": "pip install layoutlens[dev] && playwright install chromium",
  "customizations": {
    "vscode": {
      "extensions": ["ms-python.python", "ms-python.flake8"]
    }
  }
}
```

## Configuration

### Project-Level Configuration

Create a configuration file for your project:

```bash
layoutlens generate config --output .layoutlens.yaml
```

Edit the generated configuration:

```yaml
# .layoutlens.yaml
project:
  name: "My UI Tests"
  base_dir: "./tests/ui"

llm:
  provider: "openai"
  model: "gpt-4o-mini"
  api_key: "${OPENAI_API_KEY}"  # Use environment variable

screenshots:
  base_dir: "./test-screenshots"
  format: "png"
  quality: 90

viewports:
  desktop: {width: 1920, height: 1080}
  tablet: {width: 768, height: 1024}
  mobile: {width: 375, height: 667}

output:
  results_dir: "./test-results"
  format: ["json", "html"]
  verbose: true
```

### User-Level Configuration

Create a global configuration file:

```bash
mkdir -p ~/.layoutlens
layoutlens generate config --output ~/.layoutlens/config.yaml
```

## Troubleshooting

### Common Issues

**1. Playwright Installation Issues**
```bash
# Try installing with specific browser
playwright install chromium --force

# Check Playwright installation
playwright --version
```

**2. Permission Issues on Linux/macOS**
```bash
# Install with user flag if getting permission errors
pip install --user layoutlens

# Or fix pip permissions
python -m pip install --user --upgrade pip
```

**3. OpenAI API Issues**
```bash
# Test API key
python -c "
import openai
client = openai.OpenAI(api_key='your-key')
print('API key works!')
"
```

**4. Import Errors**
```bash
# Reinstall in development mode
pip uninstall layoutlens
pip install -e .
```

### System-Specific Instructions

**macOS with Apple Silicon (M1/M2):**
```bash
# Install compatible versions
pip install --upgrade pip
pip install layoutlens
arch -x86_64 playwright install chromium
```

**Ubuntu/Debian:**
```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv
sudo apt-get install -y libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libgtk-3-0

# Install LayoutLens
pip3 install layoutlens
playwright install-deps
playwright install chromium
```

**Windows:**
```powershell
# Use PowerShell or Command Prompt
pip install layoutlens
playwright install chromium

# If you get execution policy errors:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Upgrading

### Upgrade LayoutLens
```bash
pip install --upgrade layoutlens
```

### Upgrade Playwright Browsers
```bash
playwright install chromium --force
```

### Check for Updates
```bash
pip list --outdated | grep layoutlens
```

## Uninstalling

To completely remove LayoutLens:

```bash
# Uninstall the package
pip uninstall layoutlens

# Remove browsers (optional)
playwright uninstall

# Remove configuration files (optional)
rm -rf ~/.layoutlens
rm -f .layoutlens.yaml
```

## Getting Help

If you encounter installation issues:

1. Check the [FAQ](faq.md) for common solutions
2. Search [GitHub Issues](https://github.com/matmulai/layoutlens/issues)
3. Review the [troubleshooting section](../developer-guide/contributing.md#troubleshooting)
4. Create a new issue with:
   - Operating system and version
   - Python version (`python --version`)
   - Installation method used
   - Complete error message
   - Steps to reproduce the issue

## Next Steps

After successful installation:

1. Read the [Quick Start Guide](quickstart.md) to create your first test
2. Explore [Configuration Options](configuration.md) to customize behavior
3. Check out [Examples](examples.md) for common usage patterns
4. Learn about the [CLI Commands](cli-reference.md) for automation