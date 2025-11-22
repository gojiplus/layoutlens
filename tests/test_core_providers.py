"""Tests for core API with provider architecture integration."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from layoutlens.api.core import AnalysisResult, LayoutLens
from layoutlens.exceptions import AuthenticationError, ConfigurationError
from layoutlens.providers import VisionAnalysisResponse


class TestLayoutLensProviderIntegration:
    """Test LayoutLens integration with provider architecture."""

    def test_initialization_default_provider(self):
        """Test LayoutLens initialization with default provider."""
        with patch("layoutlens.api.core.create_provider") as mock_create:
            mock_provider = Mock()
            mock_create.return_value = mock_provider

            lens = LayoutLens(api_key="test-key")

            mock_create.assert_called_once_with(provider_name="openrouter", api_key="test-key", model="gpt-4o-mini")
            assert lens.provider == "openrouter"
            assert lens.model == "gpt-4o-mini"
            assert lens.vision_provider == mock_provider

    def test_initialization_custom_provider(self):
        """Test LayoutLens initialization with custom provider."""
        with patch("layoutlens.api.core.create_provider") as mock_create:
            mock_provider = Mock()
            mock_create.return_value = mock_provider

            lens = LayoutLens(api_key="test-key", provider="anthropic", model="claude-3-haiku")

            mock_create.assert_called_once_with(provider_name="anthropic", api_key="test-key", model="claude-3-haiku")
            assert lens.provider == "anthropic"
            assert lens.model == "claude-3-haiku"

    def test_api_key_resolution_openrouter(self):
        """Test API key resolution for OpenRouter."""
        with (
            patch.dict("os.environ", {"OPENROUTER_API_KEY": "openrouter-key"}),
            patch("layoutlens.api.core.create_provider") as mock_create,
        ):
            mock_create.return_value = Mock()

            lens = LayoutLens(provider="openrouter")

            mock_create.assert_called_once_with(
                provider_name="openrouter",
                api_key="openrouter-key",
                model="gpt-4o-mini",
            )

    def test_api_key_resolution_fallback(self):
        """Test API key resolution fallback to OPENAI_API_KEY."""
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "openai-key"}, clear=True),
            patch("layoutlens.api.core.create_provider") as mock_create,
        ):
            mock_create.return_value = Mock()

            lens = LayoutLens(provider="openrouter")

            mock_create.assert_called_once_with(
                provider_name="openrouter",
                api_key="openai-key",
                model="gpt-4o-mini",
            )

    def test_api_key_missing(self):
        """Test error when no API key is available."""
        with (
            patch.dict("os.environ", {}, clear=True),
            pytest.raises(AuthenticationError, match="API key required"),
        ):
            LayoutLens(provider="openrouter")

    @patch("layoutlens.api.core.URLCapture")
    @patch("layoutlens.api.core.LayoutComparator")
    @patch("layoutlens.api.core.create_cache")
    def test_analyze_with_provider(self, mock_cache, mock_comparator, mock_capture):
        """Test analyze method using provider architecture."""
        # Setup mocks
        mock_cache_instance = Mock()
        mock_cache_instance.get.return_value = None  # No cached result
        mock_cache.return_value = mock_cache_instance

        mock_provider = Mock()
        mock_vision_response = VisionAnalysisResponse(
            answer="The page is well designed",
            confidence=0.85,
            reasoning="Good use of whitespace and clear navigation",
            metadata={"analysis_time": 2.5},
            provider="openrouter",
            model="gpt-4o-mini",
            usage_stats={"tokens": 150},
        )
        mock_provider.analyze_image.return_value = mock_vision_response

        # Setup capture mock before LayoutLens creation
        mock_capture_instance = Mock()
        mock_capture_instance.capture_url.return_value = "/path/to/screenshot.png"
        mock_capture.return_value = mock_capture_instance

        with patch("layoutlens.api.core.create_provider", return_value=mock_provider):
            lens = LayoutLens(api_key="test-key", provider="openrouter")

            # Mock URL detection and screenshot capture
            with patch.object(lens, "_is_url", return_value=True):
                result = lens.analyze(
                    source="https://example.com",
                    query="Is this well designed?",
                    viewport="desktop",
                )

        # Verify provider was called correctly
        mock_provider.analyze_image.assert_called_once()
        call_args = mock_provider.analyze_image.call_args[0][0]
        assert call_args.image_path == "/path/to/screenshot.png"
        assert call_args.query == "Is this well designed?"
        assert call_args.source_url == "https://example.com"
        assert call_args.viewport == "desktop"

        # Verify result
        assert isinstance(result, AnalysisResult)
        assert result.answer == "The page is well designed"
        assert result.confidence == 0.85
        assert result.metadata["provider"] == "openrouter"
        assert result.metadata["model"] == "gpt-4o-mini"
        assert result.metadata["cache_hit"] is False

    @patch("layoutlens.api.core.URLCapture")
    @patch("layoutlens.api.core.LayoutComparator")
    @patch("layoutlens.api.core.create_cache")
    @pytest.mark.asyncio
    async def test_analyze_async_with_provider(self, mock_cache, mock_comparator, mock_capture):
        """Test async analyze method using provider architecture."""
        # Setup mocks
        mock_cache_instance = Mock()
        mock_cache_instance.get.return_value = None
        mock_cache.return_value = mock_cache_instance

        mock_provider = AsyncMock()
        mock_vision_response = VisionAnalysisResponse(
            answer="The page is accessible",
            confidence=0.92,
            reasoning="Excellent contrast and keyboard navigation",
            metadata={"accessibility_score": 95},
            provider="anthropic",
            model="claude-3-haiku",
        )
        mock_provider.analyze_image_async.return_value = mock_vision_response

        with patch("layoutlens.api.core.create_provider", return_value=mock_provider):
            lens = LayoutLens(api_key="test-key", provider="anthropic", model="claude-3-haiku")

            # Mock file path analysis (not URL)
            with (
                patch.object(lens, "_is_url", return_value=False),
                patch("pathlib.Path.exists", return_value=True),
            ):
                result = await lens.analyze_async(
                    source="/path/to/screenshot.png",
                    query="Is this accessible?",
                    context={"focus": "accessibility"},
                )

        # Verify async provider was called
        mock_provider.analyze_image_async.assert_called_once()
        call_args = mock_provider.analyze_image_async.call_args[0][0]
        assert call_args.image_path == "/path/to/screenshot.png"
        assert call_args.query == "Is this accessible?"
        assert call_args.context == {"focus": "accessibility"}

        # Verify result
        assert result.answer == "The page is accessible"
        assert result.confidence == 0.92
        assert result.metadata["provider"] == "anthropic"
        assert result.metadata["model"] == "claude-3-haiku"

    @patch("layoutlens.api.core.URLCapture")
    @patch("layoutlens.api.core.LayoutComparator")
    @patch("layoutlens.api.core.create_cache")
    def test_analyze_with_file_path(self, mock_cache, mock_comparator, mock_capture):
        """Test analyze method with local file path."""
        mock_cache_instance = Mock()
        mock_cache_instance.get.return_value = None
        mock_cache.return_value = mock_cache_instance

        mock_provider = Mock()
        mock_vision_response = VisionAnalysisResponse(
            answer="Mobile layout looks good",
            confidence=0.78,
            reasoning="Responsive design with appropriate touch targets",
            metadata={"viewport": "mobile"},
            provider="google",
            model="gemini-1.5-flash",
        )
        mock_provider.analyze_image.return_value = mock_vision_response

        with patch("layoutlens.api.core.create_provider", return_value=mock_provider):
            lens = LayoutLens(api_key="test-key", provider="google", model="gemini-1.5-flash")

            with patch("pathlib.Path.exists", return_value=True):
                result = lens.analyze(
                    source=Path("/path/to/mobile_screenshot.png"),
                    query="Is this mobile-friendly?",
                    viewport="mobile_portrait",
                )

        # Verify provider was called with file path directly
        call_args = mock_provider.analyze_image.call_args[0][0]
        assert call_args.image_path == "/path/to/mobile_screenshot.png"
        assert call_args.source_url is None  # No URL for file path
        assert call_args.viewport == "mobile_portrait"

        assert result.answer == "Mobile layout looks good"
        assert result.metadata["provider"] == "google"
        assert result.metadata["model"] == "gemini-1.5-flash"

    @patch("layoutlens.api.core.URLCapture")
    @patch("layoutlens.api.core.LayoutComparator")
    @patch("layoutlens.api.core.create_cache")
    @pytest.mark.asyncio
    async def test_analyze_batch_async_with_provider(self, mock_cache, mock_comparator, mock_capture):
        """Test async batch analysis with providers."""
        mock_cache_instance = Mock()
        mock_cache_instance.get.return_value = None
        mock_cache.return_value = mock_cache_instance

        # Mock provider responses
        mock_provider = AsyncMock()
        responses = [
            VisionAnalysisResponse(
                answer=f"Page {i} analysis",
                confidence=0.8 + i * 0.05,
                reasoning=f"Analysis for page {i}",
                metadata={},
                provider="openrouter",
                model="gpt-4o-mini",
            )
            for i in range(3)
        ]
        mock_provider.analyze_image_async.side_effect = responses

        with patch("layoutlens.api.core.create_provider", return_value=mock_provider):
            lens = LayoutLens(api_key="test-key")

            with (
                patch.object(lens, "_is_url", return_value=False),
                patch("pathlib.Path.exists", return_value=True),
            ):
                batch_result = await lens.analyze_batch_async(
                    sources=[f"/path/page{i}.png" for i in range(3)],
                    queries=["Is this good design?"],
                    max_concurrent=2,
                )

        # Verify all analyses were called
        assert mock_provider.analyze_image_async.call_count == 3
        assert len(batch_result.results) == 3
        assert batch_result.successful_queries == 3
        assert batch_result.average_confidence > 0.8

    def test_provider_error_handling(self):
        """Test error handling in provider integration."""
        with patch("layoutlens.api.core.create_provider") as mock_create:
            mock_create.side_effect = ConfigurationError("Invalid provider configuration")

            with pytest.raises(ConfigurationError, match="Invalid provider configuration"):
                LayoutLens(api_key="test-key", provider="invalid")


class TestBackwardCompatibility:
    """Test backward compatibility with existing API."""

    @patch("layoutlens.api.core.create_provider")
    @patch("layoutlens.api.core.URLCapture")
    @patch("layoutlens.api.core.LayoutComparator")
    @patch("layoutlens.api.core.create_cache")
    def test_old_initialization_still_works(self, mock_cache, mock_comparator, mock_capture, mock_create):
        """Test that old initialization patterns still work."""
        mock_provider = Mock()
        mock_create.return_value = mock_provider
        mock_cache.return_value = Mock()

        # Old style initialization without provider argument
        lens = LayoutLens(api_key="test-key", model="gpt-4o")

        # Should default to openrouter provider
        mock_create.assert_called_once_with(provider_name="openrouter", api_key="test-key", model="gpt-4o")

    @patch("layoutlens.api.core.create_provider")
    @patch("layoutlens.api.core.URLCapture")
    @patch("layoutlens.api.core.LayoutComparator")
    @patch("layoutlens.api.core.create_cache")
    def test_existing_methods_work(self, mock_cache, mock_comparator, mock_capture, mock_create):
        """Test that existing public methods continue to work."""
        mock_provider = Mock()
        mock_create.return_value = mock_provider
        mock_cache_instance = Mock()
        mock_cache_instance.get.return_value = None
        mock_cache.return_value = mock_cache_instance

        # Mock a simple response
        mock_response = VisionAnalysisResponse(
            answer="Test answer",
            confidence=0.9,
            reasoning="Test reasoning",
            metadata={},
            provider="openrouter",
            model="gpt-4o-mini",
        )
        mock_provider.analyze_image.return_value = mock_response

        lens = LayoutLens(api_key="test-key")

        # Test that built-in methods still work
        with patch.object(lens, "_is_url", return_value=False), patch("pathlib.Path.exists", return_value=True):
            # These methods should work without modification
            result = lens.check_accessibility("/path/to/image.png")
            assert result.answer == "Test answer"

            result = lens.check_mobile_friendly("/path/to/image.png")
            assert result.answer == "Test answer"
