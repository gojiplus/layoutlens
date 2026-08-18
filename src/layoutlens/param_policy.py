"""Per-model completion-parameter policy for LiteLLM calls.

Different vision models accept different sampling parameters. In particular,
Anthropic's newest reasoning-tuned Claude models REJECT any non-default
sampling parameter (notably ``temperature``) with an HTTP 400 — they only
accept the provider default. Sending ``temperature=0.0`` (or any value) to
those models makes every call fail.

This module centralizes the decision of which parameters are safe to send to a
given model, so both the analyze path (``_call_vision_api``) and the judge path
(``judge``) stay correct across providers without duplicating the logic.

Policy (as of 2026-07; revisit when Anthropic's constraints change):
    Claude Sonnet 5 and Opus 4.6/4.7/4.8 (and any ``*-4-6*`` sampling-locked
    Claude) omit ``temperature`` entirely; every other model includes it.

The registry is an ordered list of ``fnmatch`` glob patterns matched against a
normalized model name (lowercased, provider prefix such as ``anthropic/``
stripped). First match wins.
"""

from __future__ import annotations

from fnmatch import fnmatch
from typing import Any, Final

# Ordered glob patterns (matched against the normalized model name) whose models
# reject non-default sampling params and must therefore OMIT temperature.
# First match wins. Patterns are matched case-insensitively against the model
# name with any provider prefix (e.g. "anthropic/", "bedrock/") and Bedrock /
# cross-region dotted namespace (e.g. "anthropic.", "us.anthropic.") stripped —
# so "bedrock/anthropic.claude-sonnet-5-...v1:0" normalizes to "claude-sonnet-5-...".
_OMIT_TEMPERATURE_PATTERNS: tuple[str, ...] = (
    "claude-sonnet-5*",
    "claude-opus-4-6*",
    "claude-opus-4-7*",
    "claude-opus-4-8*",
    "claude-*-4-6*",
)

# Ordered glob patterns for reasoning/"thinking" models that spend thinking
# tokens INSIDE the completion budget by default (verified 2026-07). For these,
# the flat 300-token judge default truncates the actual verdict (e.g. Gemini 3
# Flash spends ~2,700 thinking tokens before emitting its answer), so the AUTO
# max-tokens default resolves higher. Matched case-insensitively against the
# normalized model name (provider prefix stripped); first match wins.
_REASONING_MODEL_PATTERNS: tuple[str, ...] = (
    "gemini-3*",
    "gemini-2.5*",
    "gpt-5*",
    "o1*",
    "o3*",
    "o4*",
)


class _Auto:
    """Sentinel type for an auto-resolved ``max_tokens`` (see :data:`AUTO`)."""

    _instance: _Auto | None = None

    def __new__(cls) -> _Auto:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return "AUTO"


# Sentinel meaning "pick a reasoning-aware default": callers pass ``AUTO`` (the
# default) and :func:`resolved_max_tokens` picks 8000 for reasoning models else
# 300. An explicit integer always passes through unchanged.
AUTO: Final = _Auto()

# Reasoning models spend thinking tokens in the completion budget, so the flat
# non-reasoning default truncates them. These two constants are the resolved
# AUTO values.
_REASONING_MAX_TOKENS: Final = 8000
_DEFAULT_MAX_TOKENS: Final = 300


def _normalize_model(model: str) -> str:
    """Reduce a model id to its bare Claude-style name for pattern matching.

    Strips any ``/``-delimited provider prefix (``anthropic/``, ``bedrock/``),
    then any leading dot-delimited namespace segments that precede the model
    family (Bedrock / cross-region forms such as ``anthropic.claude-...`` or
    ``us.anthropic.claude-...``). Everything is lowercased.
    """
    normalized = (model or "").lower()
    if "/" in normalized:
        normalized = normalized.rsplit("/", 1)[-1]
    # Drop dotted namespace prefixes (e.g. "us.anthropic.claude-..." -> "claude-...").
    # The model family always starts at the first segment beginning with "claude".
    if "." in normalized and "claude" in normalized:
        segments = normalized.split(".")
        for idx, segment in enumerate(segments):
            if segment.startswith("claude"):
                normalized = ".".join(segments[idx:])
                break
    return normalized


def model_omits_temperature(model: str) -> bool:
    """Return True if ``model`` rejects a non-default ``temperature`` param.

    Args:
        model: The model name (LiteLLM naming, optionally provider-prefixed).

    Returns:
        True when temperature must be omitted for this model, else False.
    """
    normalized = _normalize_model(model)
    return any(fnmatch(normalized, pattern) for pattern in _OMIT_TEMPERATURE_PATTERNS)


def is_reasoning_model(model: str) -> bool:
    """Return True if ``model`` is a reasoning/thinking model.

    Reasoning models spend thinking tokens inside the completion budget, so the
    judge path defaults such models to a much higher ``max_tokens`` (see
    :func:`resolved_max_tokens`) to avoid truncating the actual verdict.

    Args:
        model: The model name (LiteLLM naming, optionally provider-prefixed).

    Returns:
        True when the normalized model matches a known reasoning-model pattern.
    """
    normalized = _normalize_model(model)
    return any(fnmatch(normalized, pattern) for pattern in _REASONING_MODEL_PATTERNS)


def resolved_max_tokens(model: str, max_tokens: int | _Auto) -> int:
    """Resolve a possibly-``AUTO`` ``max_tokens`` to a concrete integer.

    ``AUTO`` resolves to 8000 for reasoning models (they spend thinking tokens
    in the completion budget) and 300 otherwise. Any explicit integer passes
    through unchanged.

    Args:
        model: The target model name.
        max_tokens: An explicit token budget, or :data:`AUTO` to auto-resolve.

    Returns:
        The concrete ``max_tokens`` integer to send.
    """
    if isinstance(max_tokens, _Auto):
        return (
            _REASONING_MAX_TOKENS if is_reasoning_model(model) else _DEFAULT_MAX_TOKENS
        )
    return max_tokens


def completion_params(
    model: str, *, temperature: float | None, max_tokens: int
) -> dict[str, Any]:
    """Build the policy-correct sampling kwargs for a completion call.

    ``max_tokens`` is always included. ``temperature`` is included only when it
    is non-None and the model is neither sampling-locked nor a reasoning model.
    Reasoning APIs reject or constrain sampling parameters, so synchronous and
    batch paths both retain the provider default for them.

    Args:
        model: The target model name.
        temperature: Desired sampling temperature, or None to omit it.
        max_tokens: Maximum tokens to generate.

    Returns:
        A kwargs dict suitable for merging into an ``acompletion`` call.
    """
    params: dict[str, Any] = {"max_tokens": max_tokens}
    if (
        temperature is not None
        and not model_omits_temperature(model)
        and not is_reasoning_model(model)
    ):
        params["temperature"] = temperature
    return params
