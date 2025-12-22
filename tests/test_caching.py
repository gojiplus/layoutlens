"""Tests for the caching functionality."""

import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from layoutlens import LayoutLens
from layoutlens.api.core import AnalysisResult
from layoutlens.cache import (
    AnalysisCache,
    CacheEntry,
    FileCache,
    InMemoryCache,
    create_cache,
)
from layoutlens.exceptions import ConfigurationError


class TestCacheEntry:
    """Test CacheEntry functionality."""

    def test_cache_entry_creation(self):
        """Test creating a cache entry."""
        result = AnalysisResult(
            source="test.html",
            query="Is this good?",
            answer="Yes",
            confidence=0.9,
            reasoning="Good design",
        )

        entry = CacheEntry(key="test_key", result=result, timestamp=time.time(), ttl_seconds=300)

        assert entry.key == "test_key"
        assert entry.result == result
        assert not entry.is_expired
        assert entry.age_seconds >= 0

    def test_cache_entry_expiration(self):
        """Test cache entry expiration."""
        result = AnalysisResult(
            source="test.html",
            query="Is this good?",
            answer="Yes",
            confidence=0.9,
            reasoning="Good design",
        )

        # Create expired entry
        old_timestamp = time.time() - 3700  # 1 hour 1 minute ago
        entry = CacheEntry(
            key="test_key",
            result=result,
            timestamp=old_timestamp,
            ttl_seconds=3600,  # 1 hour
        )

        assert entry.is_expired
        assert entry.age_seconds > 3600

    def test_never_expires(self):
        """Test entry that never expires."""
        result = AnalysisResult(
            source="test.html",
            query="Is this good?",
            answer="Yes",
            confidence=0.9,
            reasoning="Good design",
        )

        entry = CacheEntry(
            key="test_key",
            result=result,
            timestamp=time.time() - 10000,
            ttl_seconds=0,  # Never expires
        )

        assert not entry.is_expired


class TestInMemoryCache:
    """Test in-memory cache backend."""

    def test_basic_operations(self):
        """Test basic get/set/delete operations."""
        cache = InMemoryCache(max_size=10)

        result = AnalysisResult(
            source="test.html",
            query="Is this good?",
            answer="Yes",
            confidence=0.9,
            reasoning="Good design",
        )

        entry = CacheEntry(key="test_key", result=result, timestamp=time.time(), ttl_seconds=3600)

        # Test set and get
        cache.set("test_key", entry)
        retrieved = cache.get("test_key")

        assert retrieved == entry
        assert cache.size() == 1

        # Test delete
        assert cache.delete("test_key")
        assert cache.get("test_key") is None
        assert cache.size() == 0

    def test_expiration_handling(self):
        """Test automatic expiration handling."""
        cache = InMemoryCache()

        result = AnalysisResult(
            source="test.html",
            query="Is this good?",
            answer="Yes",
            confidence=0.9,
            reasoning="Good design",
        )

        # Create expired entry
        expired_entry = CacheEntry(
            key="expired_key",
            result=result,
            timestamp=time.time() - 7200,
            ttl_seconds=3600,
        )

        cache.set("expired_key", expired_entry)

        # Should return None and remove expired entry
        assert cache.get("expired_key") is None
        assert cache.size() == 0

    def test_max_size_eviction(self):
        """Test eviction when max size is reached."""
        cache = InMemoryCache(max_size=2)

        result = AnalysisResult(
            source="test.html",
            query="Is this good?",
            answer="Yes",
            confidence=0.9,
            reasoning="Good design",
        )

        # Add first entry
        entry1 = CacheEntry("key1", result, time.time(), 3600)
        cache.set("key1", entry1)
        time.sleep(0.01)  # Small delay to ensure different timestamps

        # Add second entry
        entry2 = CacheEntry("key2", result, time.time(), 3600)
        cache.set("key2", entry2)
        time.sleep(0.01)

        # Add third entry - should evict oldest (key1)
        entry3 = CacheEntry("key3", result, time.time(), 3600)
        cache.set("key3", entry3)

        assert cache.size() == 2
        assert cache.get("key1") is None  # Evicted
        assert cache.get("key2") is not None
        assert cache.get("key3") is not None


class TestFileCache:
    """Test file-based cache backend."""

    def test_basic_operations(self):
        """Test basic file cache operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = FileCache(cache_dir=temp_dir, max_files=10)

            result = AnalysisResult(
                source="test.html",
                query="Is this good?",
                answer="Yes",
                confidence=0.9,
                reasoning="Good design",
            )

            entry = CacheEntry(key="test_key", result=result, timestamp=time.time(), ttl_seconds=3600)

            # Test set and get
            cache.set("test_key", entry)
            retrieved = cache.get("test_key")

            assert retrieved.key == entry.key
            assert retrieved.result.answer == entry.result.answer
            assert cache.size() == 1

            # Test delete
            assert cache.delete("test_key")
            assert cache.get("test_key") is None
            assert cache.size() == 0

    def test_persistence(self):
        """Test that cache persists across instances."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = AnalysisResult(
                source="test.html",
                query="Is this good?",
                answer="Yes",
                confidence=0.9,
                reasoning="Good design",
            )

            entry = CacheEntry(
                key="persist_key",
                result=result,
                timestamp=time.time(),
                ttl_seconds=3600,
            )

            # Create first cache instance and store
            cache1 = FileCache(cache_dir=temp_dir)
            cache1.set("persist_key", entry)

            # Create second cache instance and retrieve
            cache2 = FileCache(cache_dir=temp_dir)
            retrieved = cache2.get("persist_key")

            assert retrieved is not None
            assert retrieved.key == entry.key


class TestAnalysisCache:
    """Test high-level analysis cache."""

    def test_key_generation(self):
        """Test cache key generation."""
        cache = AnalysisCache()

        # Test analysis key
        key1 = cache.get_analysis_key(
            source="https://example.com",
            query="Is this accessible?",
            viewport="desktop",
        )

        key2 = cache.get_analysis_key(
            source="https://example.com",
            query="Is this accessible?",
            viewport="desktop",
        )

        # Same inputs should generate same key
        assert key1 == key2

        # Different query should generate different key
        key3 = cache.get_analysis_key(
            source="https://example.com",
            query="Is this mobile-friendly?",
            viewport="desktop",
        )

        assert key1 != key3

    def test_comparison_key_generation(self):
        """Test comparison cache key generation."""
        cache = AnalysisCache()

        key1 = cache.get_comparison_key(sources=["page1.html", "page2.html"], query="Which is better?")

        # Order should not matter
        key2 = cache.get_comparison_key(sources=["page2.html", "page1.html"], query="Which is better?")

        assert key1 == key2

    def test_cache_operations(self):
        """Test cache get/set operations."""
        cache = AnalysisCache()

        result = AnalysisResult(
            source="test.html",
            query="Is this good?",
            answer="Yes",
            confidence=0.9,
            reasoning="Good design",
        )

        cache.set("test_key", result)
        retrieved = cache.get("test_key")

        assert retrieved == result

        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 1.0

    def test_disabled_cache(self):
        """Test cache when disabled."""
        cache = AnalysisCache(enabled=False)

        result = AnalysisResult(
            source="test.html",
            query="Is this good?",
            answer="Yes",
            confidence=0.9,
            reasoning="Good design",
        )

        cache.set("test_key", result)
        retrieved = cache.get("test_key")

        assert retrieved is None

        stats = cache.stats()
        assert stats["enabled"] is False


class TestCacheFactory:
    """Test cache creation factory."""

    def test_memory_cache_creation(self):
        """Test creating memory cache."""
        cache = create_cache(cache_type="memory", max_size=100)

        assert isinstance(cache.backend, InMemoryCache)
        assert cache.backend.max_size == 100

    def test_file_cache_creation(self):
        """Test creating file cache."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = create_cache(cache_type="file", cache_dir=temp_dir, max_size=50)

            assert isinstance(cache.backend, FileCache)
            assert cache.backend.max_files == 50

    def test_invalid_cache_type(self):
        """Test invalid cache type raises error."""
        with pytest.raises(ConfigurationError):
            create_cache(cache_type="invalid")


class TestLayoutLensCacheIntegration:
    """Test caching integration with LayoutLens."""

    @patch("layoutlens.vision.capture.Capture.screenshots")
    @patch("layoutlens.api.core.acompletion")
    @pytest.mark.asyncio
    async def test_cache_hit(self, mock_acompletion, mock_capture):
        """Test cache hit behavior."""
        # Setup mocks
        mock_capture.return_value = ["screenshot.png"]

        # Mock LiteLLM acompletion response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[
            0
        ].message.content = '{"answer": "Yes, it\'s accessible", "confidence": 0.9, "reasoning": "Good design"}'
        mock_response.usage.total_tokens = 150
        mock_acompletion.return_value = mock_response

        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"}),
            patch("os.path.exists", return_value=True),
            patch("layoutlens.api.core.LayoutLens._encode_image", return_value="fake-base64-data"),
        ):
            lens = LayoutLens(cache_enabled=True, cache_type="memory")

            # First call - should hit API
            result1 = await lens.analyze("https://example.com", "Is this accessible?")
            assert result1.metadata.get("cache_hit") is False

            # Second call - should hit cache
            result2 = await lens.analyze("https://example.com", "Is this accessible?")
            assert result2.metadata.get("cache_hit") is True

            # Should have called acompletion only once
            assert mock_acompletion.call_count == 1

            # Check cache stats
            stats = lens.get_cache_stats()
            assert stats["hits"] == 1
            assert stats["misses"] == 1
            assert stats["hit_rate"] == 0.5

    @patch("layoutlens.vision.capture.Capture.screenshots")
    @patch("layoutlens.api.core.acompletion")
    @pytest.mark.asyncio
    async def test_cache_disabled(self, mock_acompletion, mock_capture):
        """Test behavior with cache disabled."""
        # Setup mocks
        mock_capture.return_value = ["screenshot.png"]

        # Mock LiteLLM acompletion response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[
            0
        ].message.content = '{"answer": "Yes, it\'s accessible", "confidence": 0.9, "reasoning": "Good design"}'
        mock_response.usage.total_tokens = 150
        mock_acompletion.return_value = mock_response

        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"}),
            patch("os.path.exists", return_value=True),
            patch("layoutlens.api.core.LayoutLens._encode_image", return_value="fake-base64-data"),
        ):
            lens = LayoutLens(cache_enabled=False)

            # Make two identical calls
            await lens.analyze("https://example.com", "Is this accessible?")
            await lens.analyze("https://example.com", "Is this accessible?")

            # Should have called acompletion twice (no caching)
            assert mock_acompletion.call_count == 2

            # Cache stats should show no hits
            stats = lens.get_cache_stats()
            assert stats["hits"] == 0
            assert stats["enabled"] is False

    def test_cache_management_methods(self):
        """Test cache management methods."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"}):
            lens = LayoutLens(cache_enabled=True)

            # Test initial state
            stats = lens.get_cache_stats()
            assert stats["enabled"] is True

            # Test disable/enable
            lens.disable_cache()
            assert lens.cache.enabled is False

            lens.enable_cache()
            assert lens.cache.enabled is True

            # Test clear cache
            lens.clear_cache()
            stats = lens.get_cache_stats()
            assert stats["size"] == 0


class TestCachePerformance:
    """Test cache performance characteristics."""

    def test_key_generation_performance(self):
        """Test that key generation is fast."""
        cache = AnalysisCache()

        start_time = time.time()
        for i in range(1000):
            cache.get_analysis_key(source=f"https://example{i}.com", query=f"Query {i}", viewport="desktop")

        elapsed = time.time() - start_time
        assert elapsed < 1.0  # Should be very fast

    def test_memory_cache_performance(self):
        """Test memory cache performance."""
        cache = InMemoryCache(max_size=1000)

        result = AnalysisResult(
            source="test.html",
            query="Is this good?",
            answer="Yes",
            confidence=0.9,
            reasoning="Good design",
        )

        entries = [CacheEntry(f"key_{i}", result, time.time(), 3600) for i in range(100)]

        # Test write performance
        start_time = time.time()
        for entry in entries:
            cache.set(entry.key, entry)
        write_time = time.time() - start_time

        # Test read performance
        start_time = time.time()
        for entry in entries:
            retrieved = cache.get(entry.key)
            assert retrieved is not None
        read_time = time.time() - start_time

        # Should be fast
        assert write_time < 0.1
        assert read_time < 0.1
