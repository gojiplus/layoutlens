# Changelog

All notable changes to the LayoutLens project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Enhanced LayoutLens framework with modern Python API
- CLI interface with comprehensive commands (`layoutlens`)
- Multi-viewport screenshot testing across desktop, tablet, and mobile
- Intelligent test query generation from HTML DOM analysis
- Comprehensive test suite orchestration with YAML configuration
- Benchmark generation system with systematic HTML templates
- Advanced screenshot management with context managers
- Configuration management with hierarchical settings (files, env vars, params)
- Package distribution setup with proper entry points
- Comprehensive testing framework with mocked dependencies
- CI/CD pipelines for automated testing and release
- Complete documentation structure with user guides and API references

### Changed
- **BREAKING**: Reorganized project structure with clear separation
  - Moved original components to `legacy/` directory
  - Moved benchmark data to `benchmarks/` directory  
  - Moved HTML samples to `tests/fixtures/sample_pages/legacy_samples/`
  - Enhanced framework now in `layoutlens/` package
  - Testing engine in `scripts/testing/`
  - Benchmark tools in `scripts/benchmark/`
- Updated all import paths and references to new structure
- Enhanced error handling with graceful degradation
- Improved API design with backward compatibility maintained

### Enhanced
- Original `LayoutLens.ask()` and `compare_layouts()` methods preserved for compatibility
- Extended API with new methods:
  - `test_page()` - Comprehensive page testing with auto-generated queries
  - `compare_pages()` - Visual comparison with structured results
  - `run_test_suite()` - Execute organized test suites
  - `generate_benchmark_data()` - Create systematic test datasets

### Infrastructure
- GitHub Actions workflows for testing across Python 3.8-3.12
- Automated package building and PyPI publishing
- Code coverage reporting with Codecov integration
- Example validation in CI/CD pipeline
- Comprehensive test fixtures and mock strategies

## [0.1.0] - Initial Release

### Added
- Basic LayoutLens framework for AI-powered UI testing
- Screenshot capture using Playwright
- OpenAI vision model integration for natural language queries
- CSV-based benchmark system
- HTML test samples for various UI patterns
- Simple benchmark runner for automated testing

### Core Features
- `framework.py` - Original LayoutLens class
- `screenshot.py` - HTML to image conversion
- `benchmark_runner.py` - CSV-driven test execution
- Support for single image tests and pairwise comparisons
- Natural language query interface for UI validation

---

## Migration Guide

### From v0.1.0 to v1.0.0

**File Locations:**
- `framework.py` → `legacy/framework.py` 
- `screenshot.py` → `legacy/screenshot.py`
- `benchmark_runner.py` → `legacy/benchmark_runner.py`
- `benchmark.csv` → `benchmarks/benchmark.csv`
- `html/` samples → `tests/fixtures/sample_pages/legacy_samples/`

**Usage Changes:**
```python
# Old usage (still supported)
from legacy.framework import LayoutLens
lens = LayoutLens(api_key="key")
result = lens.ask(["image.png"], "Question?")

# New recommended usage
from layoutlens import LayoutLens
tester = LayoutLens(api_key="key")
result = tester.test_page("page.html", queries=["Question?"])
```

**Command Line:**
```bash
# Old
python benchmark_runner.py

# New
python legacy/benchmark_runner.py
# Or use enhanced CLI
layoutlens test --page page.html
```

All legacy interfaces remain functional for backward compatibility.