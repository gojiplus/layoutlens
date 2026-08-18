"""Faithful judge interface for LayoutLens.

This module turns LayoutLens into a faithful *instrument* for external
evaluation harnesses (UIJudgeBench first). Unlike :meth:`LayoutLens.analyze`,
which wraps queries in its own persona/JSON scaffolding, :func:`judge` sends the
caller-supplied prompt VERBATIM as the only text block alongside one image. The
caller owns the entire prompt, including any response contract; LayoutLens adds
nothing to it.

Design contract:
    * No system persona, no ``_format_query_prompt`` scaffolding, no appended
      JSON-format instruction. One user message: ``[text=prompt, image]``.
    * Structured parsing: strict JSON first (tolerating fenced blocks and
      surrounding prose), then a leading yes/no fallback, then "unknown".
    * Conservative refusal detection (still returns the raw text).
    * Per-model parameter policy (see :mod:`layoutlens.param_policy`) so Claude
      4.6+/5 judges omit temperature.
    * No caching: a judge call must always hit the model.
    * Real token accounting: prompt/completion/total recorded separately.

``acompletion`` is imported here so tests patch it at
``layoutlens.api.judge.acompletion`` (mirroring the analyze path, which is
patched at ``layoutlens.api.core.acompletion``).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from litellm import acompletion

from ..exceptions import ValidationError
from ..logger import get_logger
from ..param_policy import AUTO, _Auto, completion_params, resolved_max_tokens

# ``.test_suite`` fully imports ``.core`` at its top, so ``.core`` is guaranteed
# loaded by the time this line runs — importing ``_read_usage`` from it here is
# cycle-safe and avoids duplicating the token-accounting helper.
from .core import _read_usage
from .test_suite import _parse_yes_no

if TYPE_CHECKING:
    from .core import LayoutLens

logger = get_logger("api.judge")

# Conservative refusal markers. Kept small and specific to avoid false positives
# on legitimate answers (e.g. "the nav could not be simpler").
_REFUSAL_PATTERNS: tuple[str, ...] = (
    "i can't",
    "i cannot assist",
    "i'm unable to",
    "i am unable to",
    "as an ai",
)

# Image extensions that map to a JPEG mime type; everything else is sent as PNG.
_JPEG_SUFFIXES = frozenset({".jpg", ".jpeg"})


@dataclass(slots=True)
class JudgeResult:
    """Structured outcome of a single :func:`judge` call.

    Attributes:
        answer: Parsed answer field, or "unknown" if unparseable.
        confidence: Parsed confidence in [0, 1], else 0.0.
        rationale: Parsed rationale/reasoning field, else "".
        raw: Full raw model text (always populated, even on refusal).
        refused: True if the response matched a refusal pattern.
        usage: Token counts with keys prompt_tokens/completion_tokens/total_tokens;
            reasoning-capable backends may also report thought_tokens.
        model: The model that produced the response.
        parse_mode: "json", "fallback", or "none".
        truncated: True if the model stopped because it hit the token budget
            (``finish_reason == "length"``) — the verdict may be incomplete.
        prompt_sha256: SHA-256 of the exact prompt sent (judge-contract
            pinning: model + prompt hash make a result auditable).
    """

    answer: str
    confidence: float
    rationale: str
    raw: str
    refused: bool
    usage: dict[str, int]
    model: str
    parse_mode: str
    truncated: bool = False
    prompt_sha256: str = ""


def detect_refusal(text: str) -> bool:
    """Return True if ``text`` matches a conservative refusal pattern."""
    lowered = (text or "").lower()
    return any(pattern in lowered for pattern in _REFUSAL_PATTERNS)


def _clamp_confidence(value: Any) -> float:
    """Coerce a parsed confidence to a float in [0, 1]; 0.0 on failure."""
    try:
        conf = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, conf))


def _iter_balanced_objects(text: str) -> list[dict[str, Any]]:
    """Yield every parseable top-level balanced JSON object found in ``text``.

    Scans character-by-character tracking brace depth while string-aware (braces
    inside JSON string values and escaped quotes are ignored), so it never mixes
    a stray ``{...}`` in surrounding prose with the real object. Each balanced
    ``{...}`` span is parsed; non-object or unparseable spans are skipped.
    """
    objects: list[dict[str, Any]] = []
    depth = 0
    start = -1
    in_string = False
    escaped = False

    for i, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start != -1:
                try:
                    parsed = json.loads(text[start : i + 1])
                except (json.JSONDecodeError, ValueError):
                    parsed = None
                if isinstance(parsed, dict):
                    objects.append(parsed)
                start = -1

    return objects


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Extract the best JSON object from ``text`` (tolerating fences/prose).

    Prefers the first balanced object containing an ``answer`` key (the real
    verdict), so a stray leading object such as ``{"x": 1}`` in surrounding
    prose can never shadow it. Falls back to the first balanced object, then to
    parsing the whole (fence-stripped) text. Returns None if nothing parses.
    """
    stripped = text.strip()

    # Strip a ```json ... ``` (or plain ``` ... ```) fence if present, so the
    # scanner works on the fence body too.
    fence = re.search(
        r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL | re.IGNORECASE
    )
    scan_targets = []
    if fence:
        scan_targets.append(fence.group(1).strip())
    scan_targets.append(stripped)

    fallback: dict[str, Any] | None = None
    for target in scan_targets:
        for obj in _iter_balanced_objects(target):
            if "answer" in obj:
                return obj
            if fallback is None:
                fallback = obj
    if fallback is not None:
        return fallback

    # Last resort: the whole text as a single JSON document.
    for candidate in scan_targets:
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def parse_judge_response(raw: str) -> tuple[str, float, str, str]:
    """Parse a raw judge response into (answer, confidence, rationale, mode).

    Args:
        raw: Raw response text returned by the model.

    Parsing strategy:
        1. Strict JSON object (fences and surrounding prose tolerated). Requires
           an ``answer`` field. ``rationale`` accepts ``reasoning`` as an alias.
        2. Leading yes/no fallback (reusing test-suite ``_parse_yes_no``).
        3. Otherwise ("none"): answer="unknown", confidence=0.0, rationale="".

    Returns:
        A 4-tuple ``(answer, confidence, rationale, parse_mode)`` where
        ``parse_mode`` is one of "json", "fallback", "none".
    """
    text = raw or ""

    parsed = _extract_json_object(text)
    if parsed is not None and "answer" in parsed:
        answer = str(parsed.get("answer", "unknown"))
        confidence = _clamp_confidence(parsed.get("confidence", 0.0))
        rationale = parsed.get("rationale")
        if rationale is None:
            rationale = parsed.get("reasoning", "")
        return answer, confidence, str(rationale or ""), "json"

    yes_no = _parse_yes_no(text)
    if yes_no is not None:
        return yes_no, 0.0, "", "fallback"

    return "unknown", 0.0, "", "none"


def _image_data_url(lens: LayoutLens, image_path: str | Path) -> str:
    """Encode ``image_path`` as a base64 data URL with mime by extension."""
    path = Path(image_path)
    if not path.exists():
        raise ValidationError(
            f"Image not found for judge call: {path}",
            field="image_path",
            value=str(path),
        )
    mime = "image/jpeg" if path.suffix.lower() in _JPEG_SUFFIXES else "image/png"
    image_b64 = lens._encode_image(path)  # noqa: SLF001
    return f"data:{mime};base64,{image_b64}"


def build_judge_messages(
    lens: LayoutLens, image_path: str | Path, prompt: str
) -> list[dict[str, Any]]:
    """Build the single-user-message payload a judge call sends.

    One user message with the caller's ``prompt`` VERBATIM as the only text
    block followed by the base64 image. Extracted so the batch path
    (:mod:`layoutlens.api.batch`) reuses the exact same construction and its
    per-request prompt stays byte-identical to :func:`judge` (parity contract).

    Args:
        lens: Configured LayoutLens client used to encode the image.
        image_path: Existing PNG or JPEG path.
        prompt: Exact text to send as the user message's text block.

    Returns:
        The single-message LiteLLM payload.

    Raises:
        ValidationError: If ``image_path`` does not exist.
    """
    data_url = _image_data_url(lens, image_path)
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]


def _finish_reason(response: Any) -> str | None:
    """Read ``finish_reason`` off the first choice, or None if absent."""
    try:
        return response.choices[0].finish_reason
    except (AttributeError, IndexError, TypeError):
        return None


def build_judge_result(
    lens: LayoutLens,
    raw: str,
    usage: dict[str, int],
    finish_reason: Any = None,
    prompt: str | None = None,
) -> JudgeResult:
    """Assemble a :class:`JudgeResult` from raw text + usage (shared by batch).

    Parses ``raw`` with :func:`parse_judge_response`, flags refusals, and sets
    ``truncated`` when ``finish_reason == "length"``. Kept public so the batch
    backends produce results identically to the synchronous :func:`judge`.
    """
    answer, confidence, rationale, parse_mode = parse_judge_response(raw)
    prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest() if prompt else ""
    truncated = finish_reason == "length"
    if truncated:
        logger.warning(
            "Judge response truncated (finish_reason=length) for model %s — "
            "raise max_tokens (reasoning models spend thinking tokens in the budget).",
            lens.model,
        )
    return JudgeResult(
        answer=answer,
        confidence=confidence,
        rationale=rationale,
        raw=raw,
        refused=detect_refusal(raw),
        usage=usage,
        model=lens.model,
        parse_mode=parse_mode,
        prompt_sha256=prompt_sha256,
        truncated=truncated,
    )


async def judge(
    lens: LayoutLens,
    image_path: str | Path,
    prompt: str,
    *,
    max_tokens: int | _Auto = AUTO,
    timeout: float = 120.0,
) -> JudgeResult:
    """Send ``prompt`` verbatim with ``image_path`` and parse the response.

    See :meth:`LayoutLens.judge` for the public contract. This is the module
    implementation so ``acompletion`` is patchable at ``layoutlens.api.judge``.

    Args:
        lens: Configured LayoutLens client.
        image_path: Existing PNG or JPEG path.
        prompt: Exact text to send with the image.
        max_tokens: Maximum model output tokens, or the model-aware default.
        timeout: Request timeout in seconds.

    Returns:
        Parsed judge result with raw text and usage metadata.

    Raises:
        ValidationError: If ``image_path`` does not exist. No result is
            fabricated — the caller must supply a real image.
    """
    # Validate the image FIRST: a missing image must raise ValidationError
    # regardless of whether an API key is configured (and before any API call).
    # ``build_judge_messages`` performs the existence check while encoding.
    messages = build_judge_messages(lens, image_path, prompt)

    lens._ensure_api_key()  # noqa: SLF001

    # Resolve AUTO to a reasoning-aware budget (8000 for thinking models, else
    # 300); an explicit integer passes through unchanged.
    max_tokens_value = resolved_max_tokens(lens.model, max_tokens)

    completion_kwargs: dict[str, Any] = {
        "model": lens.model,
        "messages": messages,
        "timeout": timeout,
        **completion_params(lens.model, temperature=0.0, max_tokens=max_tokens_value),
    }
    if lens.api_key:
        completion_kwargs["api_key"] = lens.api_key
    if lens.api_base:
        completion_kwargs["api_base"] = lens.api_base

    response = await acompletion(**completion_kwargs)

    # stream is never enabled here, so the response is a plain ModelResponse
    # despite litellm's broader union.
    raw = response.choices[0].message.content or ""  # pyright: ignore[reportAttributeAccessIssue]
    return build_judge_result(
        lens, raw, _read_usage(response), _finish_reason(response), prompt=prompt
    )
