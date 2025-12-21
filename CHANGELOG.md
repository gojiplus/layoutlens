# Changelog

All notable changes to LayoutLens are documented in this file.

## [1.4.0] - 2024-12-21

### 🚀 Major Changes
- **LiteLLM Integration**: Complete migration to LiteLLM as the unified provider
  - Removed OpenRouter provider in favor of LiteLLM's unified interface
  - Support for OpenAI, Anthropic, Google via LiteLLM's standardized API
  - Simplified architecture with single provider handling all models
  - Model naming follows LiteLLM conventions (e.g., "anthropic/claude-3-5-sonnet")

### 🎯 Breaking Changes
- **No backward compatibility** for OpenRouter provider
- Removed `openrouter` from provider choices
- Updated default provider to `openai` (via LiteLLM)
- Changed API key environment variable references (removed OPENROUTER_API_KEY)

### 🔧 Updated Provider Support
- **Provider Options**: `openai`, `anthropic`, `google`, `gemini`, `litellm`
- **Unified Interface**: All providers use LiteLLM for consistent behavior
- **Model Format**: LiteLLM naming convention for all models

## [1.3.0] - 2024-01-21

### 🚀 Major Features Added
- **Multi-Provider Support**: Complete plugin architecture for AI providers
  - LiteLLM integration for unified access to 25+ AI models
  - Support for OpenAI, Anthropic Claude, Google Gemini, and more
  - Factory pattern for easy provider instantiation and management
  - Backward compatibility with existing OpenAI-only code

### 🎯 Interactive Mode
- **Interactive CLI**: New `layoutlens interactive` command for real-time analysis
  - Session statistics and progress tracking
  - Rich terminal formatting (optional, falls back gracefully)
  - Live progress indicators and error handling
  - Command history and help system

### 🔧 Enhanced CLI Experience
- **Provider Selection**: `--provider` flag with choices (litellm, openai, anthropic, google, gemini)
- **Model Selection**: `--model` flag for specifying exact models
- **Enhanced Info Command**: Shows available providers, models, and API key status
- **Unified API Keys**: Support for OPENAI_API_KEY environment variable

### 🏗️ Architecture Improvements
- **Provider Architecture**: Abstract base classes with unified interface
  - VisionProvider, VisionProviderConfig, VisionAnalysisRequest/Response
  - LiteLLMProvider as unified gateway to multiple AI services
  - Extensible factory pattern for adding new providers

### 📦 Dependencies
- **Optional Rich Support**: Enhanced interactive mode with `pip install layoutlens[interactive]`
- **OpenAI SDK**: Single dependency for all provider communication via OpenRouter

### 🧪 Testing
- **Comprehensive Provider Tests**: 40+ tests covering provider architecture
- **Integration Tests**: Full API integration with provider system
- **Interactive Mode Tests**: Session management and progress tracking
- **Backward Compatibility**: Ensures existing code continues to work

## [1.2.0] - 2024-01-20

### 🚀 Major Features Added
- **Async Processing**: Added high-performance async analysis methods
  - `analyze_async()` - Single page async analysis
  - `analyze_batch_async()` - Concurrent batch processing with configurable limits
  - 3-5x performance improvement for batch operations
  - Semaphore-based concurrency control to prevent API overload

### 🔧 CLI Enhancements
- Added `--async` flag to main CLI for async processing
- Added `--max-concurrent` parameter for concurrency control
- New dedicated `layoutlens-async` CLI with enhanced batch commands
- Added async support to test and compare commands

### 📚 Documentation
- Updated README with async examples and performance metrics
- Added comprehensive async usage examples
- Updated CLI help text with async command examples

### 🐛 Bug Fixes
- Fixed pytest class name conflicts (TestCase → UITestCase, etc.)
- Enhanced error handling in batch operations
- Improved type annotations for Python 3.11+ compatibility

### 🔧 Developer Experience
- Enhanced pre-commit hooks with full CI/CD integration
- Improved GitHub Actions workflows (ci.yml, docs.yml, python-publish.yml)
- Added performance benchmarking tests
- Clean up of unused imports and linting improvements

## [1.1.0] - 2024-01-15

### ✨ Features Added
- Production-ready test suites with `UITestCase` and `UITestSuite`
- Smart caching system with memory and file backends
- Comprehensive exception hierarchy for better error handling
- Enhanced CLI with regression testing commands

### 🔧 Improvements
- Modernized type annotations for Python 3.11+
- GitHub Pages documentation with Furo theme
- Comprehensive integration tests with mocked OpenAI API
- Pre-commit hooks and local CI/CD setup

### 🐛 Bug Fixes
- Fixed CLI regression command implementation
- Improved error handling across the codebase
- Better resource management and cleanup

## [1.0.2] - 2024-01-10

### 🔒 Security
- **CRITICAL**: Fixed API key logging vulnerability in CLI
- Enhanced security practices across the codebase

### 🐛 Bug Fixes
- CLI no longer exposes API keys in logs
- Improved error handling for missing dependencies

## [1.0.1] - 2024-01-05

### 🐛 Bug Fixes
- Fixed import issues in certain environments
- Improved error messages for missing API keys
- Better handling of screenshot capture failures

## [1.0.0] - 2024-01-01

### 🎉 Initial Release
- Core LayoutLens functionality for UI testing
- Natural language visual analysis using GPT-4 Vision API
- Screenshot capture with Playwright
- Accessibility and mobile-friendly checks
- Basic CLI commands (test, compare, generate)
- Support for multiple viewports and queries
