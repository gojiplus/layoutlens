"""OpenRouter provider for accessing multiple AI vision models through a unified API."""

import base64
from pathlib import Path
from typing import Any

import openai

from .base import VisionAnalysisRequest, VisionAnalysisResponse, VisionProvider


class OpenRouterProvider(VisionProvider):
    """Provider that uses OpenRouter to access multiple AI models via unified OpenAI API."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client: openai.OpenAI | None = None

    # Model mapping for OpenRouter
    SUPPORTED_MODELS = {
        # OpenAI models
        "gpt-4o": "openai/gpt-4o",
        "gpt-4o-mini": "openai/gpt-4o-mini",
        "gpt-4-vision": "openai/gpt-4-vision-preview",
        # Anthropic models
        "claude-3-opus": "anthropic/claude-3-opus",
        "claude-3-sonnet": "anthropic/claude-3-sonnet",
        "claude-3-haiku": "anthropic/claude-3-haiku",
        "claude-3.5-sonnet": "anthropic/claude-3.5-sonnet",
        # Google models
        "gemini-pro-vision": "google/gemini-pro-vision",
        "gemini-1.5-pro": "google/gemini-1.5-pro",
        "gemini-1.5-flash": "google/gemini-1.5-flash",
        # Other popular vision models
        "llava-v1.6-34b": "liuhaotian/llava-v1.6-34b",
        "moondream": "vikhyatk/moondream2",
    }

    @property
    def provider_name(self) -> str:
        return "openrouter"

    @property
    def supported_models(self) -> list[str]:
        return list(self.SUPPORTED_MODELS.keys())

    def initialize(self) -> None:
        """Initialize OpenRouter client using OpenAI SDK."""
        self._client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.config.api_key,
            timeout=self.config.timeout,
        )

    def analyze_image(self, request: VisionAnalysisRequest) -> VisionAnalysisResponse:
        """Analyze image using OpenRouter's unified API."""
        if not self._client:
            self.initialize()

        assert self._client is not None, "OpenAI client not initialized"

        # Get OpenRouter model name
        openrouter_model = self._get_openrouter_model(self.config.model)

        # Encode image
        image_b64 = self._encode_image(request.image_path)

        # Build prompt
        prompt = self.format_query_prompt(request.query, request.context)

        try:
            response = self._client.chat.completions.create(
                model=openrouter_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                            },
                        ],
                    }
                ],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                extra_headers={
                    "HTTP-Referer": "https://layoutlens.io",
                    "X-Title": "LayoutLens UI Testing Framework",
                },
            )

            raw_response = response.choices[0].message.content

            # Parse response using base class method
            result = self.parse_response(raw_response, request)

            # Add usage statistics
            if hasattr(response, "usage") and response.usage:
                result.usage_stats = {
                    "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                    "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                    "total_tokens": getattr(response.usage, "total_tokens", 0),
                }

            return result

        except Exception as e:
            # Return error response
            return VisionAnalysisResponse(
                answer=f"Error during analysis: {str(e)}",
                confidence=0.0,
                reasoning=f"Analysis failed: {str(e)}",
                metadata={
                    "error": str(e),
                    "source": request.image_path,
                    "query": request.query,
                },
                provider=self.provider_name,
                model=self.config.model,
            )

    async def analyze_image_async(self, request: VisionAnalysisRequest) -> VisionAnalysisResponse:
        """Async version using OpenAI async client."""
        # Create async client
        async_client = openai.AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.config.api_key,
            timeout=self.config.timeout,
        )

        openrouter_model = self._get_openrouter_model(self.config.model)
        image_b64 = self._encode_image(request.image_path)
        prompt = self.format_query_prompt(request.query, request.context)

        try:
            response = await async_client.chat.completions.create(
                model=openrouter_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                            },
                        ],
                    }
                ],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                extra_headers={
                    "HTTP-Referer": "https://layoutlens.io",
                    "X-Title": "LayoutLens UI Testing Framework",
                },
            )

            raw_response = response.choices[0].message.content
            result = self.parse_response(raw_response, request)

            if hasattr(response, "usage") and response.usage:
                result.usage_stats = {
                    "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                    "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                    "total_tokens": getattr(response.usage, "total_tokens", 0),
                }

            return result

        except Exception as e:
            return VisionAnalysisResponse(
                answer=f"Error during analysis: {str(e)}",
                confidence=0.0,
                reasoning=f"Analysis failed: {str(e)}",
                metadata={
                    "error": str(e),
                    "source": request.image_path,
                    "query": request.query,
                },
                provider=self.provider_name,
                model=self.config.model,
            )
        finally:
            await async_client.close()

    def _encode_image(self, image_path: str) -> str:
        """Encode image to base64."""
        image_file = Path(image_path)
        if not image_file.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        with open(image_file, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _get_openrouter_model(self, model_name: str) -> str:
        """Convert local model name to OpenRouter model identifier."""
        if model_name in self.SUPPORTED_MODELS:
            return self.SUPPORTED_MODELS[model_name]

        # If it's already an OpenRouter format (provider/model), use as-is
        if "/" in model_name:
            return model_name

        # Default to gpt-4o-mini if model not found
        return self.SUPPORTED_MODELS["gpt-4o-mini"]

    def get_pricing_info(self) -> dict[str, Any]:
        """Get pricing information for supported models."""
        # This would typically come from OpenRouter's API
        return {
            "currency": "USD",
            "note": "Visit https://openrouter.ai/models for current pricing",
            "popular_models": {
                "gpt-4o-mini": {
                    "input": "$0.15/1M tokens",
                    "output": "$0.60/1M tokens",
                },
                "claude-3-haiku": {
                    "input": "$0.25/1M tokens",
                    "output": "$1.25/1M tokens",
                },
                "gemini-1.5-flash": {
                    "input": "$0.075/1M tokens",
                    "output": "$0.30/1M tokens",
                },
            },
        }
