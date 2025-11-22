"""AI Provider abstraction for LayoutLens.

This module provides access to multiple AI vision providers through OpenRouter's
unified API, supporting OpenAI, Anthropic, Google Gemini, and many others.
"""

from .base import (
    VisionAnalysisRequest,
    VisionAnalysisResponse,
    VisionProvider,
    VisionProviderConfig,
)
from .factory import create_provider, get_available_providers, get_provider_info
from .openrouter_provider import OpenRouterProvider

__all__ = [
    "VisionProvider",
    "VisionProviderConfig",
    "VisionAnalysisRequest",
    "VisionAnalysisResponse",
    "OpenRouterProvider",
    "create_provider",
    "get_available_providers",
    "get_provider_info",
]
