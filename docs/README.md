# LayoutLens Documentation

Comprehensive documentation for the LayoutLens AI-enabled UI testing framework.

## Documentation Structure

### User Documentation
- **[Quick Start Guide](user-guide/quickstart.md)** - Get started in 5 minutes
- **[Installation Guide](user-guide/installation.md)** - Installation and setup
- **[Configuration](user-guide/configuration.md)** - Framework configuration
- **[CLI Reference](user-guide/cli-reference.md)** - Command-line interface
- **[Examples](user-guide/examples.md)** - Usage examples and patterns

### API Documentation  
- **[Core API](api/core.md)** - Main LayoutLens class
- **[Configuration API](api/config.md)** - Configuration management
- **[Test Runner API](api/test-runner.md)** - Test execution
- **[CLI API](api/cli.md)** - Command-line interface

### Developer Documentation
- **[Architecture](developer-guide/architecture.md)** - Framework architecture
- **[Contributing](developer-guide/contributing.md)** - Contribution guidelines
- **[Testing Guide](testing.md)** - Testing framework and guidelines
- **[Development Setup](developer-guide/development.md)** - Development environment

## Quick Links

### Getting Started
```bash
pip install layoutlens
layoutlens --help
```

### Basic Usage
```python
from layoutlens import LayoutLens

tester = LayoutLens()
result = tester.test_page("page.html", queries=["Is the layout responsive?"])
print(f"Success rate: {result.success_rate:.2%}")
```

### CLI Usage  
```bash
# Test a single page
layoutlens test --page homepage.html --queries "Is the logo centered?"

# Run a test suite
layoutlens test --suite tests.yaml --parallel

# Compare pages
layoutlens compare before.html after.html
```

## Support

- **GitHub Issues**: [Report bugs and request features](https://github.com/matmulai/layoutlens/issues)
- **Discussions**: [Community discussions](https://github.com/matmulai/layoutlens/discussions)
- **Documentation**: [Online docs](https://layoutlens.readthedocs.io/)

## Contributing

See [Contributing Guide](developer-guide/contributing.md) for details on:
- Code style and standards
- Testing requirements
- Pull request process
- Development workflow