.PHONY: install lint test docs build ci-docker

install:
	uv sync --all-groups --all-extras
	uv run playwright install chromium firefox webkit

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run pyright
	uv run --isolated --no-project --with pydoclint==0.9.1 pydoclint src

test:
	LITELLM_LOCAL_MODEL_COST_MAP=True uv run pytest tests

docs:
	uv run sphinx-build -W -b html docs docs/_build/html

build:
	uv build

ci-docker:
	docker run --rm -v "$(CURDIR):/work" -v /work/.venv -w /work -e LITELLM_LOCAL_MODEL_COST_MAP=True python:3.12-slim sh -c 'apt-get update && apt-get install -y --no-install-recommends git && pip install uv && uv sync --frozen --all-groups --all-extras && uv run playwright install --with-deps chromium firefox webkit && uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run --isolated --no-project --with pydoclint==0.9.1 pydoclint src && uv run pytest tests && uv run sphinx-build -W -b html docs /tmp/layoutlens-docs && uv build'
