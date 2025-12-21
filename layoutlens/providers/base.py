"""Base classes for AI vision providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ..logger import get_logger


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
        # Logger will be initialized in subclasses after provider_name is available
        self.logger = None

    def _init_logger(self) -> None:
        """Initialize logger for the provider."""
        if not self.logger:
            self.logger = get_logger(f"providers.{self.provider_name}")

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
        if self.logger:
            self.logger.debug(f"Validating configuration for {self.provider_name}")

        if not self.config.api_key:
            error_msg = f"API key required for {self.provider_name} provider"
            if self.logger:
                self.logger.error(error_msg)
            raise ValueError(error_msg)

        if self.config.model not in self.supported_models:
            error_msg = f"Model '{self.config.model}' not supported by {self.provider_name}. Supported models: {', '.join(self.supported_models)}"
            if self.logger:
                self.logger.error(error_msg)
            raise ValueError(error_msg)

        if self.logger:
            self.logger.info(f"Configuration validated for {self.provider_name} with model {self.config.model}")
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

        # Try to extract JSON from response first
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

        # Try to parse structured text response (ANSWER:/CONFIDENCE:/REASONING: format)
        answer_match = re.search(r"ANSWER:\s*(.+?)(?=\n(?:CONFIDENCE|REASONING)|$)", response_text, re.DOTALL)
        confidence_match = re.search(r"CONFIDENCE:\s*([0-9]*\.?[0-9]+)", response_text)
        reasoning_match = re.search(r"REASONING:\s*(.+?)$", response_text, re.DOTALL)

        if answer_match:
            answer = answer_match.group(1).strip()
            confidence = float(confidence_match.group(1)) if confidence_match else 0.5
            reasoning = reasoning_match.group(1).strip() if reasoning_match else "Analysis completed"

            return VisionAnalysisResponse(
                answer=answer,
                confidence=confidence,
                reasoning=reasoning,
                metadata={
                    "source": request.image_path,
                    "query": request.query,
                    "viewport": request.viewport,
                    "raw_response": response_text,
                    "parsing_type": "structured_text",
                },
                provider=self.provider_name,
                model=self.config.model,
            )

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
                "parsing_note": "Used fallback parsing due to unrecognized response format",
            },
            provider=self.provider_name,
            model=self.config.model,
        )

    def __str__(self) -> str:
        return f"{self.provider_name} Provider (model: {self.config.model})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.config.model!r})"

    def parse_structured_response(self, content: str) -> tuple[str, float, str]:
        """Parse structured response and return answer, confidence, and reasoning.

        Args:
            content: Raw response content to parse

        Returns:
            Tuple of (answer, confidence, reasoning)
        """
        import re

        # Try to extract confidence from common patterns
        confidence_patterns = [
            r"confidence[:\s]+([0-9]*\.?[0-9]+)",
            r"([0-9]*\.?[0-9]+)%?\s*confidence",
            r"\*\*confidence[:\s]*\*\*\s*([0-9]*\.?[0-9]+)",
        ]

        confidence = 0.8  # Default confidence
        for pattern in confidence_patterns:
            match = re.search(pattern, content.lower())
            if match:
                try:
                    confidence_val = float(match.group(1))
                    # Convert percentage to decimal if needed
                    if confidence_val > 1.0:
                        confidence_val = confidence_val / 100.0
                    confidence = max(0.0, min(1.0, confidence_val))
                    break
                except (ValueError, IndexError):
                    continue

        # Try to extract answer from common patterns
        answer_patterns = [
            r"answer[:\s]+([^\n\*]+)",
            r"\*\*answer[:\s]*\*\*\s*([^\n\*]+)",
            r"^([^.\n]*(?:yes|no)[^.\n]*)",
        ]

        answer = ""
        for pattern in answer_patterns:
            match = re.search(pattern, content.lower())
            if match:
                answer = match.group(1).strip()
                break

        # If no specific answer found, use first sentence or paragraph
        if not answer:
            # Split by sentences and take first meaningful one
            sentences = re.split(r"[.!?]\s+", content.strip())
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) > 10:  # Avoid very short fragments
                    answer = sentence
                    break

            # Fallback to first 200 characters
            if not answer:
                answer = content.strip()[:200]

        # Try to extract reasoning
        reasoning_patterns = [
            r"reasoning[:\s]+(.+?)(?=\n\n|\*\*|$)",
            r"\*\*reasoning[:\s]*\*\*\s*(.+?)(?=\n\n|\*\*|$)",
        ]

        reasoning = ""
        for pattern in reasoning_patterns:
            match = re.search(pattern, content.lower(), re.DOTALL)
            if match:
                reasoning = match.group(1).strip()
                break

        # If no specific reasoning, use content after answer
        if not reasoning:
            reasoning = content.strip()

        return answer, confidence, reasoning
