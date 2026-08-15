"""Tests for the faithful judge interface (``LayoutLens.judge`` + ``JudgeResult``).

The judge interface lets LayoutLens act as a reference judge for external eval
harnesses (UIJudgeBench first): the caller-supplied prompt is sent VERBATIM (no
persona, no scaffolding, no appended JSON contract), the structured answer is
parsed, per-model parameter policy is honored, and real token usage is recorded.

All tests are offline — ``acompletion`` is patched at ``layoutlens.api.judge``.
"""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from layoutlens.api.core import LayoutLens
from layoutlens.api.judge import (
    JudgeResult,
    detect_refusal,
    parse_judge_response,
)
from layoutlens.exceptions import ValidationError

# A minimal valid 1x1 PNG so image sources exist on disk.
_PNG_1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGNgAAIAAAUAAen63NgAAAAASUVORK5CYII="
)

# Scaffolding substrings that must NEVER appear in a verbatim judge prompt.
_SCAFFOLDING_MARKERS = [
    "Respond in this JSON format",
    "Analyze this UI screenshot",
    "Your confidence level",
    "USER QUERY:",
    "Focus on:",
]


def _mock_response(
    content: str,
    *,
    prompt_tokens=11,
    completion_tokens=7,
    total_tokens=18,
    finish_reason="stop",
) -> MagicMock:
    response = MagicMock()
    response.choices[0].message.content = content
    response.choices[0].finish_reason = finish_reason
    response.usage.prompt_tokens = prompt_tokens
    response.usage.completion_tokens = completion_tokens
    response.usage.total_tokens = total_tokens
    return response


@pytest.fixture
def png(tmp_path):
    p = tmp_path / "shot.png"
    p.write_bytes(_PNG_1x1)
    return str(p)


@pytest.fixture
def lens(tmp_path):
    return LayoutLens(
        api_key="sk-test", model="gpt-4o-mini", output_dir=str(tmp_path / "out")
    )


# --- Verbatim passthrough -------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_sent_verbatim(lens, png):
    prompt = 'You are UIJudgeBench judge v3. Which layout is better, A or B? Reply {"answer": ...}.'
    resp = _mock_response('{"answer": "A", "confidence": 0.9, "rationale": "cleaner"}')

    with patch(
        "layoutlens.api.judge.acompletion", new=AsyncMock(return_value=resp)
    ) as mock_llm:
        await lens.judge(png, prompt)

    messages = mock_llm.await_args.kwargs["messages"]
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    content = messages[0]["content"]

    text_parts = [c for c in content if c["type"] == "text"]
    image_parts = [c for c in content if c["type"] == "image_url"]

    # Exactly one text part, equal to the prompt VERBATIM (no scaffolding).
    assert len(text_parts) == 1
    assert text_parts[0]["text"] == prompt
    for marker in _SCAFFOLDING_MARKERS:
        assert marker not in text_parts[0]["text"]

    # Exactly one image part.
    assert len(image_parts) == 1
    assert image_parts[0]["image_url"]["url"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_no_system_persona_message(lens, png):
    resp = _mock_response('{"answer": "yes", "confidence": 0.5}')
    with patch(
        "layoutlens.api.judge.acompletion", new=AsyncMock(return_value=resp)
    ) as mock_llm:
        await lens.judge(png, "Is it good?")
    messages = mock_llm.await_args.kwargs["messages"]
    assert all(m["role"] != "system" for m in messages)


@pytest.mark.asyncio
async def test_jpeg_mime_from_extension(lens, tmp_path):
    jpg = tmp_path / "shot.jpg"
    jpg.write_bytes(_PNG_1x1)
    resp = _mock_response('{"answer": "yes", "confidence": 0.5}')
    with patch(
        "layoutlens.api.judge.acompletion", new=AsyncMock(return_value=resp)
    ) as mock_llm:
        await lens.judge(str(jpg), "Is it good?")
    content = mock_llm.await_args.kwargs["messages"][0]["content"]
    image_parts = [c for c in content if c["type"] == "image_url"]
    assert image_parts[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")


# --- Parameter policy -----------------------------------------------------


@pytest.mark.asyncio
async def test_judge_omits_temperature_for_sonnet5(tmp_path, png):
    lens = LayoutLens(
        api_key="sk",
        model="claude-sonnet-5",
        provider="anthropic",
        output_dir=str(tmp_path / "o"),
    )
    resp = _mock_response('{"answer": "A", "confidence": 0.5}')
    with patch(
        "layoutlens.api.judge.acompletion", new=AsyncMock(return_value=resp)
    ) as mock_llm:
        await lens.judge(png, "prompt")
    assert "temperature" not in mock_llm.await_args.kwargs


@pytest.mark.asyncio
async def test_judge_includes_temperature_for_gpt4o(lens, png):
    resp = _mock_response('{"answer": "A", "confidence": 0.5}')
    with patch(
        "layoutlens.api.judge.acompletion", new=AsyncMock(return_value=resp)
    ) as mock_llm:
        await lens.judge(png, "prompt")
    assert mock_llm.await_args.kwargs["temperature"] == 0.0


@pytest.mark.asyncio
async def test_judge_max_tokens_from_kwarg(lens, png):
    resp = _mock_response('{"answer": "A", "confidence": 0.5}')
    with patch(
        "layoutlens.api.judge.acompletion", new=AsyncMock(return_value=resp)
    ) as mock_llm:
        await lens.judge(png, "prompt", max_tokens=1234)
    assert mock_llm.await_args.kwargs["max_tokens"] == 1234


# --- Reasoning-aware AUTO max_tokens --------------------------------------


@pytest.mark.asyncio
async def test_judge_auto_max_tokens_non_reasoning(lens, png):
    """AUTO default resolves to 300 for a non-reasoning model (gpt-4o-mini)."""
    resp = _mock_response('{"answer": "A", "confidence": 0.5}')
    with patch(
        "layoutlens.api.judge.acompletion", new=AsyncMock(return_value=resp)
    ) as mock_llm:
        await lens.judge(png, "prompt")
    assert mock_llm.await_args.kwargs["max_tokens"] == 300


@pytest.mark.asyncio
async def test_judge_auto_max_tokens_reasoning(tmp_path, png):
    """AUTO default resolves to 8000 for a reasoning model (gemini-3)."""
    lens = LayoutLens(
        api_key="sk",
        model="gemini/gemini-3-flash-preview",
        provider="gemini",
        output_dir=str(tmp_path / "o"),
    )
    resp = _mock_response('{"answer": "A", "confidence": 0.5}')
    with patch(
        "layoutlens.api.judge.acompletion", new=AsyncMock(return_value=resp)
    ) as mock_llm:
        await lens.judge(png, "prompt")
    assert mock_llm.await_args.kwargs["max_tokens"] == 8000


# --- Truncation flag ------------------------------------------------------


@pytest.mark.asyncio
async def test_truncated_flag_set_on_length_finish(lens, png):
    resp = _mock_response('{"answer": "A", "confidence": 0.5}', finish_reason="length")
    with patch("layoutlens.api.judge.acompletion", new=AsyncMock(return_value=resp)):
        result = await lens.judge(png, "prompt")
    assert result.truncated is True


@pytest.mark.asyncio
async def test_truncated_flag_false_on_stop_finish(lens, png):
    resp = _mock_response('{"answer": "A", "confidence": 0.5}', finish_reason="stop")
    with patch("layoutlens.api.judge.acompletion", new=AsyncMock(return_value=resp)):
        result = await lens.judge(png, "prompt")
    assert result.truncated is False


# --- api_base -------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_base_reaches_acompletion(tmp_path, png):
    lens = LayoutLens(
        api_key="sk",
        model="ollama/qwen2.5vl",
        provider="litellm",
        api_base="http://localhost:11434",
        output_dir=str(tmp_path / "o"),
    )
    resp = _mock_response('{"answer": "yes", "confidence": 0.5}')
    with patch(
        "layoutlens.api.judge.acompletion", new=AsyncMock(return_value=resp)
    ) as mock_llm:
        await lens.judge(png, "prompt")
    assert mock_llm.await_args.kwargs["api_base"] == "http://localhost:11434"


@pytest.mark.asyncio
async def test_api_base_absent_by_default(lens, png):
    resp = _mock_response('{"answer": "yes", "confidence": 0.5}')
    with patch(
        "layoutlens.api.judge.acompletion", new=AsyncMock(return_value=resp)
    ) as mock_llm:
        await lens.judge(png, "prompt")
    assert "api_base" not in mock_llm.await_args.kwargs


# --- Usage split ----------------------------------------------------------


@pytest.mark.asyncio
async def test_usage_split_recorded(lens, png):
    resp = _mock_response(
        '{"answer": "yes", "confidence": 0.5}',
        prompt_tokens=100,
        completion_tokens=20,
        total_tokens=120,
    )
    with patch("layoutlens.api.judge.acompletion", new=AsyncMock(return_value=resp)):
        result = await lens.judge(png, "prompt")
    assert result.usage == {
        "prompt_tokens": 100,
        "completion_tokens": 20,
        "total_tokens": 120,
    }


@pytest.mark.asyncio
async def test_usage_defaults_to_zero_when_absent(lens, png):
    resp = MagicMock()
    resp.choices[0].message.content = '{"answer": "yes", "confidence": 0.5}'
    resp.usage = None
    with patch("layoutlens.api.judge.acompletion", new=AsyncMock(return_value=resp)):
        result = await lens.judge(png, "prompt")
    assert result.usage == {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }


# --- Cache bypass ---------------------------------------------------------


@pytest.mark.asyncio
async def test_judge_bypasses_cache(lens, png):
    """Two identical judge calls must both hit the model (no caching)."""
    resp = _mock_response('{"answer": "A", "confidence": 0.9}')
    with patch(
        "layoutlens.api.judge.acompletion", new=AsyncMock(return_value=resp)
    ) as mock_llm:
        await lens.judge(png, "same prompt")
        await lens.judge(png, "same prompt")
    assert mock_llm.await_count == 2


# --- Missing image --------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_image_raises_validation_error(lens, tmp_path):
    missing = str(tmp_path / "nope.png")
    with (
        patch("layoutlens.api.judge.acompletion", new=AsyncMock()) as mock_llm,
        pytest.raises(ValidationError),
    ):
        await lens.judge(missing, "prompt")
    mock_llm.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_image_raises_validation_error_even_without_api_key(
    tmp_path, monkeypatch
):
    """Image existence is validated BEFORE the API-key check (per brief)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    lens = LayoutLens(
        api_key=None, model="gpt-4o-mini", output_dir=str(tmp_path / "out")
    )
    assert lens.api_key is None
    missing = str(tmp_path / "nope.png")
    with (
        patch("layoutlens.api.judge.acompletion", new=AsyncMock()) as mock_llm,
        pytest.raises(ValidationError),
    ):
        await lens.judge(missing, "prompt")
    mock_llm.assert_not_awaited()


# --- Result plumbing ------------------------------------------------------


@pytest.mark.asyncio
async def test_result_fields_populated(lens, png):
    resp = _mock_response(
        '{"answer": "A", "confidence": 0.9, "rationale": "cleaner nav"}'
    )
    with patch("layoutlens.api.judge.acompletion", new=AsyncMock(return_value=resp)):
        result = await lens.judge(png, "prompt")
    assert isinstance(result, JudgeResult)
    assert result.answer == "A"
    assert result.confidence == 0.9
    assert result.rationale == "cleaner nav"
    assert result.model == "gpt-4o-mini"
    assert result.parse_mode == "json"
    assert result.refused is False
    assert '"answer": "A"' in result.raw


# --- Parsing (pure function) ----------------------------------------------


def test_parse_strict_json():
    answer, conf, rationale, mode = parse_judge_response(
        '{"answer": "B", "confidence": 0.8, "rationale": "x"}'
    )
    assert (answer, conf, rationale, mode) == ("B", 0.8, "x", "json")


def test_parse_fenced_json():
    raw = '```json\n{"answer": "A", "confidence": 0.7}\n```'
    answer, conf, _rationale, mode = parse_judge_response(raw)
    assert answer == "A"
    assert conf == 0.7
    assert mode == "json"


def test_parse_json_with_surrounding_prose():
    raw = 'Here is my verdict.\n{"answer": "A", "confidence": 0.6}\nThanks!'
    answer, conf, _rationale, mode = parse_judge_response(raw)
    assert answer == "A"
    assert conf == 0.6
    assert mode == "json"


def test_parse_picks_answer_object_among_multiple():
    # Reviewer repro: a stray leading object must not swallow the real verdict.
    raw = 'prefix {"x":1} more {"answer":"A"} end'
    answer, _conf, _rationale, mode = parse_judge_response(raw)
    assert answer == "A"
    assert mode == "json"


def test_parse_nested_brace_prose():
    raw = 'Notes {a set {1,2}} then {"answer":"B","confidence":0.4} done'
    answer, conf, _rationale, mode = parse_judge_response(raw)
    assert answer == "B"
    assert conf == 0.4
    assert mode == "json"


def test_parse_json_value_containing_braces():
    # Braces inside a JSON string value must not confuse brace counting.
    raw = '{"answer": "A", "rationale": "use {curly} braces { unbalanced"}'
    answer, _conf, rationale, mode = parse_judge_response(raw)
    assert answer == "A"
    assert rationale == "use {curly} braces { unbalanced"
    assert mode == "json"


def test_parse_reasoning_alias():
    _answer, _conf, rationale, mode = parse_judge_response(
        '{"answer": "A", "confidence": 0.5, "reasoning": "why"}'
    )
    assert rationale == "why"
    assert mode == "json"


def test_parse_yes_no_fallback():
    answer, conf, _rationale, mode = parse_judge_response(
        "Yes, the contrast is sufficient."
    )
    assert answer == "yes"
    assert mode == "fallback"
    assert conf == 0.0


def test_parse_no_fallback():
    answer, _conf, _rationale, mode = parse_judge_response(
        "No — the button is too small."
    )
    assert answer == "no"
    assert mode == "fallback"


def test_parse_garbage_is_unknown():
    answer, conf, rationale, mode = parse_judge_response(
        "The weather is pleasant today."
    )
    assert answer == "unknown"
    assert mode == "none"
    assert conf == 0.0
    assert rationale == ""


def test_parse_confidence_clamped():
    _, conf, _, _ = parse_judge_response('{"answer": "A", "confidence": 5}')
    assert conf == 1.0
    _, conf2, _, _ = parse_judge_response('{"answer": "A", "confidence": -1}')
    assert conf2 == 0.0


def test_parse_confidence_unparseable_defaults_zero():
    _, conf, _, _ = parse_judge_response('{"answer": "A", "confidence": "high"}')
    assert conf == 0.0


# --- Refusal detection ----------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "I can't help with that.",
        "I cannot assist with this request.",
        "I'm unable to evaluate this image.",
        "As an AI, I do not have opinions.",
    ],
)
def test_detect_refusal_positive(text):
    assert detect_refusal(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "Yes, the layout is clear.",
        '{"answer": "A", "confidence": 0.9}',
        "The navigation could not be simpler.",
    ],
)
def test_detect_refusal_negative(text):
    assert detect_refusal(text) is False


@pytest.mark.asyncio
async def test_refusal_flag_set_but_raw_returned(lens, png):
    resp = _mock_response("I can't assist with evaluating this.")
    with patch("layoutlens.api.judge.acompletion", new=AsyncMock(return_value=resp)):
        result = await lens.judge(png, "prompt")
    assert result.refused is True
    assert result.raw == "I can't assist with evaluating this."
