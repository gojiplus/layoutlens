# LayoutLens Development Makefile

.PHONY: help install install-dev test test-unit test-integration test-e2e test-coverage lint format clean build docs serve-docs

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
	@echo "  make lint            Run linting (flake8, mypy)"
	@echo "  make format          Format code (black, isort)"
	@echo "  make check           Check code formatting and linting"
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

# Installation targets
install:
	pip install -e .

install-dev:
	pip install -e .
	pip install -r requirements-test.txt

install-browsers:
	playwright install chromium

# Testing targets
test:
	pytest tests/ -v

test-unit:
	pytest tests/unit/ -v -m unit

test-integration:
	pytest tests/integration/ -v -m integration

test-e2e:
	pytest tests/e2e/ -v -m e2e

test-coverage:
	pytest tests/ -v --cov=layoutlens --cov=scripts --cov-report=html --cov-report=term-missing

test-fast:
	pytest tests/ -v -m "not slow"

test-parallel:
	pytest tests/ -v -n auto

# Code quality targets
lint:
	flake8 layoutlens/ scripts/ tests/ --exclude=__pycache__
	mypy layoutlens/ --ignore-missing-imports

format:
	black layoutlens/ scripts/ tests/ examples/
	isort layoutlens/ scripts/ tests/ examples/

check:
	black --check layoutlens/ scripts/ tests/ examples/
	isort --check-only layoutlens/ scripts/ tests/ examples/
	flake8 layoutlens/ scripts/ tests/ --exclude=__pycache__

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
	python -m build

check-package: build
	twine check dist/*

upload-test: build check-package
	twine upload --repository testpypi dist/*

upload: build check-package
	twine upload dist/*

# Documentation targets
docs:
	cd docs && sphinx-build -b html . _build/html

serve-docs: docs
	cd docs/_build/html && python -m http.server 8000

# Development workflow targets
dev-setup: install-dev install-browsers
	@echo "Development environment setup complete!"
	@echo "Run 'make test' to verify everything works."

ci-test: install-dev install-browsers test-coverage
	@echo "CI test suite completed."

pre-commit: format lint test-fast
	@echo "Pre-commit checks passed!"

release-check: clean install-dev test-coverage lint check-package
	@echo "Release checks completed successfully!"
	@echo "Package is ready for release."

# Benchmark and example targets
run-benchmarks:
	python scripts/benchmark/benchmark_generator.py

test-examples:
	python examples/basic_usage.py
	python -m py_compile examples/advanced_usage.py
	python -m py_compile examples/ci_cd_integration.py

validate-configs:
	python -c "import yaml; yaml.safe_load(open('examples/layoutlens_config.yaml'))"
	python -c "import yaml; yaml.safe_load(open('examples/sample_test_suite.yaml'))"

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