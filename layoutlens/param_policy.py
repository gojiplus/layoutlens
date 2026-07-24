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
from typing import Any

# Ordered glob patterns (matched against the normalized model name) whose models
# reject non-default sampling params and must therefore OMIT temperature.
# First match wins. Patterns are matched case-insensitively with the provider
# prefix (e.g. "anthropic/") stripped.
_OMIT_TEMPERATURE_PATTERNS: tuple[str, ...] = (
    "claude-sonnet-5*",
    "claude-opus-4-6*",
    "claude-opus-4-7*",
    "claude-opus-4-8*",
    "claude-*-4-6*",
)


def _normalize_model(model: str) -> str:
    """Lowercase and strip any provider prefix (``anthropic/claude-...``)."""
    normalized = (model or "").lower()
    if "/" in normalized:
        normalized = normalized.rsplit("/", 1)[-1]
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


def completion_params(model: str, *, temperature: float | None, max_tokens: int) -> dict[str, Any]:
    """Build the policy-correct sampling kwargs for a completion call.

    ``max_tokens`` is always included. ``temperature`` is included only when it
    is non-None AND the model accepts a non-default sampling parameter (see
    :func:`model_omits_temperature`).

    Args:
        model: The target model name.
        temperature: Desired sampling temperature, or None to omit it.
        max_tokens: Maximum tokens to generate.

    Returns:
        A kwargs dict suitable for merging into an ``acompletion`` call.
    """
    params: dict[str, Any] = {"max_tokens": max_tokens}
    if temperature is not None and not model_omits_temperature(model):
        params["temperature"] = temperature
    return params
