"""Direct OpenAI provider for accessing OpenAI's vision models."""

import base64
from pathlib import Path
from typing import Any

import openai

from .base import VisionAnalysisRequest, VisionAnalysisResponse, VisionProvider


class OpenAIProvider(VisionProvider):
    """Provider that directly uses OpenAI's API for vision analysis."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client: openai.OpenAI | None = None
        self._init_logger()

    # Supported OpenAI models
    SUPPORTED_MODELS = {
        "gpt-4o": "gpt-4o",
        "gpt-4o-mini": "gpt-4o-mini",
        "gpt-4-vision-preview": "gpt-4-vision-preview",
    }

    @property
    def provider_name(self) -> str:
        return "openai_direct"

    @property
    def supported_models(self) -> list[str]:
        return list(self.SUPPORTED_MODELS.keys())

    def initialize(self) -> None:
        """Initialize OpenAI client."""
        self.logger.debug("Initializing OpenAI client")
        self._client = openai.OpenAI(
            api_key=self.config.api_key,
            timeout=self.config.timeout,
        )
        self.logger.info(f"OpenAI client initialized with model: {self.config.model}")

    def analyze_image(self, request: VisionAnalysisRequest) -> VisionAnalysisResponse:
        """Analyze image using OpenAI's API."""
        self.logger.debug(f"Starting image analysis: {request.image_path}")
        self.logger.debug(f"Query: {request.query[:100]}..." if len(request.query) > 100 else f"Query: {request.query}")

        if not self._client:
            self.initialize()

        assert self._client is not None, "OpenAI client not initialized"

        # Encode image
        try:
            image_b64 = self._encode_image(request.image_path)
            self.logger.debug(f"Image encoded successfully: {len(image_b64)} characters")
        except Exception as e:
            self.logger.error(f"Image encoding failed: {e}")
            raise

        # Build prompt
        prompt = self.format_query_prompt(request.query, request.context)

        try:
            self.logger.debug("Making API call to OpenAI")
            response = self._client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{image_b64}", "detail": "high"},
                            },
                        ],
                    }
                ],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )

            self.logger.debug(f"API call successful, response length: {len(response.choices[0].message.content or '')}")

            # Extract answer
            content = response.choices[0].message.content or ""

            # Parse structured response
            answer, confidence, reasoning = self.parse_structured_response(content)

            self.logger.debug(f"Parsed response - confidence: {confidence:.2f}")

            return VisionAnalysisResponse(
                answer=answer,
                confidence=confidence,
                reasoning=reasoning,
                metadata={
                    "raw_response": content,
                    "tokens_used": response.usage.total_tokens if response.usage else 0,
                },
                provider=self.provider_name,
                model=self.config.model,
            )

        except Exception as e:
            self.logger.error(f"OpenAI API call failed: {e}")
            error_msg = f"OpenAI API call failed: {e}"
            return VisionAnalysisResponse(
                answer=f"Error during analysis: {e}",
                confidence=0.0,
                reasoning=f"Analysis failed: {e}",
                metadata={
                    "raw_response": error_msg,
                    "tokens_used": 0,
                },
                provider=self.provider_name,
                model=self.config.model,
            )

    async def analyze_image_async(self, request: VisionAnalysisRequest) -> VisionAnalysisResponse:
        """Async version of analyze_image - for now just calls sync version."""
        return self.analyze_image(request)

    def _encode_image(self, image_path: str | Path) -> str:
        """Encode image to base64."""
        image_path = Path(image_path)

        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
