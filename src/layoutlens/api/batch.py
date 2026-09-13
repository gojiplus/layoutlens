"""Resumable vision judging through batchlane's provider batch transports.

LayoutLens owns verbatim prompts, image preparation, manifest locking, and
judgment parsing. Batchlane owns request sizing, submission, recovery, polling
requests, and result transport. Provider calls run outside the event loop.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import tempfile
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import batchlane as bl

from ..exceptions import ValidationError
from ..logger import get_logger
from ..param_policy import (
    AUTO,
    _Auto,
    _normalize_model,
    completion_params,
    resolved_max_tokens,
)
from .judge import _JPEG_SUFFIXES, JudgeResult, build_judge_messages, build_judge_result

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .core import LayoutLens

logger = get_logger("api.batch")

_OPENAI_REASONING_EFFORTS = frozenset({"none", "low", "medium", "high", "xhigh", "max"})
_OPENAI_IMAGE_DETAILS = frozenset({"auto", "low", "high", "original"})
_ZERO_USAGE = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
_BATCH_FINGERPRINT_VERSION = b"layoutlens-batch-request-v4"


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


def batch_usage_summary(results: dict[str, JudgeResult]) -> dict[str, Any]:
    """Aggregate token usage (and estimated cost) across judge_batch results.

    Args:
        results: Judge results keyed by the caller-owned batch request ids.

    Returns:
        Dict with request counts, per-field token totals, and
        ``estimated_cost_usd`` (None when the model is unknown to litellm).
    """
    from .core import _estimate_cost

    prompt = sum(r.usage.get("prompt_tokens", 0) for r in results.values())
    completion = sum(r.usage.get("completion_tokens", 0) for r in results.values())
    models = {r.model for r in results.values()}
    model = next(iter(models)) if len(models) == 1 else ""
    return {
        "requests": len(results),
        "refused": sum(1 for r in results.values() if r.refused),
        "unparsed": sum(1 for r in results.values() if r.parse_mode == "none"),
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": sum(r.usage.get("total_tokens", 0) for r in results.values()),
        "estimated_cost_usd": _estimate_cost(model, prompt, completion)
        if model
        else None,
    }


def _mime_for(image_path: str | Path) -> str:
    """JPEG for ``.jpg``/``.jpeg`` (matching the judge path), else PNG."""
    return (
        "image/jpeg"
        if Path(image_path).suffix.lower() in _JPEG_SUFFIXES
        else "image/png"
    )


def _unknown_result(lens: LayoutLens, reason: str, prompt: str = "") -> JudgeResult:
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
        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        if prompt
        else "",
    )


def _legacy_manifest_path(lens: LayoutLens, requests: list[BatchRequest]) -> Path:
    """Return the pre-2.1.1 id/model-only manifest path.

    Legacy manifests cannot be safely resumed because they do not attest the
    prompt, image, or output budget. The path is retained only so
    :func:`judge_batch` can detect one and fail before a duplicate submission.
    """
    digest = hashlib.sha256(
        ("|".join(sorted(r.id for r in requests)) + "::" + lens.model).encode("utf-8")
    ).hexdigest()[:16]
    return lens.output_dir / "batch" / f"manifest_{digest}.json"


def _digest_field(digest: Any, label: str, data: bytes) -> None:
    """Add one length-delimited field to a batch request fingerprint."""
    label_bytes = label.encode("utf-8")
    digest.update(len(label_bytes).to_bytes(4, "big"))
    digest.update(label_bytes)
    digest.update(len(data).to_bytes(8, "big"))
    digest.update(data)


def _batch_fingerprint(
    lens: LayoutLens,
    requests: list[BatchRequest],
    max_tokens: int,
    *,
    backend: str | None = None,
    reasoning_effort: str | None = None,
    image_detail: str = "auto",
) -> str:
    """Hash every provider-visible input that determines a batch response."""
    if backend is None:
        backend = _batch_backend_name(lens)
    digest = hashlib.sha256()
    _digest_field(digest, "version", _BATCH_FINGERPRINT_VERSION)
    _digest_field(digest, "model", lens.model.encode("utf-8"))
    _digest_field(digest, "api_base", (lens.api_base or "").encode("utf-8"))
    _digest_field(digest, "max_tokens", str(max_tokens).encode("ascii"))
    _digest_field(digest, "backend", backend.encode("ascii"))
    _digest_field(
        digest,
        "reasoning_effort",
        (reasoning_effort or "provider-default").encode("ascii"),
    )
    _digest_field(digest, "image_detail", image_detail.encode("ascii"))
    for request in sorted(requests, key=lambda item: item.id):
        image_path = Path(request.image_path)
        _digest_field(digest, "id", request.id.encode("utf-8"))
        _digest_field(digest, "prompt", request.prompt.encode("utf-8"))
        _digest_field(digest, "image_mime", _mime_for(image_path).encode("ascii"))
        try:
            image_bytes = image_path.read_bytes()
        except OSError:
            image_bytes = b"<missing>"
        _digest_field(digest, "image", image_bytes)
    return digest.hexdigest()


def _default_manifest_path(lens: LayoutLens, fingerprint: str) -> Path:
    """Return the content-addressed manifest path for an exact batch request."""
    return lens.output_dir / "batch" / f"manifest_{fingerprint}.json"


def _overlapping_manifest_paths(
    path: Path, lens: LayoutLens, request_ids: set[str]
) -> list[Path]:
    """Find prior manifests that may already have billed any requested id."""
    overlaps: list[Path] = []
    if not path.parent.is_dir():
        return overlaps
    for candidate in sorted(path.parent.glob("manifest_*.json")):
        if candidate == path:
            continue
        manifest = _read_manifest(candidate)
        if manifest is None or manifest.get("model") != lens.model:
            continue
        submitted_ids = {
            request_id
            for job in manifest.get("jobs", [])
            if isinstance(job, dict)
            for request_id in job.get("ids", [])
            if isinstance(request_id, str)
        }
        # Requests are persisted before submission; a crash can leave receipts
        # only in batchlane's journal, before job handles reach this manifest.
        submitted_ids.update(
            request["custom_id"]
            for request in manifest.get("requests", [])
            if isinstance(request, dict) and isinstance(request.get("custom_id"), str)
        )
        if submitted_ids & request_ids:
            overlaps.append(candidate)
    return overlaps


def _resume_manifest(
    path: Path,
    *,
    resume: bool,
    fingerprint: str,
    model: str,
    backend: str,
    max_tokens: int,
    reasoning_effort: str | None = None,
    image_detail: str = "auto",
) -> dict[str, Any]:
    """Load a manifest only when its full request identity matches."""
    if not resume:
        return {}
    if not path.exists():
        return {}
    manifest = _read_manifest(path)
    if manifest is None:
        raise ValidationError(
            "Batch resume manifest exists but is unreadable or invalid. Refusing to submit "
            "a possibly duplicate batch. Inspect it for a recoverable provider job id; if it "
            "cannot be recovered, move it aside before retrying. No submission was made.",
            field="manifest_path",
            value=str(path),
        )
    expected = {
        "fingerprint": fingerprint,
        "model": model,
        "backend": backend,
        "max_tokens": max_tokens,
        "reasoning_effort": reasoning_effort,
        "image_detail": image_detail,
    }
    actual = {key: manifest.get(key) for key in expected}
    if actual != expected:
        raise ValidationError(
            "Batch resume manifest does not match the exact model, prompt/image payload, "
            "backend, token budget, reasoning effort, and image detail. Use a new "
            "manifest path; stale results will not be reused.",
            field="manifest_path",
            value=str(path),
        )
    return manifest


def _read_manifest(path: Path) -> dict[str, Any] | None:
    """Load a manifest, returning None when it is absent, unreadable, or invalid."""
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    return manifest if isinstance(manifest, dict) else None


def _write_manifest(path: Path, data: dict[str, Any]) -> None:
    """Persist a manifest with an atomic replace in the destination directory."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{p.name}.", dir=p.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(data, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(p)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


@contextmanager
def _manifest_lock(path: Path) -> Iterator[None]:
    """Prevent concurrent submissions from sharing one manifest identity."""
    lock_path = path.with_suffix(f"{path.suffix}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValidationError(
            "Another process owns this Batch manifest, or a prior process stopped without "
            "releasing its lock. Confirm no matching run is active before removing the lock; "
            "no submission was made.",
            field="manifest_path",
            value=str(lock_path),
        ) from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(f"pid={os.getpid()} created_unix={time.time()}\n")
            handle.flush()
            os.fsync(handle.fileno())
        yield
    finally:
        lock_path.unlink(missing_ok=True)


def _validate_request_ids(requests: list[BatchRequest]) -> None:
    """Reject ids that cannot map one-to-one onto provider responses."""
    seen: set[str] = set()
    duplicate_ids: set[str] = set()
    for request in requests:
        if request.id in seen:
            duplicate_ids.add(request.id)
        seen.add(request.id)
    if duplicate_ids:
        raise ValidationError(
            "Batch request ids must be unique.",
            field="requests",
            value=", ".join(sorted(duplicate_ids)),
        )


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
            logger.warning(
                "Batch request %s: image not found (%s) — unknown result.",
                req.id,
                req.image_path,
            )
            results[req.id] = _unknown_result(lens, "missing image", req.prompt)
    return valid


def _litellm_body(
    lens: LayoutLens, req: BatchRequest, max_tokens: int
) -> dict[str, Any]:
    """Build the chat-completion ``body`` for one JSONL line (verbatim prompt)."""
    return {
        "model": lens.model,
        "messages": build_judge_messages(lens, req.image_path, req.prompt),
        **completion_params(lens.model, temperature=0.0, max_tokens=max_tokens),
    }


def _openai_body(
    lens: LayoutLens,
    request: BatchRequest,
    max_tokens: int,
    *,
    reasoning_effort: str | None,
    image_detail: str,
) -> dict[str, Any]:
    """Build one native Responses API body without changing the caller prompt."""
    messages = build_judge_messages(lens, request.image_path, request.prompt)
    data_url = messages[0]["content"][1]["image_url"]["url"]
    body: dict[str, Any] = {
        "model": _normalize_model(lens.model),
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": request.prompt},
                    {
                        "type": "input_image",
                        "image_url": data_url,
                        "detail": image_detail,
                    },
                ],
            }
        ],
        "max_output_tokens": max_tokens,
    }
    if reasoning_effort is not None:
        body["reasoning"] = {"effort": reasoning_effort}
    parameter_policy = completion_params(
        lens.model, temperature=0.0, max_tokens=max_tokens
    )
    if "temperature" in parameter_policy:
        body["temperature"] = parameter_policy["temperature"]
    return body


def _responses_output_text(body: dict[str, Any]) -> str:
    """Join every Responses API ``output_text`` block in provider order."""
    texts: list[str] = []
    for output in body.get("output") or []:
        if not isinstance(output, dict) or output.get("type") != "message":
            continue
        texts.extend(
            str(content.get("text") or "")
            for content in output.get("content") or []
            if isinstance(content, dict) and content.get("type") == "output_text"
        )
    return "\n".join(text for text in texts if text)


def _is_gemini_studio(model: str) -> bool:
    """True for AI-Studio Gemini (``gemini/*``) — the google-genai batch path."""
    return (model or "").strip().lower().startswith("gemini/")


def _is_native_openai(lens: LayoutLens) -> bool:
    """True when the official OpenAI client owns the configured provider."""
    return (lens.provider or "").strip().lower() == "openai"


def _batch_backend_name(lens: LayoutLens) -> str:
    """Return the one backend selected by the model/provider contract."""
    if _is_gemini_studio(lens.model):
        return "batchlane-chat"
    if _is_native_openai(lens):
        return "batchlane-responses"
    return "batchlane-chat"


def _validate_backend_configuration(lens: LayoutLens) -> None:
    """Reject provider/model combinations that could route credentials incorrectly."""
    provider = (lens.provider or "").strip().lower()
    gemini_model = _is_gemini_studio(lens.model)
    if gemini_model and provider not in {"gemini", "google"}:
        raise ValidationError(
            "A gemini/* Batch model requires provider='gemini' (or 'google'); refusing to "
            "route it with credentials for another provider.",
            field="provider",
            value=lens.provider,
        )
    if not gemini_model and provider in {"gemini", "google"}:
        raise ValidationError(
            "The Gemini Batch provider requires a gemini/* model id.",
            field="model",
            value=lens.model,
        )
    inferred = _litellm_provider_for(lens.model)
    if provider in {"openai", "anthropic"} and inferred != provider:
        raise ValidationError(
            f"provider={provider!r} conflicts with model {lens.model!r}; refusing to route "
            "the model to the wrong provider Batch API.",
            field="model",
            value=lens.model,
        )


def _litellm_provider_for(model: str) -> str:
    """Resolve a provider prefix or the known bare model families."""
    if "/" in model:
        prefix = model.split("/", 1)[0]
        return "vertex_ai" if prefix == "vertex" else prefix
    return "anthropic" if model.startswith("claude") else "openai"


def _batch_line(
    lens: LayoutLens,
    request: BatchRequest,
    max_tokens: int,
    reasoning_effort: str | None,
    image_detail: str,
) -> bl.BatchLine:
    """Build a provider request without altering the caller's prompt or image."""
    provider = _litellm_provider_for(lens.model)
    model = (
        lens.model
        if lens.model.startswith(f"{provider}/")
        else f"{provider}/{lens.model}"
    )
    if _is_native_openai(lens):
        body = _openai_body(
            lens,
            request,
            max_tokens,
            reasoning_effort=reasoning_effort,
            image_detail=image_detail,
        )
        return bl.BatchLine(
            request.id,
            model,
            input=body.pop("input"),
            params={k: v for k, v in body.items() if k != "model"},
        )
    body = _litellm_body(lens, request, max_tokens)
    return bl.BatchLine(
        request.id,
        model,
        body["messages"],
        {k: v for k, v in body.items() if k not in {"model", "messages"}},
    )


def _judgment(lens: LayoutLens, result: bl.RequestResult, prompt: str) -> JudgeResult:
    """Preserve usage, refusal, and truncation while applying the shared parser."""
    body = result.response or {}
    if not result.ok or body.get("error"):
        return _unknown_result(
            lens, f"batch request failed: {result.error or body.get('error')}", prompt
        )
    usage_raw = body.get("usage") or {}
    refusal = ""
    if "output" in body:
        raw = _responses_output_text(body)
        refusal = "\n".join(
            block.get("refusal", "")
            for item in body.get("output") or []
            if item.get("type") == "message"
            for block in item.get("content") or []
            if block.get("type") == "refusal"
        )
        usage = {
            "prompt_tokens": int(usage_raw.get("input_tokens") or 0),
            "completion_tokens": int(usage_raw.get("output_tokens") or 0),
            "total_tokens": int(usage_raw.get("total_tokens") or 0),
            "thought_tokens": int(
                (usage_raw.get("output_tokens_details") or {}).get("reasoning_tokens")
                or 0
            ),
        }
        finish = (
            "length"
            if (body.get("incomplete_details") or {}).get("reason")
            == "max_output_tokens"
            else None
        )
    else:
        choice = (body.get("choices") or [{}])[0]
        raw = bl.answer_text(result) or ""
        refusal = (choice.get("message") or {}).get("refusal") or ""
        usage = {key: int(usage_raw.get(key) or 0) for key in _ZERO_USAGE}
        details = usage_raw.get("completion_tokens_details") or {}
        if details.get("reasoning_tokens") is not None:
            usage["thought_tokens"] = int(details["reasoning_tokens"])
        finish = choice.get("finish_reason")
    judgment = build_judge_result(lens, raw or refusal, usage, finish, prompt=prompt)
    if refusal:
        judgment.refused = True
        judgment.answer = "unknown"
    return judgment


async def _submit_all(
    lines: list[bl.BatchLine], endpoint: str, journal: Path, api_key: str | None
) -> list[bl.BatchHandle]:
    """Keep the manifest lock until a cancelled submission thread has finished."""
    task = asyncio.create_task(
        asyncio.to_thread(
            bl.submit_all, lines, endpoint=endpoint, checkpoint=journal, api_key=api_key
        )
    )
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    if cancelled:
        # The journal retains completed receipts even if the caller is cancelled.
        if not task.cancelled():
            task.exception()
        raise asyncio.CancelledError
    return task.result()


async def _judge_batchlane(
    lens: LayoutLens,
    requests: list[BatchRequest],
    max_tokens: int,
    resume: bool,
    path: Path,
    poll_interval: float,
    poll_timeout: float,
    fingerprint: str,
    reasoning_effort: str | None,
    image_detail: str,
) -> dict[str, JudgeResult]:
    """Submit once, poll without blocking the event loop, and persist judgments."""
    results: dict[str, JudgeResult] = {}
    valid = sorted(_split_missing_images(lens, requests, results), key=lambda r: r.id)
    if not valid:
        return results
    endpoint = "responses" if _is_native_openai(lens) else "chat.completions"
    manifest = _resume_manifest(
        path,
        resume=resume,
        fingerprint=fingerprint,
        model=lens.model,
        backend=_batch_backend_name(lens),
        max_tokens=max_tokens,
        reasoning_effort=reasoning_effort,
        image_detail=image_detail,
    )
    lines = [
        _batch_line(lens, request, max_tokens, reasoning_effort, image_detail)
        for request in valid
    ]
    plan = await asyncio.to_thread(bl.plan, lines, endpoint=endpoint)
    if not manifest:
        manifest = {
            "fingerprint": fingerprint,
            "model": lens.model,
            "backend": _batch_backend_name(lens),
            "max_tokens": max_tokens,
            "reasoning_effort": reasoning_effort,
            "image_detail": image_detail,
            "requests": [asdict(line) for line in lines],
            "jobs": [],
            "results": {},
        }
        _write_manifest(path, manifest)
    elif manifest.get("requests") != [asdict(line) for line in lines]:
        raise ValidationError(
            "Saved batch payload does not match these requests.",
            field="manifest_path",
            value=str(path),
        )
    jobs = manifest["jobs"]
    if not jobs:
        handles = await _submit_all(
            lines, endpoint, path.with_suffix(".batchlane.jsonl"), lens.api_key
        )
        jobs = [
            {"handle": handle.to_json(), "ids": [line.custom_id for line in chunk]}
            for handle, chunk in zip(handles, plan.chunks, strict=True)
        ]
        manifest["jobs"] = jobs
        _write_manifest(path, manifest)
    prompts = {request.id: request.prompt for request in valid}
    results.update(
        {
            key: JudgeResult(**value)
            for key, value in manifest.get("results", {}).items()
        }
    )
    for job in jobs:
        ids = set(job["ids"])
        if ids <= results.keys():
            continue
        handle = bl.BatchHandle.from_json(job["handle"])
        if handle.provider != plan.provider or handle.endpoint != endpoint:
            raise ValidationError(
                "Saved provider handle does not match this batch.",
                field="manifest_path",
                value=str(path),
            )
        deadline = time.monotonic() + poll_timeout
        while True:
            state = await asyncio.to_thread(bl.status, handle, api_key=lens.api_key)
            if state.is_terminal:
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            await asyncio.sleep(min(poll_interval, remaining))
        if not state.is_terminal:
            continue
        collected = await asyncio.to_thread(
            lambda receipt=handle: list(bl.results(receipt, api_key=lens.api_key))
        )
        seen: set[str] = set()
        for result in collected:
            if result.custom_id not in ids or result.custom_id in seen:
                raise ValidationError(
                    "Unexpected or duplicate batch result ID.",
                    field="custom_id",
                    value=result.custom_id,
                )
            seen.add(result.custom_id)
            results[result.custom_id] = _judgment(
                lens, result, prompts[result.custom_id]
            )
        for request_id in ids:
            results.setdefault(
                request_id,
                _unknown_result(lens, "no batch response", prompts[request_id]),
            )
        manifest["results"].update({key: asdict(results[key]) for key in ids})
        _write_manifest(path, manifest)
    for request in valid:
        results.setdefault(
            request.id, _unknown_result(lens, "batch still running", request.prompt)
        )
    return results


async def judge_batch(
    lens: LayoutLens,
    requests: list[BatchRequest],
    *,
    max_tokens: int | _Auto = AUTO,
    resume: bool = True,
    manifest_path: str | Path | None = None,
    poll_interval: float = 10.0,
    poll_timeout: float = 24 * 3600.0,
    reasoning_effort: str | None = None,
    image_detail: str = "auto",
) -> dict[str, JudgeResult]:
    """Judge every request via a batch transport (see :meth:`LayoutLens.judge_batch`).

    Uses batchlane for transport and retains the shared judgment contract.
    """
    if not requests:
        return {}

    if (
        not math.isfinite(poll_interval)
        or poll_interval <= 0
        or not math.isfinite(poll_timeout)
        or poll_timeout < 0
    ):
        raise ValidationError(
            "Poll interval must be positive and timeout nonnegative.",
            field="poll_interval",
        )
    if lens.api_base:
        raise ValidationError(
            "Batch providers do not support a custom api_base.",
            field="api_base",
            value=lens.api_base,
        )
    _validate_request_ids(requests)
    _validate_backend_configuration(lens)
    if (
        reasoning_effort is not None
        and reasoning_effort not in _OPENAI_REASONING_EFFORTS
    ):
        raise ValidationError(
            "OpenAI reasoning_effort must be one of none, low, medium, high, xhigh, or max.",
            field="reasoning_effort",
            value=reasoning_effort,
        )
    if image_detail not in _OPENAI_IMAGE_DETAILS:
        raise ValidationError(
            "OpenAI image_detail must be one of auto, low, high, or original.",
            field="image_detail",
            value=image_detail,
        )
    native_openai = _is_native_openai(lens)
    if not native_openai and (reasoning_effort is not None or image_detail != "auto"):
        raise ValidationError(
            "reasoning_effort and non-default image_detail are supported only by the "
            "native OpenAI Responses Batch backend.",
            field="provider",
            value=lens.provider,
        )
    max_tokens_value = resolved_max_tokens(lens.model, max_tokens)
    bl.get_adapter(_litellm_provider_for(lens.model))
    lens._ensure_api_key()  # noqa: SLF001
    backend_name = _batch_backend_name(lens)
    fingerprint = _batch_fingerprint(
        lens,
        requests,
        max_tokens_value,
        backend=backend_name,
        reasoning_effort=reasoning_effort,
        image_detail=image_detail,
    )
    if manifest_path is not None:
        path = Path(manifest_path)
    else:
        path = _default_manifest_path(lens, fingerprint)
        legacy_path = _legacy_manifest_path(lens, requests)
        if resume and not path.exists() and legacy_path.exists():
            raise ValidationError(
                "A legacy Batch manifest exists but does not attest its prompt, image, or token budget. "
                "Refusing to submit a possibly duplicate batch. After verifying that its provider "
                f"jobs belong to this exact request, copy it to '{path}' and add top-level fields "
                f"fingerprint='{fingerprint}', model='{lens.model}', backend='{backend_name}', and "
                f"max_tokens={max_tokens_value}, reasoning_effort={reasoning_effort!r}, and "
                f"image_detail={image_detail!r}, preserving jobs. Otherwise pass resume=False only "
                "when a fresh billed submission is intended. No submission was made.",
                field="manifest_path",
                value=str(legacy_path),
            )

    if not resume and path.exists():
        raise ValidationError(
            "resume=False requires a new manifest path; overwriting this manifest would lose "
            "provider job ids from a paid submission. No submission was made.",
            field="manifest_path",
            value=str(path),
        )

    if resume and not path.exists():
        overlaps = _overlapping_manifest_paths(
            path, lens, {request.id for request in requests}
        )
        if overlaps:
            raise ValidationError(
                "A prior Batch manifest for this model records submitted request ids that "
                "overlap this run, but it uses a different request fingerprint. Refusing a "
                "possibly duplicate paid submission after an upgrade or input change. Inspect "
                "and deliberately migrate/resume the prior provider jobs, or pass resume=False "
                "with a new manifest only when another billed run is intended. No submission "
                f"was made. Conflicting manifests: {', '.join(str(item) for item in overlaps[:5])}",
                field="manifest_path",
                value=str(path),
            )

    with _manifest_lock(path):
        return await _judge_batchlane(
            lens,
            requests,
            max_tokens_value,
            resume,
            path,
            poll_interval,
            poll_timeout,
            fingerprint,
            reasoning_effort,
            image_detail,
        )
