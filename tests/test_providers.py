"""Tests for the provider architecture system."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from layoutlens.exceptions import ConfigurationError
from layoutlens.providers import (
    VisionAnalysisRequest,
    VisionAnalysisResponse,
    VisionProvider,
    VisionProviderConfig,
    create_provider,
    get_available_providers,
    get_provider_info,
)
from layoutlens.providers.litellm_provider import LiteLLMProvider


class TestVisionProviderConfig:
    """Test VisionProviderConfig dataclass."""

    def test_basic_config(self):
        """Test basic configuration creation."""
        config = VisionProviderConfig(api_key="test-key", model="gpt-4o-mini")

        assert config.api_key == "test-key"
        assert config.model == "gpt-4o-mini"
        assert config.max_tokens == 1000
        assert config.temperature == 0.1
        assert config.timeout == 30.0
        assert config.max_retries == 3
        assert config.custom_params == {}

    def test_config_with_custom_params(self):
        """Test configuration with custom parameters."""
        config = VisionProviderConfig(
            api_key="test-key",
            model="claude-3-haiku",
            temperature=0.2,
            custom_params={"detail": "high"},
        )

        assert config.temperature == 0.2
        assert config.custom_params == {"detail": "high"}


class TestVisionAnalysisObjects:
    """Test VisionAnalysisRequest and VisionAnalysisResponse."""

    def test_analysis_request(self):
        """Test VisionAnalysisRequest creation."""
        request = VisionAnalysisRequest(
            image_path="/path/to/image.png",
            query="Is this accessible?",
            context={"user_type": "elderly"},
            source_url="https://example.com",
            viewport="mobile_portrait",
        )

        assert request.image_path == "/path/to/image.png"
        assert request.query == "Is this accessible?"
        assert request.context == {"user_type": "elderly"}
        assert request.source_url == "https://example.com"
        assert request.viewport == "mobile_portrait"

    def test_analysis_response(self):
        """Test VisionAnalysisResponse creation."""
        response = VisionAnalysisResponse(
            answer="Yes, this page is accessible",
            confidence=0.85,
            reasoning="The page has good contrast and clear navigation",
            metadata={"source": "test.png"},
            provider="litellm",
            model="gpt-4o-mini",
            usage_stats={"tokens": 150},
        )

        assert response.answer == "Yes, this page is accessible"
        assert response.confidence == 0.85
        assert response.reasoning == "The page has good contrast and clear navigation"
        assert response.metadata == {"source": "test.png"}
        assert response.provider == "litellm"
        assert response.model == "gpt-4o-mini"
        assert response.usage_stats == {"tokens": 150}


class TestLiteLLMProvider:
    """Test LiteLLMProvider implementation."""

    def test_provider_properties(self):
        """Test provider basic properties."""
        config = VisionProviderConfig(api_key="test-key", model="gpt-4o-mini")
        provider = LiteLLMProvider(config)

        assert provider.provider_name == "litellm"
        assert "gpt-4o-mini" in provider.supported_models
        assert "claude-3-haiku" in provider.supported_models
        assert "gemini-1.5-flash" in provider.supported_models

    def test_config_validation_success(self):
        """Test successful configuration validation."""
        config = VisionProviderConfig(api_key="test-key", model="gpt-4o-mini")
        provider = LiteLLMProvider(config)

        assert provider.validate_config() is True

    def test_config_validation_missing_key(self):
        """Test validation failure with missing API key."""
        config = VisionProviderConfig(api_key="", model="gpt-4o-mini")
        provider = LiteLLMProvider(config)

        with pytest.raises(ValueError, match="API key required"):
            provider.validate_config()

    def test_config_validation_unsupported_model(self):
        """Test validation failure with unsupported model."""
        config = VisionProviderConfig(api_key="test-key", model="unsupported-model")
        provider = LiteLLMProvider(config)

        with pytest.raises(ValueError, match="not supported"):
            provider.validate_config()

    def test_litellm_model_mapping(self):
        """Test LiteLLM model name mapping."""
        config = VisionProviderConfig(api_key="test-key", model="gpt-4o-mini")
        provider = LiteLLMProvider(config)

        # Test known mappings
        assert provider._get_litellm_model("gpt-4o-mini") == "openai/gpt-4o-mini"
        assert provider._get_litellm_model("claude-3-haiku") == "anthropic/claude-3-haiku"
        assert provider._get_litellm_model("gemini-1.5-flash") == "google/gemini-1.5-flash"

        # Test already formatted model names
        assert provider._get_litellm_model("openai/gpt-4o") == "openai/gpt-4o"

        # Test fallback for unknown models
        assert provider._get_litellm_model("unknown-model") == "openai/gpt-4o-mini"

    @patch("openai.OpenAI")
    def test_initialize(self, mock_openai):
        """Test provider initialization."""
        config = VisionProviderConfig(api_key="test-key", model="gpt-4o-mini")
        provider = LiteLLMProvider(config)

        provider.initialize()

        mock_openai.assert_called_once_with(base_url="https://litellm.ai/api/v1", api_key="test-key", timeout=30.0)

    @patch("openai.OpenAI")
    @patch("builtins.open")
    @patch("base64.b64encode")
    @patch("pathlib.Path.exists")
    def test_analyze_image_success(self, mock_exists, mock_b64, mock_open, mock_openai):
        """Test successful image analysis."""
        # Setup mocks
        mock_exists.return_value = True
        mock_b64.return_value = b"fake-base64-data"
        mock_file = Mock()
        mock_file.read.return_value = b"fake-image-data"
        mock_open.return_value.__enter__.return_value = mock_file

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"answer": "Yes", "confidence": 0.9, "reasoning": "Good design"}'
        mock_response.usage.prompt_tokens = 50
        mock_response.usage.completion_tokens = 100
        mock_response.usage.total_tokens = 150

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        # Test analysis
        config = VisionProviderConfig(api_key="test-key", model="gpt-4o-mini")
        provider = LiteLLMProvider(config)
        provider.initialize()

        request = VisionAnalysisRequest(
            image_path="/fake/path/image.png",
            query="Is this well designed?",
            context={"focus": "accessibility"},
        )

        response = provider.analyze_image(request)

        assert response.answer == "Yes"
        assert response.confidence == 0.9
        assert response.reasoning == "Good design"
        assert response.provider == "litellm"
        assert response.model == "gpt-4o-mini"
        assert response.usage_stats["total_tokens"] == 150

    @patch("openai.OpenAI")
    @patch("pathlib.Path.exists")
    def test_analyze_image_file_not_found(self, mock_exists, mock_openai):
        """Test analysis with non-existent image file."""
        mock_exists.return_value = False

        config = VisionProviderConfig(api_key="test-key", model="gpt-4o-mini")
        provider = LiteLLMProvider(config)
        provider.initialize()

        request = VisionAnalysisRequest(image_path="/fake/path/nonexistent.png", query="Is this well designed?")

        with pytest.raises(FileNotFoundError):
            provider.analyze_image(request)

    @patch("openai.AsyncOpenAI")
    @patch("builtins.open")
    @patch("base64.b64encode")
    @patch("pathlib.Path.exists")
    @pytest.mark.asyncio
    async def test_analyze_image_async_success(self, mock_exists, mock_b64, mock_open, mock_async_openai):
        """Test successful async image analysis."""
        # Setup mocks
        mock_exists.return_value = True
        mock_b64.return_value = b"fake-base64-data"
        mock_file = Mock()
        mock_file.read.return_value = b"fake-image-data"
        mock_open.return_value.__enter__.return_value = mock_file

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"answer": "Yes", "confidence": 0.9, "reasoning": "Good design"}'
        mock_response.usage.prompt_tokens = 50
        mock_response.usage.completion_tokens = 100
        mock_response.usage.total_tokens = 150

        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_client.close = AsyncMock()
        mock_async_openai.return_value = mock_client

        # Test async analysis
        config = VisionProviderConfig(api_key="test-key", model="gpt-4o-mini")
        provider = LiteLLMProvider(config)

        request = VisionAnalysisRequest(image_path="/fake/path/image.png", query="Is this well designed?")

        response = await provider.analyze_image_async(request)

        assert response.answer == "Yes"
        assert response.confidence == 0.9
        assert response.provider == "litellm"
        mock_client.close.assert_called_once()


class TestProviderFactory:
    """Test provider factory functions."""

    def test_get_available_providers(self):
        """Test getting available providers."""
        providers = get_available_providers()

        assert "litellm" in providers
        assert "openai" in providers
        assert "anthropic" in providers
        assert issubclass(providers["litellm"], VisionProvider)

    def test_create_provider_success(self):
        """Test successful provider creation."""
        provider = create_provider(provider_name="litellm", api_key="test-key", model="gpt-4o-mini")

        assert isinstance(provider, LiteLLMProvider)
        assert provider.config.api_key == "test-key"
        assert provider.config.model == "gpt-4o-mini"

    def test_create_provider_unknown(self):
        """Test creation with unknown provider."""
        with pytest.raises(ConfigurationError, match="not found"):
            create_provider(provider_name="unknown-provider", api_key="test-key", model="test-model")

    def test_create_provider_invalid_model(self):
        """Test creation with invalid model."""
        with pytest.raises(ValueError, match="not supported"):
            create_provider(provider_name="litellm", api_key="test-key", model="invalid-model")

    def test_get_provider_info(self):
        """Test getting provider information."""
        info = get_provider_info()

        assert "litellm" in info
        assert "supported_models" in info["litellm"]
        assert isinstance(info["litellm"]["supported_models"], list)
        assert len(info["litellm"]["supported_models"]) > 0


class TestProviderIntegration:
    """Integration tests for provider system."""

    @pytest.mark.integration
    @patch("openai.OpenAI")
    def test_full_provider_workflow(self, mock_openai):
        """Test complete provider workflow."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "The layout is well-designed with good accessibility features."

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        # Create provider through factory
        provider = create_provider(
            provider_name="litellm",
            api_key="test-key",
            model="gpt-4o-mini",
            temperature=0.2,
            max_tokens=1500,
        )

        # Verify configuration
        assert provider.config.temperature == 0.2
        assert provider.config.max_tokens == 1500

        # Test that client is initialized
        assert provider._client is not None

        # Verify OpenAI client was called with correct parameters
        mock_openai.assert_called_once_with(base_url="https://litellm.ai/api/v1", api_key="test-key", timeout=30.0)
