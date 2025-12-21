"""LiteLLM provider for unified access to all vision LLMs."""

import asyncio
import base64
from pathlib import Path
from typing import Any

try:
    import litellm
    from litellm import acompletion, completion
except ImportError as e:
    raise ImportError("litellm is required for LiteLLM provider. Install with: pip install litellm") from e

from .base import VisionAnalysisRequest, VisionAnalysisResponse, VisionProvider


class LiteLLMProvider(VisionProvider):
    """Provider using LiteLLM for unified access to all vision models."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._init_logger()

    @property
    def provider_name(self) -> str:
        return "litellm"

    @property
    def supported_models(self) -> list[str]:
        return [
            # OpenAI
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-vision-preview",
            # Anthropic
            "claude-3-opus",
            "claude-3-sonnet",
            "claude-3-haiku",
            "claude-3-5-sonnet",
            # Google
            "gemini-pro-vision",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            # And many more supported by LiteLLM
        ]

    def initialize(self) -> None:
        """Initialize LiteLLM - no setup needed."""
        self.logger.info(f"LiteLLM provider initialized with model: {self.config.model}")

    def analyze_image(self, request: VisionAnalysisRequest) -> VisionAnalysisResponse:
        """Analyze image using LiteLLM."""
        self.logger.debug(f"Starting image analysis: {request.image_path}")
        self.logger.debug(f"Query: {request.query[:100]}..." if len(request.query) > 100 else f"Query: {request.query}")

        # Encode image
        try:
            image_b64 = self._encode_image(request.image_path)
            self.logger.debug(f"Image encoded successfully: {len(image_b64)} characters")
        except Exception as e:
            self.logger.error(f"Image encoding failed: {e}")
            return self._create_error_response(f"Image encoding failed: {e}")

        # Build prompt
        prompt = self.format_query_prompt(request.query, request.context)

        try:
            self.logger.debug(f"Making API call with LiteLLM to model: {self.config.model}")

            response = completion(
                model=self.config.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                        ],
                    }
                ],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                api_key=self.config.api_key,
                timeout=self.config.timeout,
            )

            self.logger.debug(f"API call successful")

            # Extract content
            content = response.choices[0].message.content or ""
            tokens_used = (
                getattr(response.usage, "total_tokens", 0) if hasattr(response, "usage") and response.usage else 0
            )

            # Parse structured response
            answer, confidence, reasoning = self.parse_structured_response(content)

            self.logger.debug(f"Parsed response - confidence: {confidence:.2f}")

            return VisionAnalysisResponse(
                answer=answer,
                confidence=confidence,
                reasoning=reasoning,
                metadata={
                    "raw_response": content,
                    "tokens_used": tokens_used,
                    "model_used": self.config.model,
                },
                provider=self.provider_name,
                model=self.config.model,
            )

        except Exception as e:
            self.logger.error(f"LiteLLM API call failed: {e}")
            return self._create_error_response(f"API call failed: {e}")

    async def analyze_image_async(self, request: VisionAnalysisRequest) -> VisionAnalysisResponse:
        """Async image analysis using LiteLLM's built-in async support."""
        self.logger.debug(f"Starting async image analysis: {request.image_path}")
        self.logger.debug(f"Query: {request.query[:100]}..." if len(request.query) > 100 else f"Query: {request.query}")

        # Encode image
        try:
            # Run encoding in executor to avoid blocking
            loop = asyncio.get_event_loop()
            image_b64 = await loop.run_in_executor(None, self._encode_image, request.image_path)
            self.logger.debug(f"Image encoded successfully: {len(image_b64)} characters")
        except Exception as e:
            self.logger.error(f"Image encoding failed: {e}")
            return self._create_error_response(f"Image encoding failed: {e}")

        # Build prompt
        prompt = self.format_query_prompt(request.query, request.context)

        try:
            self.logger.debug(f"Making async API call with LiteLLM to model: {self.config.model}")

            response = await acompletion(
                model=self.config.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                        ],
                    }
                ],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                api_key=self.config.api_key,
                timeout=self.config.timeout,
            )

            self.logger.debug(f"Async API call successful")

            # Extract content
            content = response.choices[0].message.content or ""
            tokens_used = (
                getattr(response.usage, "total_tokens", 0) if hasattr(response, "usage") and response.usage else 0
            )

            # Parse structured response
            answer, confidence, reasoning = self.parse_structured_response(content)

            self.logger.debug(f"Parsed async response - confidence: {confidence:.2f}")

            return VisionAnalysisResponse(
                answer=answer,
                confidence=confidence,
                reasoning=reasoning,
                metadata={
                    "raw_response": content,
                    "tokens_used": tokens_used,
                    "model_used": self.config.model,
                },
                provider=self.provider_name,
                model=self.config.model,
            )

        except Exception as e:
            self.logger.error(f"LiteLLM async API call failed: {e}")
            return self._create_error_response(f"Async API call failed: {e}")

    def _encode_image(self, image_path: str | Path) -> str:
        """Encode image to base64."""
        image_path = Path(image_path)

        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def _create_error_response(self, error_message: str) -> VisionAnalysisResponse:
        """Create error response."""
        return VisionAnalysisResponse(
            answer=f"Error during analysis: {error_message}",
            confidence=0.0,
            reasoning=f"Analysis failed: {error_message}",
            metadata={
                "raw_response": error_message,
                "tokens_used": 0,
                "error": True,
            },
            provider=self.provider_name,
            model=self.config.model,
        )
