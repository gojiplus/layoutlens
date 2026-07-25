"""Multi-provider batch judging for LayoutLens.

Bulk offline evaluation (thousands of independent judgments with no latency
requirement) is exactly what provider *batch* APIs are for: a flat ~50% discount
and no rate-limit juggling. This module adds :func:`judge_batch`, which sends the
SAME per-request payload :func:`layoutlens.api.judge.judge` sends — the caller's
prompt VERBATIM plus one image, reasoning-aware ``max_tokens``, the per-model
parameter policy — over a batch transport, and parses every response with the
SHARED :func:`layoutlens.api.judge.parse_judge_response`. A parity test asserts
each request's prompt is byte-identical to the synchronous path.

Two backends, dispatched by ``lens.model``:

* ``gemini/*`` (AI Studio) -> **google-genai inline batch**. ``google-genai`` is
  an optional dependency (``layoutlens[gemini]``), imported lazily through a
  patchable factory so importing this module never requires it. Requests are
  chunked under the ~20 MB inline cap, keyed back to ids via per-request
  ``metadata``. Usage output = ``total - prompt`` (Gemini bills thinking as
  output).
* everything else (``gpt-*``/``openai/*``/``anthropic/*``/``vertex_ai/*``/
  ``bedrock/*`` ...) -> **litellm file-based batch**: a JSONL upload
  (``acreate_file``) -> ``acreate_batch`` -> poll ``aretrieve_batch`` ->
  ``afile_content``, parsed by ``custom_id``.

Both backends are **resumable**: a manifest persists submitted job/batch/file
ids BEFORE polling, so a killed run collects prior work on the next call and
submits only uncovered ids (never re-billing recovered work).

``acompletion`` is not used here; the litellm batch helpers are imported at
module level so tests patch them at ``layoutlens.api.batch``.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from litellm import acreate_batch, acreate_file, afile_content, aretrieve_batch

from ..exceptions import ValidationError
from ..logger import get_logger
from ..param_policy import AUTO, _Auto, _normalize_model, completion_params, resolved_max_tokens
from .judge import (
    _JPEG_SUFFIXES,
    JudgeResult,
    build_judge_messages,
    build_judge_result,
)

if TYPE_CHECKING:
    from .core import LayoutLens

logger = get_logger("api.batch")

# Inline batch payloads are capped at ~20 MB; leave headroom for JSON overhead.
_INLINE_CHUNK_BYTES = 18 * 1024 * 1024

# Batch statuses that mean "no further polling" (OpenAI/litellm vocabulary).
_LITELLM_TERMINAL = frozenset({"completed", "failed", "cancelled", "expired"})
# Substrings that mark a terminal google-genai batch job state.
_GENAI_TERMINAL = ("SUCCEEDED", "FAILED", "EXPIRED", "CANCELLED")

_ZERO_USAGE: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


@dataclass(slots=True)
class BatchRequest:
    """One item in a batch judge call.

    Attributes:
        id: Caller-owned unique id; results are keyed by it.
        image_path: Path to the image to judge.
        prompt: The exact prompt to send VERBATIM (as in :func:`judge`).
    """

    id: str
    image_path: str | Path
    prompt: str


# --- shared helpers -------------------------------------------------------


def _mime_for(image_path: str | Path) -> str:
    """JPEG for ``.jpg``/``.jpeg`` (matching the judge path), else PNG."""
    return "image/jpeg" if Path(image_path).suffix.lower() in _JPEG_SUFFIXES else "image/png"


def _unknown_result(lens: LayoutLens, reason: str) -> JudgeResult:
    """An 'unknown' result for a request that never produced a verdict.

    Used for a missing image or a job that failed/returned nothing, so one bad
    item never crashes the whole batch. ``rationale`` records ``reason``.
    """
    return JudgeResult(
        answer="unknown",
        confidence=0.0,
        rationale=reason,
        raw="",
        refused=False,
        usage=dict(_ZERO_USAGE),
        model=lens.model,
        parse_mode="none",
        truncated=False,
    )


def _default_manifest_path(lens: LayoutLens, requests: list[BatchRequest]) -> Path:
    """Deterministic manifest path keyed by the request-id set + model.

    So the same batch resumes from the same manifest, but two different batches
    (different ids or model) never collide.
    """
    digest = hashlib.sha256(("|".join(sorted(r.id for r in requests)) + "::" + lens.model).encode("utf-8")).hexdigest()[
        :16
    ]
    return lens.output_dir / "batch" / f"manifest_{digest}.json"


def _read_manifest(path: Path) -> dict[str, Any]:
    """Load a manifest, or an empty dict if absent/corrupt (corrupt => no resume)."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def _write_manifest(path: Path, data: dict[str, Any]) -> None:
    """Persist a manifest atomically enough for resume (parent created as needed)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _split_missing_images(
    lens: LayoutLens, requests: list[BatchRequest], results: dict[str, JudgeResult]
) -> list[BatchRequest]:
    """Record an unknown result for any request whose image is missing.

    Returns the requests with a real, existing image (the ones that enter a
    batch). Mutates ``results`` in place for the missing ones.
    """
    valid: list[BatchRequest] = []
    for req in requests:
        if Path(req.image_path).exists():
            valid.append(req)
        else:
            logger.warning("Batch request %s: image not found (%s) — unknown result.", req.id, req.image_path)
            results[req.id] = _unknown_result(lens, "missing image")
    return valid


# --- litellm file-based backend -------------------------------------------

# LiteLLM's batch helpers accept these custom_llm_provider values. NOTE: as of
# litellm 1.80.10, BOTH ``acreate_file`` AND ``acreate_batch`` restrict
# custom_llm_provider to openai/azure/vertex_ai/bedrock/hosted_vllm — NEITHER
# lists "anthropic" (only aretrieve_batch/afile_content do). So a native
# Anthropic/Claude model cannot even create a batch through litellm: it is FULLY
# unsupported, not partially. ``judge_batch`` therefore fails loud and helpful at
# submit time for such models (see ``_judge_batch_litellm``) rather than letting
# a cryptic litellm error surface mid-run. Run Claude synchronously via
# ``judge()``, or route it through Vertex.
_LITELLM_PROVIDER_PREFIXES = frozenset(
    {"openai", "azure", "vertex_ai", "bedrock", "anthropic", "hosted_vllm", "vertex"}
)


def _litellm_provider_for(model: str) -> str:
    """Derive the ``custom_llm_provider`` for a litellm batch from ``model``.

    Uses the explicit ``provider/`` prefix when present, else infers from the
    bare model family (``gpt``/``o1``/``o3``/``o4`` -> openai, ``claude`` ->
    anthropic), defaulting to ``openai``.
    """
    lowered = (model or "").lower()
    if "/" in lowered:
        prefix = lowered.split("/", 1)[0]
        if prefix in _LITELLM_PROVIDER_PREFIXES:
            return "vertex_ai" if prefix == "vertex" else prefix
    bare = _normalize_model(model)
    if bare.startswith(("gpt", "o1", "o3", "o4")):
        return "openai"
    if bare.startswith("claude"):
        return "anthropic"
    return "openai"


def _litellm_body(lens: LayoutLens, req: BatchRequest, max_tokens: int) -> dict[str, Any]:
    """Build the chat-completion ``body`` for one JSONL line (verbatim prompt)."""
    return {
        "model": lens.model,
        "messages": build_judge_messages(lens, req.image_path, req.prompt),
        **completion_params(lens.model, temperature=0.0, max_tokens=max_tokens),
    }


def _litellm_jsonl(lens: LayoutLens, requests: list[BatchRequest], max_tokens: int) -> bytes:
    """Encode the batch input JSONL (one line per request, keyed by custom_id)."""
    lines = [
        json.dumps(
            {
                "custom_id": req.id,
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": _litellm_body(lens, req, max_tokens),
            }
        )
        for req in requests
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _parse_litellm_output(lens: LayoutLens, text: str) -> dict[str, JudgeResult]:
    """Parse a batch output JSONL body into ``{custom_id: JudgeResult}``."""
    out: dict[str, JudgeResult] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        cid = rec.get("custom_id")
        if cid is None:
            continue
        body = ((rec.get("response") or {}).get("body")) or {}
        choices = body.get("choices") or [{}]
        first = choices[0] or {}
        raw = (first.get("message") or {}).get("content") or ""
        finish = first.get("finish_reason")
        usage_raw = body.get("usage") or {}
        usage = {
            "prompt_tokens": int(usage_raw.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(usage_raw.get("completion_tokens", 0) or 0),
            "total_tokens": int(usage_raw.get("total_tokens", 0) or 0),
        }
        out[cid] = build_judge_result(lens, raw, usage, finish)
    return out


async def _collect_litellm_job(
    lens: LayoutLens, job: dict[str, Any], provider: str, poll_interval: float, poll_timeout: float
) -> dict[str, JudgeResult]:
    """Poll one prior/just-submitted litellm batch to completion and parse it.

    Returns ``{}`` (its ids stay uncovered) if the batch failed or produced no
    output file, so those ids fall back to unknown rather than crashing.
    """
    batch_id = job["batch_id"]
    deadline = time.monotonic() + poll_timeout
    batch = await aretrieve_batch(batch_id, custom_llm_provider=provider)
    while str(getattr(batch, "status", "")) not in _LITELLM_TERMINAL:
        if time.monotonic() > deadline:
            raise TimeoutError(f"litellm batch {batch_id} did not finish within {poll_timeout}s")
        await asyncio.sleep(poll_interval)
        batch = await aretrieve_batch(batch_id, custom_llm_provider=provider)

    if str(getattr(batch, "status", "")) != "completed":
        logger.warning("litellm batch %s ended in status %s", batch_id, getattr(batch, "status", "?"))
        return {}
    output_file_id = getattr(batch, "output_file_id", None)
    if not output_file_id:
        return {}
    content = await afile_content(output_file_id, custom_llm_provider=provider)
    text = content.text if hasattr(content, "text") else content.content.decode("utf-8")
    return _parse_litellm_output(lens, text)


async def _judge_batch_litellm(
    lens: LayoutLens,
    requests: list[BatchRequest],
    max_tokens_value: int,
    resume: bool,
    manifest_path: Path,
    poll_interval: float,
    poll_timeout: float,
) -> dict[str, JudgeResult]:
    """litellm file-based batch backend (see module docstring).

    Raises:
        ValidationError: For a native Anthropic/Claude model — litellm 1.80.10
            supports neither ``acreate_file`` nor ``acreate_batch`` for the
            ``anthropic`` provider, so a batch cannot be created at all.
    """
    provider = _litellm_provider_for(lens.model)
    if provider == "anthropic":
        raise ValidationError(
            "Anthropic batch is not supported by litellm 1.80.10 "
            "(neither acreate_file nor acreate_batch accept the 'anthropic' provider). "
            f"Use judge() (synchronous) for Claude model '{lens.model}', or run Claude via Vertex "
            "(vertex_ai/…) for batch.",
            field="model",
            value=lens.model,
        )
    results: dict[str, JudgeResult] = {}
    valid = _split_missing_images(lens, requests, results)

    manifest = _read_manifest(manifest_path) if resume else {}
    jobs: list[dict[str, Any]] = list(manifest.get("jobs", [])) if resume else []
    covered: set[str] = set()
    for job in jobs:
        try:
            collected = await _collect_litellm_job(lens, job, provider, poll_interval, poll_timeout)
        except Exception as exc:  # noqa: BLE001 - a broken prior job just re-submits its ids
            logger.warning("Resume: skipping prior litellm batch %s: %s", job.get("batch_id"), exc)
            continue
        results.update(collected)
        covered |= set(collected)

    remaining = [r for r in valid if r.id not in covered]
    if remaining:
        jsonl = _litellm_jsonl(lens, remaining, max_tokens_value)
        file_obj = await acreate_file(file=jsonl, purpose="batch", custom_llm_provider=provider)
        batch = await acreate_batch(
            input_file_id=file_obj.id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
            custom_llm_provider=provider,
        )
        job = {"batch_id": batch.id, "input_file_id": file_obj.id, "ids": [r.id for r in remaining]}
        jobs.append(job)
        # Persist BEFORE polling so a kill during the wait leaves the batch
        # recoverable on the next resume (never re-billed).
        _write_manifest(manifest_path, {"model": lens.model, "backend": "litellm", "jobs": jobs})
        results.update(await _collect_litellm_job(lens, job, provider, poll_interval, poll_timeout))

    for req in valid:
        results.setdefault(req.id, _unknown_result(lens, "no batch response"))
    return results


# --- google-genai inline backend ------------------------------------------


def _genai_client(lens: LayoutLens):
    """Build a google-genai client (lazy import; patchable in tests).

    Raises:
        ImportError: If the optional ``google-genai`` dependency is absent.
    """
    import os

    try:
        from google import genai  # lazy: optional dependency
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise ImportError(
            "The gemini/ batch backend requires google-genai. Install it with: pip install 'layoutlens[gemini]'"
        ) from exc

    api_key = lens.api_key or os.environ.get("GEMINI_API_KEY")
    return genai.Client(api_key=api_key)


def _genai_inline_request(lens: LayoutLens, req: BatchRequest, max_tokens: int) -> dict[str, Any]:
    """Build the InlinedRequest kwargs for ``req`` as a plain dict.

    Plain dict (not a google-genai type) so payload construction is pure and
    offline-testable; :func:`_submit_genai_chunk` wraps it in the SDK types. The
    text part is the caller's prompt VERBATIM (parity with :func:`judge`).
    """
    b64 = base64.b64encode(Path(req.image_path).read_bytes()).decode("ascii")
    return {
        "contents": [
            {
                "parts": [
                    {"text": req.prompt},
                    {"inline_data": {"mime_type": _mime_for(req.image_path), "data": b64}},
                ]
            }
        ],
        "config": {"max_output_tokens": max_tokens},
        "metadata": {"req_id": req.id},
    }


def _chunk_genai(
    payloads: list[tuple[BatchRequest, dict[str, Any]]],
) -> list[list[tuple[BatchRequest, dict[str, Any]]]]:
    """Split (request, inline-dict) pairs into chunks under the inline size cap."""
    chunks: list[list[tuple[BatchRequest, dict[str, Any]]]] = []
    cur: list[tuple[BatchRequest, dict[str, Any]]] = []
    cur_bytes = 0
    for req, payload in payloads:
        parts = payload["contents"][0]["parts"]
        size = len(parts[1]["inline_data"]["data"]) + len(parts[0]["text"])
        if cur and cur_bytes + size > _INLINE_CHUNK_BYTES:
            chunks.append(cur)
            cur, cur_bytes = [], 0
        cur.append((req, payload))
        cur_bytes += size
    if cur:
        chunks.append(cur)
    return chunks


def _submit_genai_chunk(
    client, model: str, chunk: list[tuple[BatchRequest, dict[str, Any]]], max_tokens: int, display_name: str
) -> str:
    """Wrap a chunk in google-genai types, submit it, return the job name.

    Isolated so tests can patch it (bypassing the SDK type wrapping) while the
    rest of the orchestration is exercised.
    """
    from google.genai import types  # lazy

    reqs = [
        types.InlinedRequest(
            contents=payload["contents"],
            config=types.GenerateContentConfig(max_output_tokens=max_tokens),
            metadata=payload["metadata"],
        )
        for _req, payload in chunk
    ]
    job = client.batches.create(model=model, src=reqs, config={"display_name": display_name})
    return job.name


def _genai_usage(um: Any) -> dict[str, int]:
    """Input/output/total split from a Gemini usage_metadata (output includes thinking)."""
    if um is None:
        return dict(_ZERO_USAGE)
    prompt = int(getattr(um, "prompt_token_count", 0) or 0)
    total = int(getattr(um, "total_token_count", 0) or 0)
    return {"prompt_tokens": prompt, "completion_tokens": max(total - prompt, 0), "total_tokens": total}


def _genai_finish_reason(resp: Any) -> str | None:
    """Normalize a Gemini candidate finish reason to the judge vocabulary.

    Returns ``"length"`` when the candidate stopped on ``MAX_TOKENS`` (so
    :func:`build_judge_result` flags truncation), else None.
    """
    try:
        reason = str(resp.candidates[0].finish_reason)
    except (AttributeError, IndexError, TypeError):
        return None
    return "length" if "MAX_TOKENS" in reason else None


async def _collect_genai_job(
    client, job_name: str, poll_interval: float, poll_timeout: float
) -> dict[str, dict[str, Any]]:
    """Poll one genai batch job to completion; return {req_id: {text, usage, finish}}."""
    deadline = time.monotonic() + poll_timeout
    job = client.batches.get(name=job_name)
    while not any(state in str(job.state) for state in _GENAI_TERMINAL):
        if time.monotonic() > deadline:
            raise TimeoutError(f"genai batch {job_name} did not finish within {poll_timeout}s (state {job.state})")
        await asyncio.sleep(poll_interval)
        job = client.batches.get(name=job_name)
    if "SUCCEEDED" not in str(job.state):
        logger.warning("genai batch %s ended in state %s", job_name, job.state)
        return {}

    out: dict[str, dict[str, Any]] = {}
    dest = getattr(job, "dest", None)
    for r in getattr(dest, "inlined_responses", None) or []:
        md = getattr(r, "metadata", None) or {}
        req_id = md.get("req_id")
        if req_id is None:
            continue
        resp = getattr(r, "response", None)
        text = getattr(resp, "text", None) if resp is not None else None
        usage = _genai_usage(getattr(resp, "usage_metadata", None) if resp is not None else None)
        finish = _genai_finish_reason(resp) if resp is not None else None
        out[req_id] = {"text": text, "usage": usage, "finish": finish}
    return out


async def _judge_batch_genai(
    lens: LayoutLens,
    requests: list[BatchRequest],
    max_tokens_value: int,
    resume: bool,
    manifest_path: Path,
    poll_interval: float,
    poll_timeout: float,
) -> dict[str, JudgeResult]:
    """google-genai inline batch backend (see module docstring)."""
    display_name = f"layoutlens-batch:{lens.model}"
    results: dict[str, JudgeResult] = {}
    valid = _split_missing_images(lens, requests, results)

    payloads = [(req, _genai_inline_request(lens, req, max_tokens_value)) for req in valid]

    client = _genai_client(lens)

    manifest = _read_manifest(manifest_path) if resume else {}
    jobs: list[dict[str, Any]] = list(manifest.get("jobs", [])) if resume else []
    covered: set[str] = set()
    collected: dict[str, dict[str, Any]] = {}
    for job in jobs:
        try:
            got = await _collect_genai_job(client, job["job_name"], poll_interval, poll_timeout)
        except Exception as exc:  # noqa: BLE001 - broken prior job re-submits its ids
            logger.warning("Resume: skipping prior genai job %s: %s", job.get("job_name"), exc)
            continue
        collected.update(got)
        covered |= set(got)

    remaining = [(req, payload) for req, payload in payloads if req.id not in covered]
    # Submit ALL remaining chunks first (each ~1 API call, flushed to the
    # manifest), then poll+collect — so a kill during polling leaves every job
    # submitted (the next resume just collects).
    new_jobs: list[str] = []
    for chunk in _chunk_genai(remaining):
        job_name = _submit_genai_chunk(client, lens.model, chunk, max_tokens_value, display_name)
        new_jobs.append(job_name)
        jobs.append({"job_name": job_name, "ids": [req.id for req, _ in chunk]})
        _write_manifest(manifest_path, {"model": lens.model, "backend": "genai", "jobs": jobs})
    for job_name in new_jobs:
        collected.update(await _collect_genai_job(client, job_name, poll_interval, poll_timeout))

    for req in valid:
        got = collected.get(req.id)
        if got is None:
            results[req.id] = _unknown_result(lens, "no batch response")
        else:
            results[req.id] = build_judge_result(lens, got["text"] or "", got["usage"], got["finish"])
    return results


# --- dispatch -------------------------------------------------------------


def _is_gemini_studio(model: str) -> bool:
    """True for AI-Studio Gemini (``gemini/*``) — the google-genai batch path."""
    return (model or "").strip().lower().startswith("gemini/")


async def judge_batch(
    lens: LayoutLens,
    requests: list[BatchRequest],
    *,
    max_tokens: int | _Auto = AUTO,
    resume: bool = True,
    manifest_path: str | Path | None = None,
    poll_interval: float = 10.0,
    poll_timeout: float = 24 * 3600.0,
) -> dict[str, JudgeResult]:
    """Judge every request via a batch transport (see :meth:`LayoutLens.judge_batch`).

    Module implementation so the litellm batch helpers and the genai client are
    patchable at ``layoutlens.api.batch``.
    """
    if not requests:
        return {}

    max_tokens_value = resolved_max_tokens(lens.model, max_tokens)
    path = Path(manifest_path) if manifest_path is not None else _default_manifest_path(lens, requests)

    lens._ensure_api_key()

    backend = _judge_batch_genai if _is_gemini_studio(lens.model) else _judge_batch_litellm
    return await backend(lens, requests, max_tokens_value, resume, path, poll_interval, poll_timeout)
