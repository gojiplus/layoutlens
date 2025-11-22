"""Base classes for AI vision providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class VisionProviderConfig:
    """Configuration for AI vision providers."""

    api_key: str
    model: str
    max_tokens: int = 1000
    temperature: float = 0.1
    timeout: float = 30.0
    max_retries: int = 3
    custom_params: dict[str, Any] | None = None

    def __post_init__(self):
        if self.custom_params is None:
            self.custom_params = {}


@dataclass
class VisionAnalysisRequest:
    """Request object for vision analysis."""

    image_path: str
    query: str
    context: dict[str, Any] | None = None
    source_url: str | None = None
    viewport: str = "desktop"


@dataclass
class VisionAnalysisResponse:
    """Response object from vision analysis."""

    answer: str
    confidence: float
    reasoning: str
    metadata: dict[str, Any]
    provider: str
    model: str
    usage_stats: dict[str, Any] | None = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.usage_stats is None:
            self.usage_stats = {}


class VisionProvider(ABC):
    """Abstract base class for AI vision providers."""

    def __init__(self, config: VisionProviderConfig):
        self.config = config
        self._client = None

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of this provider."""
        pass

    @property
    @abstractmethod
    def supported_models(self) -> list[str]:
        """Return list of supported model names."""
        pass

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the provider client."""
        pass

    @abstractmethod
    def analyze_image(self, request: VisionAnalysisRequest) -> VisionAnalysisResponse:
        """Analyze an image with the given query."""
        pass

    @abstractmethod
    async def analyze_image_async(self, request: VisionAnalysisRequest) -> VisionAnalysisResponse:
        """Async version of analyze_image."""
        pass

    def validate_config(self) -> bool:
        """Validate the provider configuration."""
        if not self.config.api_key:
            raise ValueError(f"API key required for {self.provider_name} provider")

        if self.config.model not in self.supported_models:
            raise ValueError(
                f"Model '{self.config.model}' not supported by {self.provider_name}. "
                f"Supported models: {', '.join(self.supported_models)}"
            )

        return True

    def get_client(self):
        """Get the initialized client."""
        if self._client is None:
            self.initialize()
        return self._client

    def format_query_prompt(self, query: str, context: dict[str, Any] | None = None) -> str:
        """Format the query into a proper prompt for the provider."""
        prompt = f"""
Analyze this UI screenshot and answer the following question:

Question: {query}

Please provide:
1. A direct answer to the question
2. Your confidence level (0.0 to 1.0)
3. Detailed reasoning for your assessment

Focus on:
- Visual layout and design elements
- User experience and usability
- Accessibility considerations
- Overall quality and professionalism
"""

        if context:
            context_str = ", ".join(f"{k}: {v}" for k, v in context.items())
            prompt += f"\nAdditional context: {context_str}"

        prompt += "\n\nRespond in this JSON format:\n"
        prompt += '{"answer": "your answer", "confidence": 0.0-1.0, "reasoning": "detailed explanation"}'

        return prompt

    def parse_response(self, response_text: str, request: VisionAnalysisRequest) -> VisionAnalysisResponse:
        """Parse the provider's response into a standard format."""
        import json
        import re

        # Try to extract JSON from response
        json_match = re.search(r'\{[^{}]*"answer"[^{}]*\}', response_text)

        if json_match:
            try:
                parsed = json.loads(json_match.group())
                return VisionAnalysisResponse(
                    answer=parsed.get("answer", response_text),
                    confidence=float(parsed.get("confidence", 0.5)),
                    reasoning=parsed.get("reasoning", "Analysis completed"),
                    metadata={
                        "source": request.image_path,
                        "query": request.query,
                        "viewport": request.viewport,
                        "raw_response": response_text,
                    },
                    provider=self.provider_name,
                    model=self.config.model,
                )
            except (json.JSONDecodeError, ValueError):
                pass

        # Fallback to simple text parsing
        return VisionAnalysisResponse(
            answer=response_text,
            confidence=0.5,  # Default confidence when parsing fails
            reasoning="Standard analysis completed",
            metadata={
                "source": request.image_path,
                "query": request.query,
                "viewport": request.viewport,
                "raw_response": response_text,
                "parsing_note": "Used fallback parsing due to non-JSON response",
            },
            provider=self.provider_name,
            model=self.config.model,
        )

    def __str__(self) -> str:
        return f"{self.provider_name} Provider (model: {self.config.model})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.config.model!r})"
