"""Tests for the per-model completion-parameter policy.

The policy decides whether a non-default sampling parameter (``temperature``)
may be sent to a given model. Claude Sonnet 5 / Opus 4.6+ reject non-default
sampling params with a 400, so those patterns must OMIT temperature entirely.
"""

from __future__ import annotations

import pytest

from layoutlens.param_policy import completion_params, model_omits_temperature

# (model, temperature_should_be_present) — table-tests the pattern registry.
_REGISTRY_CASES = [
    # Claude models that 400 on non-default sampling params → omit temperature.
    ("claude-sonnet-5", False),
    ("claude-sonnet-5-20250101", False),
    ("anthropic/claude-sonnet-5", False),
    ("claude-opus-4-6", False),
    ("claude-opus-4-7", False),
    ("claude-opus-4-8", False),
    ("anthropic/claude-opus-4-8-20250101", False),
    ("claude-3-5-sonnet-4-6", False),
    # Models that accept temperature → include it.
    ("gpt-4o", True),
    ("gpt-4o-mini", True),
    ("claude-3-5-sonnet-20241022", True),
    ("claude-opus-4-5", True),
    ("anthropic/claude-3-5-sonnet", True),
    ("ollama/qwen2.5vl", True),
    ("gemini-1.5-pro", True),
]


@pytest.mark.parametrize("model,temp_present", _REGISTRY_CASES)
def test_registry_temperature_inclusion(model, temp_present):
    params = completion_params(model, temperature=0.0, max_tokens=300)
    assert params["max_tokens"] == 300
    assert ("temperature" in params) is temp_present
    if temp_present:
        assert params["temperature"] == 0.0


@pytest.mark.parametrize("model,temp_present", _REGISTRY_CASES)
def test_model_omits_temperature_matches_registry(model, temp_present):
    assert model_omits_temperature(model) is (not temp_present)


def test_temperature_none_is_always_omitted():
    # Even for a permissive model, an explicit None means "don't send it".
    params = completion_params("gpt-4o", temperature=None, max_tokens=100)
    assert "temperature" not in params
    assert params["max_tokens"] == 100


def test_omit_pattern_ignores_temperature_value():
    # A non-None temperature must still be dropped for an omit-pattern model.
    params = completion_params("claude-sonnet-5", temperature=0.7, max_tokens=50)
    assert "temperature" not in params


def test_case_insensitive_matching():
    assert model_omits_temperature("CLAUDE-SONNET-5") is True
    assert model_omits_temperature("Anthropic/Claude-Opus-4-6") is True
