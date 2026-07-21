"""Tests for provider-aware API key resolution in LayoutLens.

`_get_api_key_for_provider` must select the environment variable that
matches the requested provider, an explicitly-passed `api_key` must always
win, and the missing-key error must name the env var for the *requested*
provider (not always OPENAI_API_KEY).
"""

import pytest

from layoutlens import LayoutLens
from layoutlens.exceptions import AuthenticationError


class TestProviderApiKeySelection:
    """`_get_api_key_for_provider` should pick the right env var per provider."""

    @pytest.mark.parametrize(
        "provider,env_var",
        [
            ("openai", "OPENAI_API_KEY"),
            ("anthropic", "ANTHROPIC_API_KEY"),
            ("google", "GEMINI_API_KEY"),
            ("gemini", "GEMINI_API_KEY"),
            ("litellm", "OPENAI_API_KEY"),
        ],
    )
    def test_selects_env_var_for_provider(self, monkeypatch, provider, env_var):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv(env_var, "provider-specific-key")

        lens = LayoutLens(provider=provider, model="test-model")

        assert lens.api_key == "provider-specific-key"

    def test_anthropic_does_not_pick_up_openai_key(self, monkeypatch):
        """An OPENAI_API_KEY in the environment must not leak into anthropic."""
        monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with pytest.raises(AuthenticationError, match="ANTHROPIC_API_KEY"):
            LayoutLens(provider="anthropic", model="test-model")

    def test_explicit_api_key_wins_over_env_var(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")

        lens = LayoutLens(provider="anthropic", model="test-model", api_key="explicit-key")

        assert lens.api_key == "explicit-key"

    @pytest.mark.parametrize(
        "provider,env_var",
        [
            ("openai", "OPENAI_API_KEY"),
            ("anthropic", "ANTHROPIC_API_KEY"),
            ("google", "GEMINI_API_KEY"),
        ],
    )
    def test_missing_key_error_names_correct_env_var(self, monkeypatch, provider, env_var):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        with pytest.raises(AuthenticationError, match=env_var):
            LayoutLens(provider=provider, model="test-model")
