"""Provider factory for creating and managing AI vision providers via OpenRouter."""

from typing import Any

from ..exceptions import ConfigurationError
from .base import VisionProvider, VisionProviderConfig
from .openrouter_provider import OpenRouterProvider

# Global registry of providers - simplified since OpenRouter handles all providers
_PROVIDER_REGISTRY: dict[str, type[VisionProvider]] = {
    "openrouter": OpenRouterProvider,
    "openai": OpenRouterProvider,  # Alias for backward compatibility
    "anthropic": OpenRouterProvider,  # Alias for backward compatibility
    "google": OpenRouterProvider,  # Alias for backward compatibility
    "gemini": OpenRouterProvider,  # Alias for backward compatibility
}


def register_provider(name: str, provider_class: type[VisionProvider]) -> None:
    """Register a provider class with the factory.

    Args:
        name: Provider name (e.g., 'openai', 'anthropic')
        provider_class: Provider class that implements VisionProvider
    """
    if not issubclass(provider_class, VisionProvider):
        raise TypeError(f"Provider class must inherit from VisionProvider")

    _PROVIDER_REGISTRY[name.lower()] = provider_class


def get_available_providers() -> dict[str, type[VisionProvider]]:
    """Get all registered provider classes.

    Returns:
        Dictionary mapping provider names to their classes
    """
    return _PROVIDER_REGISTRY.copy()


def create_provider(
    provider_name: str,
    api_key: str,
    model: str,
    max_tokens: int = 1000,
    temperature: float = 0.1,
    timeout: float = 30.0,
    max_retries: int = 3,
    **custom_params: Any,
) -> VisionProvider:
    """Create and initialize a provider instance.

    Args:
        provider_name: Name of the provider ('openai', 'anthropic', 'gemini')
        api_key: API key for the provider
        model: Model name to use
        max_tokens: Maximum tokens in response
        temperature: Model temperature (0.0-1.0)
        timeout: Request timeout in seconds
        max_retries: Maximum retry attempts
        **custom_params: Provider-specific parameters

    Returns:
        Initialized provider instance

    Raises:
        ConfigurationError: If provider not found or configuration invalid
    """
    provider_name_lower = provider_name.lower()

    if provider_name_lower not in _PROVIDER_REGISTRY:
        available = ", ".join(_PROVIDER_REGISTRY.keys())
        raise ConfigurationError(f"Provider '{provider_name}' not found. Available providers: {available}")

    # Create configuration
    config = VisionProviderConfig(
        api_key=api_key,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
        max_retries=max_retries,
        custom_params=custom_params,
    )

    # Create provider instance
    provider_class = _PROVIDER_REGISTRY[provider_name_lower]
    provider = provider_class(config)

    # Validate configuration
    provider.validate_config()

    # Initialize the provider
    provider.initialize()

    return provider


def create_provider_from_config(config: dict[str, Any]) -> VisionProvider:
    """Create provider from configuration dictionary.

    Args:
        config: Configuration dictionary with provider settings

    Returns:
        Initialized provider instance

    Example config:
        {
            "provider": "openai",
            "api_key": "your-key",
            "model": "gpt-4o",
            "temperature": 0.1,
            "custom_params": {"detail": "high"}
        }
    """
    provider_name = config.get("provider")
    if not provider_name:
        raise ConfigurationError("Provider name required in configuration")

    api_key = config.get("api_key")
    if not api_key:
        raise ConfigurationError("API key required in configuration")

    model = config.get("model")
    if not model:
        raise ConfigurationError("Model name required in configuration")

    return create_provider(
        provider_name=provider_name,
        api_key=api_key,
        model=model,
        max_tokens=config.get("max_tokens", 1000),
        temperature=config.get("temperature", 0.1),
        timeout=config.get("timeout", 30.0),
        max_retries=config.get("max_retries", 3),
        **(config.get("custom_params", {})),
    )


def list_supported_models(provider_name: str) -> list[str]:
    """List supported models for a provider.

    Args:
        provider_name: Name of the provider

    Returns:
        List of supported model names

    Raises:
        ConfigurationError: If provider not found
    """
    provider_name_lower = provider_name.lower()

    if provider_name_lower not in _PROVIDER_REGISTRY:
        available = ", ".join(_PROVIDER_REGISTRY.keys())
        raise ConfigurationError(f"Provider '{provider_name}' not found. Available providers: {available}")

    # Create temporary instance to get supported models
    provider_class = _PROVIDER_REGISTRY[provider_name_lower]

    # Use a dummy config just to get the model list
    dummy_config = VisionProviderConfig(api_key="dummy", model="dummy")

    temp_provider = provider_class(dummy_config)
    return temp_provider.supported_models


def get_provider_info() -> dict[str, dict[str, Any]]:
    """Get information about all available providers.

    Returns:
        Dictionary with provider info including supported models
    """
    info = {}

    for name, provider_class in _PROVIDER_REGISTRY.items():
        try:
            models = list_supported_models(name)
            info[name] = {
                "class": provider_class.__name__,
                "supported_models": models,
                "description": provider_class.__doc__ or f"{name.title()} AI vision provider",
            }
        except Exception as e:
            info[name] = {
                "class": provider_class.__name__,
                "error": str(e),
                "description": provider_class.__doc__ or f"{name.title()} AI vision provider",
            }

    return info
