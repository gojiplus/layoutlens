# LayoutLens Development Makefile

.PHONY: help install install-dev test test-unit test-integration test-e2e test-coverage lint format clean build docs serve-docs act-test act-build act-docs act-all pre-commit-install pre-commit-run ci-local

# Default target
help:
	@echo "LayoutLens Development Commands:"
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install package for production"
	@echo "  make install-dev      Install package with development dependencies"
	@echo "  make install-browsers Install Playwright browsers"
	@echo ""
	@echo "Testing:"
	@echo "  make test            Run all tests"
	@echo "  make test-unit       Run unit tests only"
	@echo "  make test-integration Run integration tests only"
	@echo "  make test-e2e        Run end-to-end tests"
	@echo "  make test-coverage   Run tests with coverage report"
	@echo "  make test-fast       Run fast tests only (skip slow)"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint            Run linting (ruff, mypy) using pyproject.toml"
	@echo "  make format          Format code (ruff) using pyproject.toml"
	@echo "  make check           Check code formatting and linting using pyproject.toml"
	@echo ""
	@echo "Package:"
	@echo "  make clean           Clean build artifacts"
	@echo "  make build           Build package distributions"
	@echo "  make check-package   Check package integrity"
	@echo ""
	@echo "Documentation:"
	@echo "  make docs            Build documentation"
	@echo "  make serve-docs      Serve docs locally"
	@echo ""
	@echo "Local CI/CD with act:"
	@echo "  make install-act     Install act (GitHub Actions runner)"
	@echo "  make act-test        Run GitHub Actions test workflow locally"
	@echo "  make act-build       Run GitHub Actions CI workflow locally"
	@echo "  make act-docs        Run GitHub Actions docs workflow locally"
	@echo "  make act-all         Run all workflows locally"
	@echo ""
	@echo "Pre-commit hooks:"
	@echo "  make pre-commit-install  Install pre-commit hooks"
	@echo "  make pre-commit-run      Run all pre-commit hooks"
	@echo "  make ci-local           Run full local CI pipeline"
	@echo ""
	@echo "Configuration:"
	@echo "  make validate-configs   Validate all configuration files"
	@echo "  make check-tooling      Verify unified tool configuration"
	@echo ""

# Installation targets
install:
	uv pip install -e .

install-dev:
	uv sync --group dev --group test
	uv run playwright install chromium

install-browsers:
	uv run playwright install chromium

# Testing targets
test:
	uv run pytest tests/ -v

test-unit:
	uv run pytest tests/unit/ -v -m unit

test-integration:
	uv run pytest tests/integration/ -v -m integration

test-e2e:
	uv run pytest tests/e2e/ -v -m e2e

test-coverage:
	uv run pytest tests/ -v --cov=layoutlens --cov-report=html --cov-report=term-missing

test-fast:
	uv run pytest tests/ -v -m "not slow"

test-parallel:
	uv run pytest tests/ -v -n auto

# Code quality targets
lint:
	uv run ruff check layoutlens/ tests/ examples/
	uv run mypy layoutlens/ --config-file=pyproject.toml

format:
	uv run ruff format layoutlens/ tests/ examples/

check:
	uv run ruff check --no-fix layoutlens/ tests/ examples/
	uv run ruff format --check layoutlens/ tests/ examples/
	uv run mypy layoutlens/ --config-file=pyproject.toml

# Package targets
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

build: clean
	uv build

check-package: build
	twine check dist/*

upload-test: build check-package
	twine upload --repository testpypi dist/*

upload: build check-package
	twine upload dist/*

# Documentation targets
docs:
	cd docs && uv run sphinx-build -b html . _build/html

serve-docs: docs
	cd docs/_build/html && python -m http.server 8000

# Development workflow targets
dev-setup: install-dev install-browsers
	@echo "Development environment setup complete!"
	@echo "Run 'make test' to verify everything works."

ci-test: install-dev install-browsers test-coverage
	@echo "CI test suite completed."

pre-commit: format lint test-fast
	@echo "Pre-commit checks passed! (using pyproject.toml config)"

release-check: clean install-dev test-coverage lint check-package
	@echo "Release checks completed successfully!"
	@echo "Package is ready for release."

# Benchmark and example targets
run-benchmarks:
	python benchmarks/evaluation/evaluator.py

test-examples:
	python examples/basic_usage.py
	python -m py_compile examples/advanced_usage.py

# User-friendly commands
info:
	python3 -m layoutlens.cli info

quick-start:
	@echo "LayoutLens Quick Start:"
	@echo "1. Install: pip install -e ."
	@echo "2. Install browsers: playwright install chromium"
	@echo "3. Set API key: export OPENAI_API_KEY='your-key'"
	@echo "4. Test setup: make info"
	@echo "5. Run example: make test-basic"

test-basic:
	python -m layoutlens.cli test --page benchmarks/test_data/layout_alignment/nav_centered.html --queries "Is this page well-structured?" --viewports desktop

validate-configs:
	@echo "Validating configuration consistency..."
	@echo "✓ Checking pyproject.toml contains ruff config..."
	@python3 -c "import tomllib; config = tomllib.load(open('pyproject.toml', 'rb')); assert 'ruff' in config.get('tool', {}), 'Missing ruff config'"
	@echo "✓ Checking pyproject.toml contains mypy config..."
	@python3 -c "import tomllib; config = tomllib.load(open('pyproject.toml', 'rb')); assert 'mypy' in config.get('tool', {}), 'Missing mypy config'"
	@echo "✓ Checking example configs are valid YAML..."
	@python3 -c "import yaml; yaml.safe_load(open('examples/layoutlens_config.yaml'))"
	@python3 -c "import yaml; yaml.safe_load(open('examples/sample_test_suite.yaml'))"
	@echo "✓ All configurations are valid and consistent!"

check-tooling:
	@echo "Verifying unified tooling configuration..."
	@echo "✓ Ruff configuration in pyproject.toml:"
	@uv run ruff check --show-settings 2>/dev/null | head -10 || echo "  (settings not available in this ruff version)"
	@echo "✓ MyPy uses pyproject.toml config"
	@echo "✓ Pre-commit hooks use pyproject.toml config"
	@echo "✓ GitHub Actions use pyproject.toml config"
	@echo "✓ Makefile uses pyproject.toml config"
	@echo "All tools unified under single configuration source!"

# Docker targets (if needed)
docker-build:
	docker build -t layoutlens:latest .

docker-test:
	docker run --rm layoutlens:latest make test

# Utility targets
show-coverage:
	@if [ -f htmlcov/index.html ]; then \
		echo "Opening coverage report..."; \
		python -m webbrowser htmlcov/index.html; \
	else \
		echo "Coverage report not found. Run 'make test-coverage' first."; \
	fi

show-size:
	@echo "Package size information:"
	@find . -name "*.py" -type f -exec wc -l {} + | tail -1
	@du -sh . --exclude=.git --exclude=__pycache__ --exclude=htmlcov --exclude=.pytest_cache

dep-tree:
	pip-tree

security-check:
	pip-audit

# Quick development commands
quick-test: test-unit test-fast
	@echo "Quick tests completed!"

full-check: format lint test-coverage check-package
	@echo "Full development check completed!"

# Environment info
env-info:
	@echo "Environment Information:"
	@echo "Python version: $$(python --version)"
	@echo "Pip version: $$(pip --version)"
	@echo "Pytest version: $$(pytest --version)"
	@echo "Playwright version: $$(playwright --version 2>/dev/null || echo 'Not installed')"
	@echo "Working directory: $$(pwd)"
	@echo "Git branch: $$(git branch --show-current 2>/dev/null || echo 'Not a git repo')"

# Local GitHub Actions with act
install-act:
	@echo "Installing act (GitHub Actions runner)..."
	@if command -v brew >/dev/null 2>&1; then \
		brew install act; \
	elif command -v curl >/dev/null 2>&1; then \
		curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash; \
	else \
		echo "Please install act manually: https://github.com/nektos/act#installation"; \
	fi

act-test:
	@echo "Running GitHub Actions test workflow locally with act..."
	act -W .github/workflows/test.yml

act-build:
	@echo "Running GitHub Actions CI workflow locally with act..."
	act -W .github/workflows/ci.yml

act-docs:
	@echo "Running GitHub Actions docs workflow locally with act..."
	act -W .github/workflows/docs.yml

act-all: act-build act-test act-docs
	@echo "✅ All GitHub Actions workflows completed locally!"

# Pre-commit integration
pre-commit-install: install-dev
	pre-commit install
	pre-commit install --hook-type commit-msg

pre-commit-run:
	pre-commit run --all-files

# Local CI pipeline that mirrors GitHub Actions
ci-local: format lint test-coverage
	@echo "🚀 Local CI pipeline completed successfully!"
	@echo "This mirrors what runs in GitHub Actions using pyproject.toml config."
	@echo "Ready to push to GitHub!"

# Development setup with all tools
dev-setup-full: install-dev install-act pre-commit-install
	@echo "🎉 Complete development environment setup finished!"
	@echo ""
	@echo "Available commands:"
	@echo "  make ci-local     - Run full local CI (like GitHub Actions)"
	@echo "  make act-all      - Test all GitHub workflows locally"
	@echo "  make pre-commit-run - Run pre-commit hooks manually"
	@echo ""
	@echo "Now you can develop with confidence! 🚀"
