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

        # Constructor no longer raises for a missing key; the error is deferred
        # to the first LLM use so deterministic-only operations stay keyless.
        lens = LayoutLens(provider="anthropic", model="test-model")
        assert lens.api_key is None

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
    def test_missing_key_does_not_raise_in_constructor(self, monkeypatch, provider, env_var):
        """The constructor must be usable with zero API keys (keyless axe mode)."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        lens = LayoutLens(provider=provider, model="test-model")
        assert lens.api_key is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "provider,env_var",
        [
            ("openai", "OPENAI_API_KEY"),
            ("anthropic", "ANTHROPIC_API_KEY"),
            ("google", "GEMINI_API_KEY"),
        ],
    )
    async def test_missing_key_error_surfaces_on_first_llm_use(self, monkeypatch, tmp_path, provider, env_var):
        """The missing-key error must surface on the first LLM call, naming the right env var."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        lens = LayoutLens(provider=provider, model="test-model")

        # The vision-API call is the choke point where the key is enforced.
        image = tmp_path / "shot.png"
        image.write_bytes(b"not-a-real-png")

        with pytest.raises(AuthenticationError, match=env_var):
            await lens._call_vision_api(str(image), "Is it accessible?")

    @pytest.mark.asyncio
    async def test_missing_key_error_surfaces_through_analyze(self, monkeypatch, tmp_path):
        """analyze() must surface the deferred key error in its result (not a bare success)."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        lens = LayoutLens(provider="openai", model="test-model")

        image = tmp_path / "shot.png"
        image.write_bytes(b"not-a-real-png")

        result = await lens.analyze(str(image), "Is it accessible?")
        assert result.confidence == 0.0
        assert "OPENAI_API_KEY" in result.reasoning
