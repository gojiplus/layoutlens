"""Caching mechanism for LayoutLens to reduce API calls and improve performance."""

import hashlib
import json
import pickle  # nosec B403 - Used only for internal caching, not user input
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Use TYPE_CHECKING to avoid circular imports

if TYPE_CHECKING:
    from .api.core import AnalysisResult, ComparisonResult

from .exceptions import ConfigurationError


@dataclass
class CacheEntry:
    """Represents a cached analysis result."""

    key: str
    result: "AnalysisResult | ComparisonResult"
    timestamp: float
    ttl_seconds: int = 3600  # 1 hour default
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    @property
    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        if self.ttl_seconds <= 0:  # Never expires
            return False
        return time.time() - self.timestamp > self.ttl_seconds

    @property
    def age_seconds(self) -> float:
        """Get the age of the cache entry in seconds."""
        return time.time() - self.timestamp


class CacheBackend(ABC):
    """Abstract base class for cache backends."""

    @abstractmethod
    def get(self, key: str) -> CacheEntry | None:
        """Retrieve a cache entry by key."""
        pass

    @abstractmethod
    def set(self, key: str, entry: CacheEntry) -> None:
        """Store a cache entry."""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a cache entry."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all cache entries."""
        pass

    @abstractmethod
    def size(self) -> int:
        """Get the number of cached entries."""
        pass


class InMemoryCache(CacheBackend):
    """In-memory cache implementation."""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: dict[str, CacheEntry] = {}

    def get(self, key: str) -> CacheEntry | None:
        """Retrieve a cache entry by key."""
        entry = self._cache.get(key)
        if entry and entry.is_expired:
            del self._cache[key]
            return None
        return entry

    def set(self, key: str, entry: CacheEntry) -> None:
        """Store a cache entry."""
        # Evict expired entries first
        self._evict_expired()

        # If at max size, remove oldest entry
        if len(self._cache) >= self.max_size:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].timestamp)
            del self._cache[oldest_key]

        self._cache[key] = entry

    def delete(self, key: str) -> bool:
        """Delete a cache entry."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()

    def size(self) -> int:
        """Get the number of cached entries."""
        return len(self._cache)

    def _evict_expired(self) -> None:
        """Remove expired entries."""
        expired_keys = [key for key, entry in self._cache.items() if entry.is_expired]
        for key in expired_keys:
            del self._cache[key]


class FileCache(CacheBackend):
    """File-based cache implementation using pickle."""

    def __init__(self, cache_dir: str | Path = ".layoutlens_cache", max_files: int = 500):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.max_files = max_files

    def get(self, key: str) -> CacheEntry | None:
        """Retrieve a cache entry by key."""
        file_path = self._get_file_path(key)

        if not file_path.exists():
            return None

        try:
            with open(file_path, "rb") as f:
                entry = pickle.load(f)  # nosec B301 - Internal cache file, not user input

            if entry.is_expired:
                file_path.unlink()
                return None

            return entry

        except (pickle.PickleError, EOFError, OSError):
            # Corrupted file, remove it
            file_path.unlink(missing_ok=True)
            return None

    def set(self, key: str, entry: CacheEntry) -> None:
        """Store a cache entry."""
        # Clean up expired files
        self._cleanup_expired()

        # If at max files, remove oldest
        if self._count_files() >= self.max_files:
            self._remove_oldest()

        file_path = self._get_file_path(key)
        try:
            with open(file_path, "wb") as f:
                pickle.dump(entry, f)
        except (pickle.PickleError, OSError) as e:
            raise ConfigurationError(f"Failed to write cache file: {e}") from e

    def delete(self, key: str) -> bool:
        """Delete a cache entry."""
        file_path = self._get_file_path(key)
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def clear(self) -> None:
        """Clear all cache entries."""
        for file_path in self.cache_dir.glob("*.cache"):
            file_path.unlink()

    def size(self) -> int:
        """Get the number of cached entries."""
        return self._count_files()

    def _get_file_path(self, key: str) -> Path:
        """Get the file path for a cache key."""
        return self.cache_dir / f"{key}.cache"

    def _count_files(self) -> int:
        """Count cache files."""
        return len(list(self.cache_dir.glob("*.cache")))

    def _cleanup_expired(self) -> None:
        """Remove expired cache files."""
        for file_path in self.cache_dir.glob("*.cache"):
            try:
                with open(file_path, "rb") as f:
                    entry = pickle.load(f)  # nosec B301 - Internal cache file, not user input
                if entry.is_expired:
                    file_path.unlink()
            except (pickle.PickleError, EOFError, OSError):
                file_path.unlink(missing_ok=True)

    def _remove_oldest(self) -> None:
        """Remove the oldest cache file."""
        cache_files = list(self.cache_dir.glob("*.cache"))
        if cache_files:
            oldest_file = min(cache_files, key=lambda f: f.stat().st_mtime)
            oldest_file.unlink()


class AnalysisCache:
    """High-level cache manager for LayoutLens analysis results."""

    def __init__(
        self,
        backend: CacheBackend = None,
        default_ttl: int = 3600,
        enabled: bool = True,
    ):
        """
        Initialize the analysis cache.

        Parameters
        ----------
        backend : CacheBackend, optional
            Cache backend to use. Defaults to InMemoryCache.
        default_ttl : int, default 3600
            Default time-to-live in seconds for cache entries.
        enabled : bool, default True
            Whether caching is enabled.
        """
        self.backend = backend or InMemoryCache()
        self.default_ttl = default_ttl
        self.enabled = enabled

        # Statistics
        self.hits = 0
        self.misses = 0

    def get_analysis_key(
        self,
        source: str,
        query: str,
        viewport: str = "desktop",
        context: dict[str, Any] = None,
    ) -> str:
        """Generate a cache key for an analysis request."""
        # Include screenshot content hash for files
        source_hash = self._get_source_hash(source)

        # Create content to hash
        content = {
            "source": source,
            "source_hash": source_hash,
            "query": query.strip().lower(),
            "viewport": viewport,
            "context": context or {},
        }

        # Create stable hash
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()[:16]

    def get_comparison_key(
        self,
        sources: list,
        query: str = "Are these layouts consistent?",
        viewport: str = "desktop",
        context: dict[str, Any] = None,
    ) -> str:
        """Generate a cache key for a comparison request."""
        # Sort sources for consistent hashing
        sorted_sources = sorted(str(s) for s in sources)
        source_hashes = [self._get_source_hash(s) for s in sorted_sources]

        content = {
            "sources": sorted_sources,
            "source_hashes": source_hashes,
            "query": query.strip().lower(),
            "viewport": viewport,
            "context": context or {},
        }

        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()[:16]

    def get(self, key: str) -> "AnalysisResult | ComparisonResult | None":
        """Get a cached result."""
        if not self.enabled:
            return None

        entry = self.backend.get(key)
        if entry:
            self.hits += 1
            return entry.result

        self.misses += 1
        return None

    def set(
        self,
        key: str,
        result: "AnalysisResult | ComparisonResult",
        ttl: int = None,
    ) -> None:
        """Cache a result."""
        if not self.enabled:
            return

        entry = CacheEntry(
            key=key,
            result=result,
            timestamp=time.time(),
            ttl_seconds=ttl or self.default_ttl,
            metadata={
                "type": type(result).__name__,
                "confidence": getattr(result, "confidence", 0),
            },
        )

        self.backend.set(key, entry)

    def clear(self) -> None:
        """Clear all cached results."""
        self.backend.clear()
        self.hits = 0
        self.misses = 0

    def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.hits + self.misses
        hit_rate = self.hits / total_requests if total_requests > 0 else 0

        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "size": self.backend.size(),
            "enabled": self.enabled,
        }

    def _get_source_hash(self, source: str) -> str:
        """Get a hash for the source content."""
        source_path = Path(source)

        # For local files, hash the content
        if source_path.exists():
            try:
                with open(source_path, "rb") as f:
                    content = f.read()
                return hashlib.sha256(content).hexdigest()[:16]
            except OSError:
                pass

        # For URLs or non-existent files, just hash the string
        return hashlib.sha256(str(source).encode()).hexdigest()[:16]


# Factory function for easy cache creation
def create_cache(
    cache_type: str = "memory",
    cache_dir: str | Path = ".layoutlens_cache",
    max_size: int = 1000,
    default_ttl: int = 3600,
    enabled: bool = True,
) -> AnalysisCache:
    """
    Create an AnalysisCache with the specified backend.

    Parameters
    ----------
    cache_type : str, default "memory"
        Type of cache backend: "memory" or "file"
    cache_dir : str or Path, default ".layoutlens_cache"
        Directory for file cache (only used if cache_type="file")
    max_size : int, default 1000
        Maximum number of cache entries
    default_ttl : int, default 3600
        Default time-to-live in seconds
    enabled : bool, default True
        Whether caching is enabled

    Returns
    -------
    AnalysisCache
        Configured cache instance
    """
    backend: InMemoryCache | FileCache
    if cache_type == "memory":
        backend = InMemoryCache(max_size=max_size)
    elif cache_type == "file":
        backend = FileCache(cache_dir=cache_dir, max_files=max_size)
    else:
        raise ConfigurationError(f"Unknown cache type: {cache_type}")

    return AnalysisCache(backend=backend, default_ttl=default_ttl, enabled=enabled)
