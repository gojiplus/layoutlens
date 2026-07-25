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
    return LayoutLens(api_key="sk-test", model="gpt-4o-mini", output_dir=str(tmp_path / "out"))


@pytest.fixture
def gemini_lens(tmp_path):
    return LayoutLens(
        api_key="sk-test",
        model="gemini/gemini-3-flash-preview",
        provider="gemini",
        output_dir=str(tmp_path / "out"),
    )


# --- litellm fakes --------------------------------------------------------


def _openai_batch_line(custom_id: str, content: str, *, finish_reason="stop", pt=100, ct=20) -> str:
    """One line of a completed litellm/OpenAI batch output file."""
    return json.dumps(
        {
            "custom_id": custom_id,
            "response": {
                "status_code": 200,
                "body": {
                    "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
                    "usage": {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": pt + ct},
                },
            },
        }
    )


def _make_litellm_mocks(output_text: str, *, status="completed", output_file_id="file-out"):
    """Build AsyncMocks for the four litellm batch helpers returning ``output_text``."""
    acreate_file = AsyncMock(return_value=SimpleNamespace(id="file-in"))
    acreate_batch = AsyncMock(return_value=SimpleNamespace(id="batch-1"))
    aretrieve_batch = AsyncMock(
        return_value=SimpleNamespace(status=status, output_file_id=output_file_id, error_file_id=None)
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
        results = await gemini_lens.judge_batch([BatchRequest("r1", png, "Is it good?")])
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
    payload = batch_mod._genai_inline_request(gemini_lens, req, 8000)
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
        results = await lens.judge_batch([BatchRequest("a", png, "p1"), BatchRequest("b", png2, "p2")])
    assert set(results) == {"a", "b"}
    assert all(isinstance(r, JudgeResult) for r in results.values())
    assert results["a"].answer == "A"
    assert results["b"].answer == "B"
    # Usage split recorded per request.
    assert results["a"].usage == {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}
    assert results["b"].usage == {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60}
    # The JSONL carried two lines.
    uploaded = acf.await_args.kwargs["file"].decode("utf-8").strip().splitlines()
    assert len(uploaded) == 2
    assert {json.loads(x)["custom_id"] for x in uploaded} == {"a", "b"}


@pytest.mark.asyncio
async def test_litellm_truncation_flag(lens, png):
    output = _openai_batch_line("r1", '{"answer": "A", "confidence": 0.9}', finish_reason="length") + "\n"
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
        results = await lens.judge_batch([BatchRequest("gone", missing, "p"), BatchRequest("ok", png, "p")])
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

    bm._write_manifest(
        bm.Path(manifest),
        {
            "model": "gpt-4o-mini",
            "backend": "litellm",
            "jobs": [{"batch_id": "prior", "input_file_id": "f", "ids": ["a"]}],
        },
    )

    prior_output = _openai_batch_line("a", '{"answer": "A", "confidence": 0.9}') + "\n"
    new_output = _openai_batch_line("b", '{"answer": "B", "confidence": 0.7}') + "\n"

    # aretrieve returns completed for both prior + new batch; afile_content
    # returns prior_output for the prior job then new_output for the new one.
    arb = AsyncMock(return_value=SimpleNamespace(status="completed", output_file_id="out", error_file_id=None))
    afc = AsyncMock(side_effect=[SimpleNamespace(text=prior_output), SimpleNamespace(text=new_output)])
    acf = AsyncMock(return_value=SimpleNamespace(id="file-in"))
    acb = AsyncMock(return_value=SimpleNamespace(id="batch-new"))

    with (
        patch.object(batch_mod, "acreate_file", acf),
        patch.object(batch_mod, "acreate_batch", acb),
        patch.object(batch_mod, "aretrieve_batch", arb),
        patch.object(batch_mod, "afile_content", afc),
    ):
        results = await lens.judge_batch(
            [BatchRequest("a", png, "p1"), BatchRequest("b", png2, "p2")],
            resume=True,
            manifest_path=manifest,
        )

    assert results["a"].answer == "A"
    assert results["b"].answer == "B"
    # Only ONE new batch submitted (for 'b'); 'a' recovered from the prior job.
    acf.assert_awaited_once()
    submitted_ids = {
        json.loads(x)["custom_id"] for x in acf.await_args.kwargs["file"].decode("utf-8").strip().splitlines()
    }
    assert submitted_ids == {"b"}


# --- genai backend with a fake client -------------------------------------


class _FakeGenaiResp:
    def __init__(self, text, prompt_tok, total_tok):
        self.text = text
        self.usage_metadata = SimpleNamespace(
            prompt_token_count=prompt_tok, candidates_token_count=10, total_token_count=total_tok
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
        results = await gemini_lens.judge_batch([BatchRequest("a", png, "p1"), BatchRequest("b", png2, "p2")])
    assert set(results) == {"a", "b"}
    assert results["a"].answer == "yes"
    assert results["a"].rationale == "x"
    assert results["b"].answer == "no"
    # Usage: output = total - prompt (Gemini bills thinking as output).
    assert results["a"].usage == {"prompt_tokens": 1200, "completion_tokens": 700, "total_tokens": 1900}


@pytest.mark.asyncio
async def test_genai_missing_image_unknown(gemini_lens, png, tmp_path):
    missing = str(tmp_path / "nope.png")
    with _fake_genai(batch_mod, {"ok": '{"answer": "yes", "confidence": 0.9}'}):
        results = await gemini_lens.judge_batch([BatchRequest("gone", missing, "p"), BatchRequest("ok", png, "p")])
    assert results["gone"].answer == "unknown"
    assert results["ok"].answer == "yes"


@pytest.mark.asyncio
async def test_empty_requests_returns_empty(lens):
    assert await lens.judge_batch([]) == {}
