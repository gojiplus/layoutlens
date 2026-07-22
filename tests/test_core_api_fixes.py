"""Regression tests for core LayoutLens API fixes (final v1.7.0 review wave).

Covers:
- provider="litellm" leaving credential resolution to LiteLLM (no hard OpenAI
  key requirement, and no ``api_key`` forwarded to ``acompletion``).
- ``compare()`` routing local HTML sources through the capture path so the
  comparative vision call receives a real screenshot, not raw HTML bytes.
"""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from layoutlens.api.core import AnalysisResult, LayoutLens

# A minimal valid 1x1 PNG so image sources exist on disk for the image path.
_PNG_1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGNgAAIAAAUAAen63NgAAAAASUVORK5CYII="
)


def _vision_response() -> MagicMock:
    response = MagicMock()
    response.choices[0].message.content = '{"answer": "Yes", "confidence": 0.8, "reasoning": "ok"}'
    response.usage.total_tokens = 42
    return response


@pytest.mark.asyncio
async def test_litellm_provider_omits_api_key_and_does_not_require_openai_key(tmp_path, monkeypatch):
    """provider='litellm' with only ANTHROPIC_API_KEY set resolves via LiteLLM.

    No AuthenticationError is raised, and ``acompletion`` is called WITHOUT an
    ``api_key`` kwarg so LiteLLM applies its own per-model credential resolution.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    png = tmp_path / "shot.png"
    png.write_bytes(_PNG_1x1)

    lens = LayoutLens(provider="litellm", model="anthropic/claude-3-5-sonnet", output_dir=str(tmp_path / "out"))
    assert lens.api_key is None  # OpenAI key was NOT grabbed for litellm.

    with patch("layoutlens.api.core.acompletion", new=AsyncMock(return_value=_vision_response())) as mock_llm:
        result = await lens.analyze(str(png), "Is it accessible?")

    assert result.confidence == 0.8
    mock_llm.assert_awaited_once()
    assert "api_key" not in mock_llm.await_args.kwargs


@pytest.mark.asyncio
async def test_compare_routes_local_html_through_capture(tmp_path):
    """compare() must screenshot local HTML, not base64-encode the raw HTML bytes."""
    a = tmp_path / "a.html"
    b = tmp_path / "b.html"
    a.write_text("<html><body>A</body></html>")
    b.write_text("<html><body>B</body></html>")

    shots = {str(a): str(tmp_path / "a.png"), str(b): str(tmp_path / "b.png")}

    lens = LayoutLens(api_key="sk-test", output_dir=str(tmp_path / "out"))

    async def fake_serve(source, viewport, *args, **kwargs):
        return shots[str(source)]

    lens._serve_html_and_capture = AsyncMock(side_effect=fake_serve)
    # Individual per-source analyses are irrelevant to this assertion.
    lens.analyze = AsyncMock(
        return_value=AnalysisResult(source="x", query="q", answer="ok", confidence=0.7, reasoning="r")
    )
    lens._call_vision_api = AsyncMock(
        return_value={"answer": "B is better", "confidence": 0.8, "reasoning": "r", "metadata": {}}
    )

    await lens.compare([str(a), str(b)], "Which is better?")

    # Both HTML sources were rendered to screenshots.
    assert lens._serve_html_and_capture.await_count == 2
    # The comparative vision call received a real screenshot path, not the HTML file.
    comparative_image = lens._call_vision_api.await_args.kwargs["image_path"]
    assert comparative_image == shots[str(a)]
    assert comparative_image.endswith(".png")
    assert comparative_image != str(a)
