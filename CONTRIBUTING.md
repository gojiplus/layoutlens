# Contributing to LayoutLens

We welcome contributions to LayoutLens! This document provides guidelines for contributing to the project.

## Development Setup

### Prerequisites

1. **Python 3.8+** - LayoutLens supports Python 3.8 through 3.12
2. **Git** - For version control
3. **OpenAI API Key** - For testing LLM functionality (optional for development)

### Installation

1. Fork and clone the repository:
```bash
git clone https://github.com/yourusername/layoutlens.git
cd layoutlens
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install in development mode:
```bash
pip install -e .
pip install pytest pytest-cov pytest-mock playwright beautifulsoup4 pyyaml
```

4. Install Playwright browsers:
```bash
playwright install chromium
```

5. Set up pre-commit hooks (optional but recommended):
```bash
pip install pre-commit
pre-commit install
```

## Project Structure

```
layoutlens/
├── layoutlens/           # Main package
│   ├── core.py          # Enhanced LayoutLens class
│   ├── config.py        # Configuration management
│   ├── cli.py           # Command-line interface
│   └── test_runner.py   # Test execution engine
├── scripts/             # Testing and benchmark tools
│   ├── testing/         # Page testing orchestration
│   └── benchmark/       # Benchmark generation
├── legacy/              # Original/legacy components
├── tests/               # Test suite
├── docs/                # Documentation
├── examples/            # Usage examples
└── benchmarks/          # Benchmark datasets
```

## Development Workflow

### 1. Create a Branch

Create a feature branch for your work:
```bash
git checkout -b feature/your-feature-name
```

### 2. Development Standards

#### Code Style
- Follow PEP 8 for Python code style
- Use type hints for function parameters and return values
- Write docstrings for all public functions and classes
- Keep line length under 88 characters (Black formatter standard)

#### Documentation
- Update docstrings when modifying function signatures
- Add examples to docstrings for complex functionality
- Update relevant documentation files when adding features

#### Testing Requirements
- Write unit tests for all new functionality
- Ensure test coverage remains above 85%
- Mock external dependencies (OpenAI API, Playwright, file operations)
- Use descriptive test names that explain what is being tested

### 3. Running Tests

Run the full test suite:
```bash
pytest tests/ -v
```

Run specific test categories:
```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# With coverage report
pytest tests/ -v --cov=layoutlens --cov-report=term-missing
```

Run tests with different Python versions using tox:
```bash
pip install tox
tox
```

### 4. Manual Testing

Test the CLI interface:
```bash
# Generate configuration
layoutlens generate config --output test_config.yaml

# Test a page (requires HTML file)
layoutlens test --page examples/sample.html --queries "Is the text visible?"

# Run validation
layoutlens validate --config test_config.yaml
```

## Contributing Guidelines

### Pull Request Process

1. **Update Documentation**: Ensure all new features are documented
2. **Add Tests**: Include comprehensive tests for new functionality
3. **Update CHANGELOG.md**: Add your changes to the `[Unreleased]` section
4. **Run Tests**: Ensure all tests pass locally
5. **Create Pull Request**: Provide a clear description of changes

### Pull Request Template

```markdown
## Description
Brief description of the changes made.

## Type of Change
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing
- [ ] Tests pass locally
- [ ] New tests added for new functionality
- [ ] Manual testing completed

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review of code completed
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
```

### Code Review Process

1. All pull requests require review from at least one maintainer
2. Address all review comments before merging
3. Ensure CI/CD pipeline passes (all GitHub Actions)
4. Squash commits when merging to keep history clean

## Types of Contributions

### Bug Reports

When reporting bugs, please include:
- Python version and operating system
- Steps to reproduce the issue
- Expected vs actual behavior
- Error messages or logs
- Minimal code example if possible

### Feature Requests

For feature requests, please provide:
- Clear description of the feature
- Use cases and motivation
- Proposed API design (if applicable)
- Implementation considerations

### Documentation Improvements

- Fix typos and grammar
- Improve code examples
- Add missing documentation
- Enhance API documentation

### Code Contributions

Priority areas for contributions:
- Additional viewport configurations
- New query generation strategies
- Enhanced screenshot capture options
- Extended benchmark templates
- Performance optimizations
- Additional LLM provider integrations

## Architecture Guidelines

### Design Principles

1. **Modularity**: Keep components loosely coupled
2. **Extensibility**: Design for easy extension and customization
3. **Reliability**: Graceful error handling and fallback behavior
4. **Performance**: Efficient resource usage and parallel execution
5. **Usability**: Simple, intuitive APIs for end users

### Adding New Features

When adding new features:
1. Consider backward compatibility
2. Design for testability
3. Follow existing patterns and conventions
4. Add configuration options when appropriate
5. Provide clear error messages

### External Dependencies

When adding new dependencies:
1. Ensure they are well-maintained and stable
2. Pin versions in requirements
3. Consider impact on installation size
4. Add to both setup.py and pyproject.toml
5. Update CI/CD configurations

## Release Process

### Version Numbering

We follow [Semantic Versioning](https://semver.org/):
- **Major** (X.0.0): Breaking changes
- **Minor** (0.X.0): New features, backward compatible
- **Patch** (0.0.X): Bug fixes, backward compatible

### Release Checklist

1. Update CHANGELOG.md with release notes
2. Update version in pyproject.toml and __init__.py
3. Create and push version tag: `git tag -a v1.0.0 -m "Release v1.0.0"`
4. GitHub Actions will handle PyPI publishing and GitHub release creation

## Getting Help

- **Documentation**: Check the [docs/](docs/) directory
- **Discussions**: Use GitHub Discussions for questions
- **Issues**: Report bugs and request features via GitHub Issues
- **Contact**: Reach out to maintainers for urgent matters

## Code of Conduct

Please note that this project is released with a Contributor Code of Conduct. By participating in this project, you agree to abide by its terms.

Thank you for contributing to LayoutLens! 🎉