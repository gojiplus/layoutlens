"""Screenshot management utilities for LayoutLens 2-stage pipeline."""

import hashlib
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ..logger import get_logger


class ScreenshotManager:
    """Manages screenshot files for 2-stage pipeline operations.

    Provides utilities for organizing, finding, and managing screenshot files
    captured during the first stage of the 2-stage pipeline.
    """

    def __init__(self, output_dir: str | Path = "layoutlens_output"):
        """Initialize screenshot manager.

        Args:
            output_dir: Base output directory for LayoutLens.
        """
        self.output_dir = Path(output_dir)
        self.screenshots_dir = self.output_dir / "screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

        self.logger = get_logger("utils.screenshot_manager")
        self.logger.debug(f"ScreenshotManager initialized with output_dir: {output_dir}")

    def generate_screenshot_path(
        self,
        source: str,
        viewport: str = "desktop",
        use_timestamp: bool = True,
    ) -> Path:
        """Generate a standardized screenshot file path.

        Args:
            source: URL or identifier for the source.
            viewport: Viewport size used for capture.
            use_timestamp: Whether to include timestamp in filename.

        Returns:
            Path object for the screenshot file.
        """
        # Create safe filename from source
        if self._is_url(source):
            parsed = urlparse(source)
            domain = parsed.netloc.replace("www.", "").replace(".", "_")
            path_part = parsed.path.replace("/", "_").replace(".", "_")
            safe_name = f"{domain}{path_part}".replace(":", "")
        else:
            # For file paths, use the filename
            safe_name = Path(source).stem.replace(".", "_")

        # Truncate if too long
        if len(safe_name) > 50:
            safe_name = safe_name[:50]

        # Add hash for uniqueness
        source_hash = hashlib.sha256(source.encode()).hexdigest()[:8]

        # Build filename components
        components = [safe_name, viewport, source_hash]

        if use_timestamp:
            timestamp = int(time.time())
            components.append(str(timestamp))

        filename = "_".join(components) + ".png"
        return self.screenshots_dir / filename

    def find_screenshots_by_source(self, source: str, viewport: str | None = None) -> list[Path]:
        """Find all screenshots for a given source.

        Args:
            source: Source URL or identifier.
            viewport: Optional viewport filter.

        Returns:
            List of screenshot paths matching the criteria.
        """
        source_hash = hashlib.sha256(source.encode()).hexdigest()[:8]

        pattern_parts = ["*", "*", source_hash]
        if viewport:
            pattern_parts[1] = viewport

        pattern = "_".join(pattern_parts) + "*.png"
        matches = list(self.screenshots_dir.glob(pattern))

        # Sort by modification time (newest first)
        matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        self.logger.debug(f"Found {len(matches)} screenshots for source: {source[:50]}...")
        return matches

    def find_latest_screenshot(self, source: str, viewport: str = "desktop") -> Path | None:
        """Find the most recent screenshot for a source and viewport.

        Args:
            source: Source URL or identifier.
            viewport: Viewport size.

        Returns:
            Path to most recent screenshot, or None if not found.
        """
        screenshots = self.find_screenshots_by_source(source, viewport)
        if screenshots:
            self.logger.debug(f"Found latest screenshot: {screenshots[0].name}")
            return screenshots[0]

        self.logger.debug(f"No screenshots found for {source} ({viewport})")
        return None

    def organize_screenshots(self, group_by: str = "date") -> dict[str, list[Path]]:
        """Organize screenshots into groups.

        Args:
            group_by: Grouping strategy ("date", "viewport", "domain").

        Returns:
            Dictionary mapping group names to lists of screenshot paths.
        """
        screenshots = list(self.screenshots_dir.glob("*.png"))
        groups: dict[str, list[Path]] = {}

        for screenshot in screenshots:
            if group_by == "date":
                # Group by creation date
                mtime = screenshot.stat().st_mtime
                date_str = time.strftime("%Y-%m-%d", time.localtime(mtime))
                key = date_str
            elif group_by == "viewport":
                # Group by viewport (second component in filename)
                parts = screenshot.stem.split("_")
                key = parts[1] if len(parts) > 1 else "unknown"
            elif group_by == "domain":
                # Group by domain (first component in filename)
                parts = screenshot.stem.split("_")
                key = parts[0] if parts else "unknown"
            else:
                key = "all"

            if key not in groups:
                groups[key] = []
            groups[key].append(screenshot)

        # Sort each group by modification time
        for group_list in groups.values():
            group_list.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        self.logger.debug(f"Organized {len(screenshots)} screenshots into {len(groups)} groups by {group_by}")
        return groups

    def cleanup_old_screenshots(self, max_age_days: int = 30) -> int:
        """Clean up screenshots older than specified age.

        Args:
            max_age_days: Maximum age in days for screenshots to keep.

        Returns:
            Number of screenshots deleted.
        """
        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
        screenshots = list(self.screenshots_dir.glob("*.png"))

        deleted_count = 0
        for screenshot in screenshots:
            if screenshot.stat().st_mtime < cutoff_time:
                try:
                    screenshot.unlink()
                    deleted_count += 1
                    self.logger.debug(f"Deleted old screenshot: {screenshot.name}")
                except Exception as e:
                    self.logger.warning(f"Failed to delete {screenshot.name}: {e}")

        self.logger.info(f"Cleaned up {deleted_count} old screenshots (older than {max_age_days} days)")
        return deleted_count

    def get_screenshot_info(self, screenshot_path: Path) -> dict[str, Any]:
        """Get metadata information about a screenshot.

        Args:
            screenshot_path: Path to the screenshot file.

        Returns:
            Dictionary with screenshot metadata.
        """
        if not screenshot_path.exists():
            return {"error": "File not found"}

        stat = screenshot_path.stat()
        parts = screenshot_path.stem.split("_")

        info = {
            "filename": screenshot_path.name,
            "size_bytes": stat.st_size,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "created": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_ctime)),
            "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
            "age_hours": round((time.time() - stat.st_mtime) / 3600, 1),
        }

        # Parse filename components if possible
        if len(parts) >= 3:
            info.update(
                {
                    "source_name": parts[0],
                    "viewport": parts[1],
                    "source_hash": parts[2],
                }
            )

            if len(parts) >= 4:
                try:
                    timestamp = int(parts[3])
                    info["capture_time"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
                except ValueError:
                    pass

        return info

    def list_screenshots(self, detailed: bool = False) -> list[dict[str, Any]]:
        """List all screenshots with optional detailed information.

        Args:
            detailed: Whether to include detailed metadata.

        Returns:
            List of dictionaries with screenshot information.
        """
        screenshots = list(self.screenshots_dir.glob("*.png"))
        screenshots.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        if detailed:
            return [self.get_screenshot_info(screenshot) for screenshot in screenshots]
        else:
            return [
                {
                    "filename": screenshot.name,
                    "size_mb": round(screenshot.stat().st_size / (1024 * 1024), 2),
                    "age_hours": round((time.time() - screenshot.stat().st_mtime) / 3600, 1),
                }
                for screenshot in screenshots
            ]

    def get_storage_stats(self) -> dict[str, Any]:
        """Get storage statistics for screenshots.

        Returns:
            Dictionary with storage statistics.
        """
        screenshots = list(self.screenshots_dir.glob("*.png"))

        if not screenshots:
            return {
                "total_screenshots": 0,
                "total_size_mb": 0,
                "average_size_mb": 0,
                "oldest_screenshot": None,
                "newest_screenshot": None,
            }

        total_size = sum(s.stat().st_size for s in screenshots)
        sizes = [s.stat().st_size for s in screenshots]
        times = [s.stat().st_mtime for s in screenshots]

        return {
            "total_screenshots": len(screenshots),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "average_size_mb": round((total_size / len(screenshots)) / (1024 * 1024), 2),
            "largest_size_mb": round(max(sizes) / (1024 * 1024), 2),
            "smallest_size_mb": round(min(sizes) / (1024 * 1024), 2),
            "oldest_screenshot": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(min(times))),
            "newest_screenshot": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(max(times))),
            "directory": str(self.screenshots_dir),
        }

    def _is_url(self, source: str) -> bool:
        """Check if source is a URL."""
        parsed = urlparse(str(source))
        return bool(parsed.scheme and parsed.netloc)
