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
