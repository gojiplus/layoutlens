"""Verify real batchlane transport, judgment parity, and durable resume."""

import asyncio
import base64
import hashlib
import json
import threading
from pathlib import Path

import httpx
import pytest
import respx

import layoutlens.api.batch as batch_mod
from layoutlens import LayoutLens
from layoutlens.api.batch import BatchRequest
from layoutlens.api.judge import build_judge_messages
from layoutlens.exceptions import ValidationError

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGNgAAIAAAUAAen63NgAAAAASUVORK5CYII="
)
BASE = "https://api.openai.com/v1"


@pytest.fixture
def png(tmp_path):
    path = tmp_path / "shot.png"
    path.write_bytes(PNG)
    return str(path)


@pytest.fixture
def png2(tmp_path):
    path = tmp_path / "shot2.png"
    path.write_bytes(PNG)
    return str(path)


@pytest.fixture
def lens(tmp_path):
    return LayoutLens(
        api_key="k",
        model="gpt-4o-mini",
        provider="litellm",
        output_dir=str(tmp_path / "out"),
    )


@pytest.fixture
def openai_lens(tmp_path):
    return LayoutLens(
        api_key="k",
        model="gpt-5.6-luna",
        provider="openai",
        output_dir=str(tmp_path / "out"),
    )


def response_line(
    key="r1",
    *,
    responses=False,
    text='{"answer":"yes","confidence":0.9}',
    finish=None,
    refusal=None,
):
    if responses:
        content = (
            [{"type": "refusal", "refusal": refusal}]
            if refusal
            else [{"type": "output_text", "text": text}]
        )
        body = {
            "output": [{"type": "message", "content": content}],
            "usage": {
                "input_tokens": 80,
                "output_tokens": 25,
                "total_tokens": 105,
                "output_tokens_details": {"reasoning_tokens": 7},
            },
        }
        if finish:
            body["incomplete_details"] = {"reason": "max_output_tokens"}
    else:
        body = {
            "choices": [{"message": {"content": text}, "finish_reason": finish}],
            "usage": {
                "prompt_tokens": 80,
                "completion_tokens": 25,
                "total_tokens": 105,
            },
        }
    return json.dumps(
        {"custom_id": key, "response": {"status_code": 200, "body": body}}
    )


@pytest.fixture
def api():
    with respx.mock(assert_all_called=False) as router:
        router.post(f"{BASE}/files").respond(200, json={"id": "file-in"})
        router.post(f"{BASE}/batches").respond(200, json={"id": "batch-1"})
        router.get(f"{BASE}/batches/batch-1").respond(
            200, json={"id": "batch-1", "status": "completed", "output_file_id": "out"}
        )
        router.get(f"{BASE}/files/out/content").respond(200, text=response_line())
        yield router


def uploaded_body(api):
    content = api.post(f"{BASE}/files").calls[0].request.content.decode()
    return next(
        json.loads(line)["body"]
        for line in content.splitlines()
        if line.startswith('{"custom_id"')
    )


@pytest.mark.asyncio
async def test_native_responses_preserves_prompt_image_reasoning_and_usage(
    api, openai_lens, png
):
    api.get(f"{BASE}/files/out/content").respond(
        200, text=response_line(responses=True)
    )
    results = await openai_lens.judge_batch(
        [BatchRequest("r1", png, "verbatim prompt")],
        max_tokens=256,
        reasoning_effort="low",
        image_detail="original",
    )
    body = uploaded_body(api)
    assert body["model"] == "gpt-5.6-luna"
    assert body["max_output_tokens"] == 256
    assert body["reasoning"] == {"effort": "low"}
    assert "temperature" not in body
    content = body["input"][0]["content"]
    assert content[0] == {"type": "input_text", "text": "verbatim prompt"}
    assert content[1]["detail"] == "original"
    assert base64.b64decode(content[1]["image_url"].split(",")[1]) == PNG
    assert (
        json.loads(api.post(f"{BASE}/batches").calls[0].request.content)["endpoint"]
        == "/v1/responses"
    )
    result = results["r1"]
    assert result.answer == "yes"
    assert result.prompt_sha256 == hashlib.sha256(b"verbatim prompt").hexdigest()
    assert result.usage == {
        "prompt_tokens": 80,
        "completion_tokens": 25,
        "total_tokens": 105,
        "thought_tokens": 7,
    }


@pytest.mark.asyncio
async def test_chat_transport_matches_judge_messages_and_joins_out_of_order(
    api, lens, png
):
    api.get(f"{BASE}/files/out/content").respond(
        200, text=response_line("b", text="no") + "\n" + response_line("a")
    )
    results = await lens.judge_batch(
        [BatchRequest("a", png, "first"), BatchRequest("b", png, "second")]
    )
    assert results["a"].answer == "yes"
    assert results["b"].answer == "no"
    assert uploaded_body(api)["messages"] == build_judge_messages(lens, png, "first")


@pytest.mark.asyncio
@pytest.mark.parametrize("native", [False, True])
async def test_truncation_survives_transport(api, lens, openai_lens, png, native):
    api.get(f"{BASE}/files/out/content").respond(
        200, text=response_line(responses=native, finish="length")
    )
    result = await (openai_lens if native else lens).judge_batch(
        [BatchRequest("r1", png, "prompt")]
    )
    assert result["r1"].truncated


@pytest.mark.asyncio
async def test_structured_refusal_is_not_a_judgment(api, openai_lens, png):
    api.get(f"{BASE}/files/out/content").respond(
        200, text=response_line(responses=True, refusal="Restricted content")
    )
    result = (await openai_lens.judge_batch([BatchRequest("r1", png, "prompt")]))["r1"]
    assert result.refused
    assert result.answer == "unknown"
    assert result.raw == "Restricted content"


@pytest.mark.asyncio
async def test_completed_results_survive_provider_retention(api, lens, png, tmp_path):
    path = tmp_path / "manifest.json"
    req = [BatchRequest("r1", png, "prompt")]
    first = await lens.judge_batch(req, manifest_path=path)
    api.reset()
    path.with_suffix(".batchlane.jsonl").unlink()
    second = await lens.judge_batch(req, manifest_path=path)
    assert second == first
    assert not api.calls


@pytest.mark.asyncio
async def test_timeout_remains_resumable_and_does_not_cache_unknown(
    api, lens, png, tmp_path
):
    path = tmp_path / "manifest.json"
    req = [BatchRequest("r1", png, "prompt")]
    api.get(f"{BASE}/batches/batch-1").respond(200, json={"status": "in_progress"})
    pending = await lens.judge_batch(req, manifest_path=path, poll_timeout=0)
    assert pending["r1"].answer == "unknown"
    assert json.loads(path.read_text())["results"] == {}
    api.get(f"{BASE}/batches/batch-1").respond(
        200, json={"status": "completed", "output_file_id": "out"}
    )
    done = await lens.judge_batch(req, manifest_path=path)
    assert done["r1"].answer == "yes"
    assert api.post(f"{BASE}/batches").call_count == 1


@pytest.mark.asyncio
async def test_missing_output_is_not_resubmitted(api, lens, png, tmp_path):
    api.get(f"{BASE}/files/out/content").respond(200, text="")
    path = tmp_path / "manifest.json"
    req = [BatchRequest("r1", png, "prompt")]
    assert (await lens.judge_batch(req, manifest_path=path))["r1"].answer == "unknown"
    assert (await lens.judge_batch(req, manifest_path=path))["r1"].answer == "unknown"
    assert api.post(f"{BASE}/batches").call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["duplicate", "unexpected"])
async def test_invalid_result_ids_refuse(api, lens, png, kind):
    text = (
        response_line() + "\n" + response_line()
        if kind == "duplicate"
        else response_line("other")
    )
    api.get(f"{BASE}/files/out/content").respond(200, text=text)
    with pytest.raises(ValidationError, match="result ID"):
        await lens.judge_batch([BatchRequest("r1", png, "prompt")])


@pytest.mark.asyncio
async def test_missing_images_produce_unknown_without_submission(api, lens, tmp_path):
    result = await lens.judge_batch(
        [BatchRequest("r1", str(tmp_path / "absent.png"), "prompt")]
    )
    assert result["r1"].answer == "unknown"
    assert not api.calls
    assert await lens.judge_batch([]) == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind", ["prompt", "corrupt", "overwrite", "locked", "duplicate"]
)
async def test_manifest_and_input_guards_run_before_submission(
    api, lens, png, tmp_path, kind
):
    path = tmp_path / "manifest.json"
    req = [BatchRequest("r1", png, "prompt")]
    kwargs = {"manifest_path": path}
    if kind in {"prompt", "overwrite"}:
        await lens.judge_batch(req, **kwargs)
        api.reset()
        if kind == "prompt":
            req[0].prompt = "changed"
        else:
            kwargs["resume"] = False
    elif kind == "corrupt":
        path.write_text("not json")
    elif kind == "locked":
        path.with_suffix(".json.lock").touch()
    else:
        req += req
    with pytest.raises(ValidationError):
        await lens.judge_batch(req, **kwargs)
    assert not api.calls


@pytest.mark.asyncio
async def test_cancelled_submission_keeps_lock_and_receipt_until_thread_finishes(
    api, lens, png, tmp_path
):
    started, release = threading.Event(), threading.Event()

    def create(request):
        started.set()
        assert release.wait(5)
        return httpx.Response(200, json={"id": "batch-1"})

    api.post(f"{BASE}/batches").mock(side_effect=create)
    path = tmp_path / "manifest.json"
    req = [BatchRequest("r1", png, "prompt")]
    task = asyncio.create_task(lens.judge_batch(req, manifest_path=path))
    assert await asyncio.to_thread(started.wait, 5)
    task.cancel()
    await asyncio.sleep(0)
    try:
        with pytest.raises(ValidationError, match="owns"):
            await lens.judge_batch(req, manifest_path=path)
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    result = await lens.judge_batch(req, manifest_path=path)
    assert result["r1"].answer == "yes"
    assert api.post(f"{BASE}/batches").call_count == 1


@pytest.mark.asyncio
async def test_gemini_uses_batchlane_with_keyed_results(api, png, tmp_path):
    lens = LayoutLens(
        api_key="gemini-key",
        model="gemini/gemini-2.5-flash",
        provider="gemini",
        output_dir=str(tmp_path / "gemini"),
    )
    base = "https://generativelanguage.googleapis.com/v1beta"
    create = api.post(f"{base}/models/gemini-2.5-flash:batchGenerateContent").respond(
        200, json={"name": "batches/g"}
    )
    api.get(f"{base}/batches/g").respond(
        200,
        json={
            "metadata": {"state": "JOB_STATE_SUCCEEDED"},
            "response": {
                "inlinedResponses": [
                    {
                        "metadata": {"key": "r1"},
                        "response": {
                            "candidates": [
                                {
                                    "content": {
                                        "role": "model",
                                        "parts": [{"text": "yes"}],
                                    },
                                    "finishReason": "STOP",
                                }
                            ],
                            "usageMetadata": {
                                "promptTokenCount": 5,
                                "candidatesTokenCount": 1,
                                "totalTokenCount": 6,
                            },
                        },
                    }
                ]
            },
        },
    )
    result = await lens.judge_batch([BatchRequest("r1", png, "exact prompt")])
    assert result["r1"].answer == "yes"
    body = json.loads(create.calls[0].request.content)
    request = body["batch"]["input_config"]["requests"]["requests"][0]["request"]
    assert request["contents"][0]["parts"][0]["text"] == "exact prompt"
    assert create.calls[0].request.headers["x-goog-api-key"] == "gemini-key"


@pytest.mark.asyncio
async def test_anthropic_batches_are_now_supported(api, png, tmp_path):
    lens = LayoutLens(
        api_key="anthropic-key",
        model="claude-sonnet-4-5",
        provider="anthropic",
        output_dir=str(tmp_path / "anthropic"),
    )
    base = "https://api.anthropic.com/v1/messages/batches"
    api.post(base).respond(200, json={"id": "a"})
    api.get(f"{base}/a").respond(
        200,
        json={
            "processing_status": "ended",
            "request_counts": {"succeeded": 1},
            "results_url": "https://api.anthropic.com/results/a",
        },
    )
    api.get("https://api.anthropic.com/results/a").respond(
        200,
        text=json.dumps(
            {
                "custom_id": "r1",
                "result": {
                    "type": "succeeded",
                    "message": {
                        "id": "m",
                        "type": "message",
                        "role": "assistant",
                        "model": "claude-sonnet-4-5",
                        "content": [{"type": "text", "text": "yes"}],
                        "stop_reason": "end_turn",
                        "usage": {"input_tokens": 5, "output_tokens": 1},
                    },
                },
            }
        ),
    )
    assert (await lens.judge_batch([BatchRequest("r1", png, "prompt")]))[
        "r1"
    ].answer == "yes"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs",
    [
        {"api_base": "https://example.com"},
        {"provider": "openai", "model": "anthropic/claude-sonnet-4-5"},
    ],
)
async def test_unsafe_or_unsupported_configuration_refuses(api, png, tmp_path, kwargs):
    lens = LayoutLens(api_key="k", output_dir=str(tmp_path), **kwargs)
    with pytest.raises(ValidationError):
        await lens.judge_batch([BatchRequest("r1", png, "prompt")])
    assert not api.calls


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

    other_endpoint = LayoutLens(
        api_key="sk",
        model=lens.model,
        api_base="https://example.com",
        output_dir=str(lens.output_dir),
    )
    assert batch_mod._batch_fingerprint(other_endpoint, requests, 300) != baseline


def test_openai_fingerprint_binds_reasoning_effort_and_image_detail(openai_lens, png):
    requests = [BatchRequest("a", png, "prompt")]
    baseline = batch_mod._batch_fingerprint(
        openai_lens,
        requests,
        256,
        reasoning_effort="low",
        image_detail="original",
    )
    assert (
        batch_mod._batch_fingerprint(
            openai_lens,
            requests,
            256,
            reasoning_effort="medium",
            image_detail="original",
        )
        != baseline
    )
    assert (
        batch_mod._batch_fingerprint(
            openai_lens,
            requests,
            256,
            reasoning_effort="low",
            image_detail="low",
        )
        != baseline
    )
