"""Offline tests for multi-provider batch judging (``LayoutLens.judge_batch``).

No network, no keys, and google-genai is NOT installed — the genai backend is
exercised with a fake client (its SDK import is lazy and patched away). The
load-bearing tests are:

* **Parity**: each request's prompt is byte-identical to what :func:`judge`
  sends, for BOTH backends (litellm messages + genai inline text).
* **Backend dispatch**: ``gemini/*`` -> genai path; everything else -> litellm.
* **Resume**: a prior job covering a request is collected; only uncovered ids
  are re-submitted.

litellm batch helpers are patched at ``layoutlens.api.batch``.
"""

from __future__ import annotations

import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

import layoutlens.api.batch as batch_mod
from layoutlens.api.batch import BatchRequest, judge_batch
from layoutlens.api.core import LayoutLens
from layoutlens.api.judge import JudgeResult, build_judge_messages
from layoutlens.exceptions import ValidationError

# A minimal valid 1x1 PNG so image sources exist on disk.
_PNG_1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGNgAAIAAAUAAen63NgAAAAASUVORK5CYII="
)


@pytest.fixture
def png(tmp_path):
    p = tmp_path / "shot.png"
    p.write_bytes(_PNG_1x1)
    return str(p)


@pytest.fixture
def png2(tmp_path):
    p = tmp_path / "shot2.png"
    p.write_bytes(_PNG_1x1)
    return str(p)


@pytest.fixture
def lens(tmp_path):
    return LayoutLens(
        api_key="sk-test", model="gpt-4o-mini", output_dir=str(tmp_path / "out")
    )


@pytest.fixture
def gemini_lens(tmp_path):
    return LayoutLens(
        api_key="sk-test",
        model="gemini/gemini-3-flash-preview",
        provider="gemini",
        output_dir=str(tmp_path / "out"),
    )


# --- litellm fakes --------------------------------------------------------


def _openai_batch_line(
    custom_id: str, content: str, *, finish_reason="stop", pt=100, ct=20
) -> str:
    """One line of a completed litellm/OpenAI batch output file."""
    return json.dumps(
        {
            "custom_id": custom_id,
            "response": {
                "status_code": 200,
                "body": {
                    "choices": [
                        {
                            "message": {"content": content},
                            "finish_reason": finish_reason,
                        }
                    ],
                    "usage": {
                        "prompt_tokens": pt,
                        "completion_tokens": ct,
                        "total_tokens": pt + ct,
                    },
                },
            },
        }
    )


def _make_litellm_mocks(
    output_text: str, *, status="completed", output_file_id="file-out"
):
    """Build AsyncMocks for the four litellm batch helpers returning ``output_text``."""
    acreate_file = AsyncMock(return_value=SimpleNamespace(id="file-in"))
    acreate_batch = AsyncMock(return_value=SimpleNamespace(id="batch-1"))
    aretrieve_batch = AsyncMock(
        return_value=SimpleNamespace(
            status=status, output_file_id=output_file_id, error_file_id=None
        )
    )
    afile_content = AsyncMock(return_value=SimpleNamespace(text=output_text))
    return acreate_file, acreate_batch, aretrieve_batch, afile_content


# --- Backend dispatch -----------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_litellm_for_gpt(lens, png):
    output = _openai_batch_line("r1", '{"answer": "A", "confidence": 0.9}') + "\n"
    acf, acb, arb, afc = _make_litellm_mocks(output)
    with (
        patch.object(batch_mod, "acreate_file", acf),
        patch.object(batch_mod, "acreate_batch", acb),
        patch.object(batch_mod, "aretrieve_batch", arb),
        patch.object(batch_mod, "afile_content", afc),
        patch.object(batch_mod, "_genai_client") as genai_client,
    ):
        results = await lens.judge_batch([BatchRequest("r1", png, "Is it good?")])
    acf.assert_awaited()  # litellm path used
    genai_client.assert_not_called()  # genai path NOT used
    assert results["r1"].answer == "A"


@pytest.mark.asyncio
async def test_dispatch_genai_for_gemini_studio(gemini_lens, png):
    with (
        patch.object(batch_mod, "acreate_file", AsyncMock()) as acf,
        _fake_genai(batch_mod, {"r1": '{"answer": "no", "confidence": 0.8}'}),
    ):
        results = await gemini_lens.judge_batch(
            [BatchRequest("r1", png, "Is it good?")]
        )
    acf.assert_not_awaited()  # litellm path NOT used
    assert results["r1"].answer == "no"


# --- Parity: prompt byte-identical to judge() -----------------------------


@pytest.mark.asyncio
async def test_litellm_body_prompt_verbatim(lens, png):
    prompt = 'UIJudgeBench judge v3. Which is better, A or B? Reply {"answer": ...}.'
    output = _openai_batch_line("r1", '{"answer": "A", "confidence": 0.9}') + "\n"
    acf, acb, arb, afc = _make_litellm_mocks(output)
    with (
        patch.object(batch_mod, "acreate_file", acf),
        patch.object(batch_mod, "acreate_batch", acb),
        patch.object(batch_mod, "aretrieve_batch", arb),
        patch.object(batch_mod, "afile_content", afc),
    ):
        await lens.judge_batch([BatchRequest("r1", png, prompt)])

    # Decode the uploaded JSONL and inspect the single request's body.
    uploaded = acf.await_args.kwargs["file"]
    line = json.loads(uploaded.decode("utf-8").strip())
    assert line["custom_id"] == "r1"
    assert line["url"] == "/v1/chat/completions"
    body = line["body"]

    # The messages are byte-identical to what judge() builds.
    expected_messages = build_judge_messages(lens, png, prompt)
    assert body["messages"] == expected_messages
    text_parts = [c for c in body["messages"][0]["content"] if c["type"] == "text"]
    assert len(text_parts) == 1
    assert text_parts[0]["text"] == prompt  # verbatim, no scaffolding
    # Reasoning-aware max_tokens (gpt-4o-mini is non-reasoning -> 300) + policy.
    assert body["max_tokens"] == 300
    assert body["temperature"] == 0.0
    assert body["model"] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_genai_inline_text_verbatim(gemini_lens, png):
    prompt = 'Referring: click the primary CTA. Reply {"answer": ...}.'
    req = BatchRequest("r1", png, prompt)
    payload = batch_mod._genai_inline_request(req, 8000)
    parts = payload["contents"][0]["parts"]
    # Text part equals the prompt verbatim (parity with judge()).
    assert parts[0]["text"] == prompt
    # Image attached inline as base64 png.
    assert parts[1]["inline_data"]["mime_type"] == "image/png"
    assert parts[1]["inline_data"]["data"]
    # Reasoning-aware max_tokens (gemini-3 -> 8000) and id metadata.
    assert payload["config"]["max_output_tokens"] == 8000
    assert payload["metadata"] == {"req_id": "r1"}


# --- litellm end-to-end: 2 requests, keyed by id --------------------------


@pytest.mark.asyncio
async def test_litellm_two_requests_keyed_by_id(lens, png, png2):
    output = (
        _openai_batch_line("a", '{"answer": "A", "confidence": 0.9}', pt=100, ct=20)
        + "\n"
        + _openai_batch_line("b", '{"answer": "B", "confidence": 0.7}', pt=50, ct=10)
        + "\n"
    )
    acf, acb, arb, afc = _make_litellm_mocks(output)
    with (
        patch.object(batch_mod, "acreate_file", acf),
        patch.object(batch_mod, "acreate_batch", acb),
        patch.object(batch_mod, "aretrieve_batch", arb),
        patch.object(batch_mod, "afile_content", afc),
    ):
        results = await lens.judge_batch(
            [BatchRequest("a", png, "p1"), BatchRequest("b", png2, "p2")]
        )
    assert set(results) == {"a", "b"}
    assert all(isinstance(r, JudgeResult) for r in results.values())
    assert results["a"].answer == "A"
    assert results["b"].answer == "B"
    # Usage split recorded per request.
    assert results["a"].usage == {
        "prompt_tokens": 100,
        "completion_tokens": 20,
        "total_tokens": 120,
    }
    assert results["b"].usage == {
        "prompt_tokens": 50,
        "completion_tokens": 10,
        "total_tokens": 60,
    }
    # The JSONL carried two lines.
    uploaded = acf.await_args.kwargs["file"].decode("utf-8").strip().splitlines()
    assert len(uploaded) == 2
    assert {json.loads(x)["custom_id"] for x in uploaded} == {"a", "b"}


@pytest.mark.asyncio
async def test_litellm_truncation_flag(lens, png):
    output = (
        _openai_batch_line(
            "r1", '{"answer": "A", "confidence": 0.9}', finish_reason="length"
        )
        + "\n"
    )
    acf, acb, arb, afc = _make_litellm_mocks(output)
    with (
        patch.object(batch_mod, "acreate_file", acf),
        patch.object(batch_mod, "acreate_batch", acb),
        patch.object(batch_mod, "aretrieve_batch", arb),
        patch.object(batch_mod, "afile_content", afc),
    ):
        results = await lens.judge_batch([BatchRequest("r1", png, "p")])
    assert results["r1"].truncated is True


# --- Missing image --------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_image_yields_unknown_without_crash(lens, png, tmp_path):
    missing = str(tmp_path / "nope.png")
    output = _openai_batch_line("ok", '{"answer": "A", "confidence": 0.9}') + "\n"
    acf, acb, arb, afc = _make_litellm_mocks(output)
    with (
        patch.object(batch_mod, "acreate_file", acf),
        patch.object(batch_mod, "acreate_batch", acb),
        patch.object(batch_mod, "aretrieve_batch", arb),
        patch.object(batch_mod, "afile_content", afc),
    ):
        results = await lens.judge_batch(
            [BatchRequest("gone", missing, "p"), BatchRequest("ok", png, "p")]
        )
    assert results["gone"].answer == "unknown"
    assert results["gone"].parse_mode == "none"
    assert results["ok"].answer == "A"
    # Only the valid request entered the JSONL.
    uploaded = acf.await_args.kwargs["file"].decode("utf-8").strip().splitlines()
    assert len(uploaded) == 1
    assert json.loads(uploaded[0])["custom_id"] == "ok"


@pytest.mark.asyncio
async def test_all_images_missing_makes_no_batch_call(lens, tmp_path):
    missing = str(tmp_path / "nope.png")
    acf, acb, arb, afc = _make_litellm_mocks("")
    with (
        patch.object(batch_mod, "acreate_file", acf),
        patch.object(batch_mod, "acreate_batch", acb),
        patch.object(batch_mod, "aretrieve_batch", arb),
        patch.object(batch_mod, "afile_content", afc),
    ):
        results = await lens.judge_batch([BatchRequest("gone", missing, "p")])
    assert results["gone"].answer == "unknown"
    acf.assert_not_awaited()


# --- Resume ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_resume_litellm_skips_covered_ids(lens, png, png2):
    """A prior batch covering 'a' is collected; only 'b' is re-submitted."""
    manifest = str(lens.output_dir / "m.json")

    # First run: submit both a and b; batch returns only 'a' (simulate a kill
    # after 'a' completed by writing a manifest with a job covering [a, b] whose
    # output only has 'a'). Simpler: seed the manifest directly.
    import layoutlens.api.batch as bm

    requests = [BatchRequest("a", png, "p1"), BatchRequest("b", png2, "p2")]
    fingerprint = bm._batch_fingerprint(lens, requests, 300)
    bm._write_manifest(
        bm.Path(manifest),
        {
            "fingerprint": fingerprint,
            "model": "gpt-4o-mini",
            "backend": "litellm",
            "max_tokens": 300,
            "jobs": [{"batch_id": "prior", "input_file_id": "f", "ids": ["a"]}],
        },
    )

    prior_output = _openai_batch_line("a", '{"answer": "A", "confidence": 0.9}') + "\n"
    new_output = _openai_batch_line("b", '{"answer": "B", "confidence": 0.7}') + "\n"

    # aretrieve returns completed for both prior + new batch; afile_content
    # returns prior_output for the prior job then new_output for the new one.
    arb = AsyncMock(
        return_value=SimpleNamespace(
            status="completed", output_file_id="out", error_file_id=None
        )
    )
    afc = AsyncMock(
        side_effect=[
            SimpleNamespace(text=prior_output),
            SimpleNamespace(text=new_output),
        ]
    )
    acf = AsyncMock(return_value=SimpleNamespace(id="file-in"))
    acb = AsyncMock(return_value=SimpleNamespace(id="batch-new"))

    with (
        patch.object(batch_mod, "acreate_file", acf),
        patch.object(batch_mod, "acreate_batch", acb),
        patch.object(batch_mod, "aretrieve_batch", arb),
        patch.object(batch_mod, "afile_content", afc),
    ):
        results = await lens.judge_batch(requests, resume=True, manifest_path=manifest)

    assert results["a"].answer == "A"
    assert results["b"].answer == "B"
    # Only ONE new batch submitted (for 'b'); 'a' recovered from the prior job.
    acf.assert_awaited_once()
    submitted_ids = {
        json.loads(x)["custom_id"]
        for x in acf.await_args.kwargs["file"].decode("utf-8").strip().splitlines()
    }
    assert submitted_ids == {"b"}


def test_batch_fingerprint_binds_prompt_image_model_budget_and_order(lens, png, png2):
    requests = [BatchRequest("a", png, "p1"), BatchRequest("b", png2, "p2")]
    baseline = batch_mod._batch_fingerprint(lens, requests, 300)

    assert batch_mod._batch_fingerprint(lens, list(reversed(requests)), 300) == baseline
    assert batch_mod._batch_fingerprint(lens, requests, 301) != baseline
    assert (
        batch_mod._batch_fingerprint(
            lens, [BatchRequest("a", png, "changed"), requests[1]], 300
        )
        != baseline
    )

    original = batch_mod.Path(png2).read_bytes()
    batch_mod.Path(png2).write_bytes(original + b"changed")
    assert batch_mod._batch_fingerprint(lens, requests, 300) != baseline

    other_model = LayoutLens(
        api_key="sk", model="gpt-4o", output_dir=str(lens.output_dir)
    )
    assert batch_mod._batch_fingerprint(other_model, requests, 300) != baseline


@pytest.mark.asyncio
async def test_explicit_resume_manifest_mismatch_fails_before_submission(lens, png):
    manifest = lens.output_dir / "mismatch.json"
    batch_mod._write_manifest(
        manifest,
        {
            "fingerprint": "wrong",
            "model": lens.model,
            "backend": "litellm",
            "max_tokens": 300,
            "jobs": [],
        },
    )
    acf, acb, arb, afc = _make_litellm_mocks("")
    with (
        patch.object(batch_mod, "acreate_file", acf),
        patch.object(batch_mod, "acreate_batch", acb),
        patch.object(batch_mod, "aretrieve_batch", arb),
        patch.object(batch_mod, "afile_content", afc),
        pytest.raises(ValidationError, match="does not match the exact"),
    ):
        await lens.judge_batch([BatchRequest("r1", png, "p")], manifest_path=manifest)
    acf.assert_not_awaited()
    acb.assert_not_awaited()


@pytest.mark.asyncio
async def test_corrupt_resume_manifest_fails_before_submission(lens, png):
    manifest = lens.output_dir / "corrupt.json"
    manifest.write_text("{", encoding="utf-8")
    acf, acb, arb, afc = _make_litellm_mocks("")
    with (
        patch.object(batch_mod, "acreate_file", acf),
        patch.object(batch_mod, "acreate_batch", acb),
        patch.object(batch_mod, "aretrieve_batch", arb),
        patch.object(batch_mod, "afile_content", afc),
        pytest.raises(ValidationError, match="unreadable or invalid"),
    ):
        await lens.judge_batch([BatchRequest("r1", png, "p")], manifest_path=manifest)
    acf.assert_not_awaited()
    acb.assert_not_awaited()


@pytest.mark.asyncio
async def test_duplicate_request_ids_fail_before_submission(lens, png):
    acf, acb, arb, afc = _make_litellm_mocks("")
    with (
        patch.object(batch_mod, "acreate_file", acf),
        patch.object(batch_mod, "acreate_batch", acb),
        patch.object(batch_mod, "aretrieve_batch", arb),
        patch.object(batch_mod, "afile_content", afc),
        pytest.raises(ValidationError, match="ids must be unique"),
    ):
        await lens.judge_batch(
            [BatchRequest("r1", png, "p1"), BatchRequest("r1", png, "p2")]
        )
    acf.assert_not_awaited()
    acb.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_default_manifest_blocks_possible_duplicate(lens, png):
    requests = [BatchRequest("r1", png, "p")]
    legacy = batch_mod._legacy_manifest_path(lens, requests)
    batch_mod._write_manifest(
        legacy,
        {"model": lens.model, "backend": "litellm", "jobs": [{"batch_id": "paid"}]},
    )
    fingerprint = batch_mod._batch_fingerprint(lens, requests, 300)
    destination = batch_mod._default_manifest_path(lens, fingerprint)
    with pytest.raises(ValidationError, match="legacy Batch manifest") as exc_info:
        await lens.judge_batch(requests)
    assert fingerprint in str(exc_info.value)
    assert str(destination) in str(exc_info.value)


@pytest.mark.asyncio
async def test_resume_false_allows_intentional_fresh_batch_with_legacy_manifest(
    lens, png
):
    requests = [BatchRequest("r1", png, "p")]
    legacy = batch_mod._legacy_manifest_path(lens, requests)
    batch_mod._write_manifest(
        legacy,
        {"model": lens.model, "backend": "litellm", "jobs": [{"batch_id": "paid"}]},
    )
    output = _openai_batch_line("r1", '{"answer": "fresh"}') + "\n"
    acf, acb, arb, afc = _make_litellm_mocks(output)
    with (
        patch.object(batch_mod, "acreate_file", acf),
        patch.object(batch_mod, "acreate_batch", acb),
        patch.object(batch_mod, "aretrieve_batch", arb),
        patch.object(batch_mod, "afile_content", afc),
    ):
        results = await lens.judge_batch(requests, resume=False)

    assert results["r1"].answer == "fresh"
    acb.assert_awaited_once()


@pytest.mark.asyncio
async def test_resume_false_cannot_overwrite_paid_job_manifest(lens, png):
    requests = [BatchRequest("r1", png, "p")]
    fingerprint = batch_mod._batch_fingerprint(lens, requests, 300)
    manifest = batch_mod._default_manifest_path(lens, fingerprint)
    batch_mod._write_manifest(
        manifest,
        {
            "fingerprint": fingerprint,
            "model": lens.model,
            "backend": "litellm",
            "max_tokens": 300,
            "jobs": [{"batch_id": "paid"}],
        },
    )
    acf, acb, arb, afc = _make_litellm_mocks("")
    with (
        patch.object(batch_mod, "acreate_file", acf),
        patch.object(batch_mod, "acreate_batch", acb),
        patch.object(batch_mod, "aretrieve_batch", arb),
        patch.object(batch_mod, "afile_content", afc),
        pytest.raises(ValidationError, match="requires a new manifest path"),
    ):
        await lens.judge_batch(requests, resume=False)
    acf.assert_not_awaited()
    acb.assert_not_awaited()
    assert batch_mod._read_manifest(manifest)["jobs"] == [{"batch_id": "paid"}]


@pytest.mark.asyncio
async def test_manifest_lock_blocks_concurrent_duplicate_submission(lens, png):
    requests = [BatchRequest("r1", png, "p")]
    fingerprint = batch_mod._batch_fingerprint(lens, requests, 300)
    manifest = batch_mod._default_manifest_path(lens, fingerprint)
    lock = manifest.with_suffix(f"{manifest.suffix}.lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("active", encoding="utf-8")
    acf, acb, arb, afc = _make_litellm_mocks("")
    with (
        patch.object(batch_mod, "acreate_file", acf),
        patch.object(batch_mod, "acreate_batch", acb),
        patch.object(batch_mod, "aretrieve_batch", arb),
        patch.object(batch_mod, "afile_content", afc),
        pytest.raises(ValidationError, match="Another process owns"),
    ):
        await lens.judge_batch(requests)
    acf.assert_not_awaited()
    acb.assert_not_awaited()


# --- genai backend with a fake client -------------------------------------


class _FakeGenaiResp:
    def __init__(self, text, prompt_tok, total_tok):
        self.text = text
        self.usage_metadata = SimpleNamespace(
            prompt_token_count=prompt_tok,
            candidates_token_count=10,
            total_token_count=total_tok,
        )


class _FakeInlined:
    def __init__(self, req_id, resp):
        self.metadata = {"req_id": req_id}
        self.response = resp
        self.error = None


class _FakeJob:
    def __init__(self, name, dest):
        self.name = name
        self.state = "JOB_STATE_SUCCEEDED"
        self.dest = dest


class _FakeBatches:
    def __init__(self, texts_by_id):
        self._texts = texts_by_id
        self._submitted: list[str] = []

    def create(self, model, src, config):
        self._submitted = [r["metadata"]["req_id"] for r in src]
        return _FakeJob("batches/fake", None)

    def get(self, name):
        inlined = [
            _FakeInlined(rid, _FakeGenaiResp(self._texts[rid], 1200, 1900))
            for rid in self._submitted
            if rid in self._texts
        ]
        return _FakeJob(name, SimpleNamespace(inlined_responses=inlined))

    def list(self, config=None):
        return []


class _FakeGenaiClient:
    def __init__(self, texts_by_id):
        self.batches = _FakeBatches(texts_by_id)


def _fake_genai(mod, texts_by_id):
    """Patch _genai_client -> fake, and _submit_genai_chunk to bypass SDK types."""
    client = _FakeGenaiClient(texts_by_id)

    def _submit(client_, model, chunk, max_tokens, display_name):
        src = [{"metadata": {"req_id": req.id}} for req, _payload in chunk]
        return client_.batches.create(model=model, src=src, config={}).name

    return _MultiPatch(
        patch.object(mod, "_genai_client", return_value=client),
        patch.object(mod, "_submit_genai_chunk", _submit),
    )


class _MultiPatch:
    """Context manager applying several patch objects together."""

    def __init__(self, *patches):
        self._patches = patches

    def __enter__(self):
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self._patches:
            p.stop()
        return False


@pytest.mark.asyncio
async def test_genai_end_to_end_keyed_by_metadata(gemini_lens, png, png2):
    with _fake_genai(
        batch_mod,
        {
            "a": '{"answer": "yes", "confidence": 0.9, "rationale": "x"}',
            "b": '{"answer": "no", "confidence": 0.5}',
        },
    ):
        results = await gemini_lens.judge_batch(
            [BatchRequest("a", png, "p1"), BatchRequest("b", png2, "p2")]
        )
    assert set(results) == {"a", "b"}
    assert results["a"].answer == "yes"
    assert results["a"].rationale == "x"
    assert results["b"].answer == "no"
    # Usage: output = total - prompt (Gemini bills thinking as output).
    assert results["a"].usage == {
        "prompt_tokens": 1200,
        "completion_tokens": 700,
        "total_tokens": 1900,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("manifest_text", ['{"fingerprint": "wrong"}', "{"])
async def test_genai_invalid_resume_manifest_fails_before_client_or_submission(
    gemini_lens, png, manifest_text
):
    manifest = gemini_lens.output_dir / "invalid.json"
    manifest.write_text(manifest_text, encoding="utf-8")
    with (
        patch.object(batch_mod, "_genai_client") as client,
        patch.object(batch_mod, "_submit_genai_chunk") as submit,
        pytest.raises(ValidationError),
    ):
        await gemini_lens.judge_batch(
            [BatchRequest("r1", png, "p")], manifest_path=manifest
        )
    client.assert_not_called()
    submit.assert_not_called()


@pytest.mark.asyncio
async def test_genai_resume_collects_prior_job_and_submits_only_uncovered(
    gemini_lens, png, png2
):
    requests = [BatchRequest("a", png, "p1"), BatchRequest("b", png2, "p2")]
    fingerprint = batch_mod._batch_fingerprint(gemini_lens, requests, 8000)
    manifest = gemini_lens.output_dir / "resume-genai.json"
    batch_mod._write_manifest(
        manifest,
        {
            "fingerprint": fingerprint,
            "model": gemini_lens.model,
            "backend": "genai",
            "max_tokens": 8000,
            "jobs": [{"job_name": "batches/prior", "ids": ["a"]}],
        },
    )
    client = _FakeGenaiClient({"a": '{"answer": "yes"}', "b": '{"answer": "no"}'})
    client.batches._submitted = ["a"]

    def _submit(client_, model, chunk, max_tokens, display_name):
        src = [{"metadata": {"req_id": req.id}} for req, _payload in chunk]
        return client_.batches.create(model=model, src=src, config={}).name

    with (
        patch.object(batch_mod, "_genai_client", return_value=client),
        patch.object(batch_mod, "_submit_genai_chunk", _submit),
    ):
        results = await gemini_lens.judge_batch(requests, manifest_path=manifest)

    assert set(results) == {"a", "b"}
    assert results["a"].answer == "yes"
    assert results["b"].answer == "no"
    assert client.batches._submitted == ["b"]


@pytest.mark.asyncio
async def test_genai_missing_image_unknown(gemini_lens, png, tmp_path):
    missing = str(tmp_path / "nope.png")
    with _fake_genai(batch_mod, {"ok": '{"answer": "yes", "confidence": 0.9}'}):
        results = await gemini_lens.judge_batch(
            [BatchRequest("gone", missing, "p"), BatchRequest("ok", png, "p")]
        )
    assert results["gone"].answer == "unknown"
    assert results["ok"].answer == "yes"


@pytest.mark.asyncio
async def test_empty_requests_returns_empty(lens):
    assert await lens.judge_batch([]) == {}


# --- Anthropic is fully unsupported via litellm batch ---------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ["claude-sonnet-5", "anthropic/claude-opus-4-8"])
async def test_anthropic_batch_raises_clear_error(tmp_path, png, model):
    """litellm 1.80.10 supports neither acreate_file nor acreate_batch for
    anthropic, so a Claude model must fail loud and helpful at submit time."""
    lens = LayoutLens(
        api_key="sk", model=model, provider="anthropic", output_dir=str(tmp_path / "o")
    )
    acf, acb, arb, afc = _make_litellm_mocks("")
    with (
        patch.object(batch_mod, "acreate_file", acf),
        patch.object(batch_mod, "acreate_batch", acb),
        patch.object(batch_mod, "aretrieve_batch", arb),
        patch.object(batch_mod, "afile_content", afc),
        pytest.raises(ValidationError, match="Anthropic batch is not supported"),
    ):
        await lens.judge_batch([BatchRequest("r1", png, "p")])
    # Failed loud BEFORE any batch API call.
    acf.assert_not_awaited()
    acb.assert_not_awaited()


# --- Malformed/error output line -> unknown, no crash ---------------------


@pytest.mark.asyncio
async def test_litellm_malformed_line_yields_unknown(lens, png, png2):
    """An error/malformed output line (no body/choices) → unknown for that id;
    the batch does not crash and other ids parse normally."""
    good = _openai_batch_line("good", '{"answer": "A", "confidence": 0.9}')
    # Error line as a real batch API failure emits: response null / error set.
    err_line = json.dumps(
        {"custom_id": "bad", "response": None, "error": {"message": "boom"}}
    )
    output = good + "\n" + err_line + "\n"
    acf, acb, arb, afc = _make_litellm_mocks(output)
    with (
        patch.object(batch_mod, "acreate_file", acf),
        patch.object(batch_mod, "acreate_batch", acb),
        patch.object(batch_mod, "aretrieve_batch", arb),
        patch.object(batch_mod, "afile_content", afc),
    ):
        results = await lens.judge_batch(
            [BatchRequest("good", png, "p1"), BatchRequest("bad", png2, "p2")]
        )
    assert set(results) == {"good", "bad"}
    assert results["good"].answer == "A"
    # Malformed line: parsed into an unknown result (empty raw, no crash).
    assert results["bad"].answer == "unknown"
    assert results["bad"].parse_mode == "none"


@pytest.mark.asyncio
async def test_litellm_ignores_unrequested_custom_ids(lens, png):
    output = "\n".join(
        [
            _openai_batch_line("r1", '{"answer": "yes"}'),
            _openai_batch_line("ghost", '{"answer": "no"}'),
            "",
        ]
    )
    acf, acb, arb, afc = _make_litellm_mocks(output)
    with (
        patch.object(batch_mod, "acreate_file", acf),
        patch.object(batch_mod, "acreate_batch", acb),
        patch.object(batch_mod, "aretrieve_batch", arb),
        patch.object(batch_mod, "afile_content", afc),
    ):
        results = await lens.judge_batch([BatchRequest("r1", png, "p")])

    assert set(results) == {"r1"}
    assert results["r1"].answer == "yes"
