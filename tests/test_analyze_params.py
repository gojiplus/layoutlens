"""Tests that the analyze path honors the per-model parameter policy.

Previously ``_call_vision_api`` hardcoded ``temperature=0.1``. It now resolves
temperature from the (optional) constructor ``temperature`` override, defaulting
to 0.1 to preserve existing behavior, and routes it through the param policy so
Claude 4.6+/5 models omit temperature entirely.
"""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from layoutlens.api.core import LayoutLens

_PNG_1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGNgAAIAAAUAAen63NgAAAAASUVORK5CYII="
)


def _resp() -> MagicMock:
    response = MagicMock()
    response.choices[0].message.content = '{"answer": "Yes", "confidence": 0.8, "reasoning": "ok"}'
    response.usage.total_tokens = 42
    response.usage.prompt_tokens = 30
    response.usage.completion_tokens = 12
    return response


@pytest.fixture
def png(tmp_path):
    p = tmp_path / "shot.png"
    p.write_bytes(_PNG_1x1)
    return str(p)


@pytest.mark.asyncio
async def test_analyze_default_temperature_is_point_one(tmp_path, png):
    lens = LayoutLens(api_key="sk", model="gpt-4o-mini", output_dir=str(tmp_path / "o"))
    with patch("layoutlens.api.core.acompletion", new=AsyncMock(return_value=_resp())) as mock_llm:
        await lens.analyze(png, "Is it good?")
    assert mock_llm.await_args.kwargs["temperature"] == 0.1


@pytest.mark.asyncio
async def test_analyze_temperature_override(tmp_path, png):
    lens = LayoutLens(api_key="sk", model="gpt-4o-mini", temperature=0.0, output_dir=str(tmp_path / "o"))
    with patch("layoutlens.api.core.acompletion", new=AsyncMock(return_value=_resp())) as mock_llm:
        await lens.analyze(png, "Is it good?")
    assert mock_llm.await_args.kwargs["temperature"] == 0.0


@pytest.mark.asyncio
async def test_analyze_omits_temperature_for_sonnet5(tmp_path, png):
    lens = LayoutLens(api_key="sk", model="claude-sonnet-5", provider="anthropic", output_dir=str(tmp_path / "o"))
    with patch("layoutlens.api.core.acompletion", new=AsyncMock(return_value=_resp())) as mock_llm:
        await lens.analyze(png, "Is it good?")
    assert "temperature" not in mock_llm.await_args.kwargs


@pytest.mark.asyncio
async def test_analyze_api_base_reaches_acompletion(tmp_path, png):
    lens = LayoutLens(
        api_key="sk",
        model="ollama/qwen2.5vl",
        provider="litellm",
        api_base="http://localhost:11434",
        output_dir=str(tmp_path / "o"),
    )
    with patch("layoutlens.api.core.acompletion", new=AsyncMock(return_value=_resp())) as mock_llm:
        await lens.analyze(png, "Is it good?")
    assert mock_llm.await_args.kwargs["api_base"] == "http://localhost:11434"


@pytest.mark.asyncio
async def test_analyze_records_usage_split(tmp_path, png):
    lens = LayoutLens(api_key="sk", model="gpt-4o-mini", output_dir=str(tmp_path / "o"))
    with patch("layoutlens.api.core.acompletion", new=AsyncMock(return_value=_resp())):
        result = await lens.analyze(png, "Is it good?")
    assert result.metadata["prompt_tokens"] == 30
    assert result.metadata["completion_tokens"] == 12
    assert result.metadata["tokens_used"] == 42
