"""Configuration management for LayoutLens testing framework."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union

import yaml


@dataclass
class ViewportConfig:
    """Viewport configuration for testing."""

    name: str
    width: int
    height: int
    device_scale_factor: float = 1.0
    is_mobile: bool = False
    has_touch: bool = False
    user_agent: str | None = None


@dataclass
class LLMConfig:
    """Configuration for Language Model providers."""

    provider: str = "openai"  # openai, anthropic, etc.
    model: str = "gpt-4o-mini"
    api_key: str | None = None
    api_key_env: str = "OPENAI_API_KEY"
    max_retries: int = 3
    timeout: int = 60
    temperature: float = 0.1
    custom_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScreenshotConfig:
    """Configuration for screenshot capture."""

    format: str = "png"  # png, jpeg
    quality: int | None = None  # for jpeg
    full_page: bool = True
    omit_background: bool = False
    animations: str = "disabled"  # disabled, allow
    wait_timeout: int = 30000  # milliseconds
    wait_for_selector: str | None = None
    mask_selectors: list[str] = field(default_factory=list)
    mask_color: str = "#FF0000"


@dataclass
class TestConfig:
    """Configuration for test execution."""

    auto_generate_queries: bool = True
    focus_areas: list[str] = field(default_factory=lambda: ["typography", "layout", "color", "accessibility"])
    parallel_execution: bool = False
    max_workers: int = 4
    continue_on_error: bool = True
    save_screenshots: bool = True
    save_detailed_results: bool = True


@dataclass
class OutputConfig:
    """Configuration for output and reporting."""

    base_dir: str = "layoutlens_output"
    screenshots_dir: str = "screenshots"
    results_dir: str = "results"
    reports_dir: str = "reports"
    format: str = "json"  # json, yaml, html
    include_metadata: bool = True
    compress_results: bool = False


class Config:
    """Main configuration class for LayoutLens framework.

    This class manages all configuration aspects including:
    - LLM provider settings
    - Viewport configurations
    - Screenshot options
    - Test execution parameters
    - Output and reporting settings
    """

    # Default viewport presets
    DEFAULT_VIEWPORTS = [
        ViewportConfig("mobile_portrait", 375, 667, 2.0, True, True),
        ViewportConfig("tablet_portrait", 768, 1024, 2.0, True, True),
        ViewportConfig("desktop", 1440, 900, 1.0, False, False),
        ViewportConfig("desktop_large", 1920, 1080, 1.0, False, False),
    ]

    def __init__(self, config_path: str | None = None):
        """Initialize configuration.

        Parameters
        ----------
        config_path : str, optional
            Path to YAML configuration file
        """
        # Set defaults
        self.llm = LLMConfig()
        self.screenshot = ScreenshotConfig()
        self.test = TestConfig()
        self.output = OutputConfig()
        self.viewports = self.DEFAULT_VIEWPORTS.copy()
        self.custom_queries: dict[str, list[str]] = {}

        # Load from file if provided
        if config_path:
            self.load_from_file(config_path)

        # Override with environment variables
        self._load_from_env()

    def load_from_file(self, config_path: str) -> None:
        """Load configuration from YAML file.

        Parameters
        ----------
        config_path : str
            Path to YAML configuration file
        """
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            return

        # Load LLM configuration
        if "llm" in data:
            llm_data = data["llm"]
            self.llm.provider = llm_data.get("provider", self.llm.provider)
            self.llm.model = llm_data.get("model", self.llm.model)
            self.llm.api_key = llm_data.get("api_key", self.llm.api_key)
            self.llm.api_key_env = llm_data.get("api_key_env", self.llm.api_key_env)
            self.llm.max_retries = llm_data.get("max_retries", self.llm.max_retries)
            self.llm.timeout = llm_data.get("timeout", self.llm.timeout)
            self.llm.temperature = llm_data.get("temperature", self.llm.temperature)
            self.llm.custom_params = llm_data.get("custom_params", self.llm.custom_params)

        # Load screenshot configuration
        if "screenshot" in data:
            screenshot_data = data["screenshot"]
            self.screenshot.format = screenshot_data.get("format", self.screenshot.format)
            self.screenshot.quality = screenshot_data.get("quality", self.screenshot.quality)
            self.screenshot.full_page = screenshot_data.get("full_page", self.screenshot.full_page)
            self.screenshot.omit_background = screenshot_data.get("omit_background", self.screenshot.omit_background)
            self.screenshot.animations = screenshot_data.get("animations", self.screenshot.animations)
            self.screenshot.wait_timeout = screenshot_data.get("wait_timeout", self.screenshot.wait_timeout)
            self.screenshot.wait_for_selector = screenshot_data.get(
                "wait_for_selector", self.screenshot.wait_for_selector
            )
            self.screenshot.mask_selectors = screenshot_data.get("mask_selectors", self.screenshot.mask_selectors)
            self.screenshot.mask_color = screenshot_data.get("mask_color", self.screenshot.mask_color)

        # Load test configuration
        if "test" in data:
            test_data = data["test"]
            self.test.auto_generate_queries = test_data.get("auto_generate_queries", self.test.auto_generate_queries)
            self.test.focus_areas = test_data.get("focus_areas", self.test.focus_areas)
            self.test.parallel_execution = test_data.get("parallel_execution", self.test.parallel_execution)
            self.test.max_workers = test_data.get("max_workers", self.test.max_workers)
            self.test.continue_on_error = test_data.get("continue_on_error", self.test.continue_on_error)
            self.test.save_screenshots = test_data.get("save_screenshots", self.test.save_screenshots)
            self.test.save_detailed_results = test_data.get("save_detailed_results", self.test.save_detailed_results)

        # Load output configuration
        if "output" in data:
            output_data = data["output"]
            self.output.base_dir = output_data.get("base_dir", self.output.base_dir)
            self.output.screenshots_dir = output_data.get("screenshots_dir", self.output.screenshots_dir)
            self.output.results_dir = output_data.get("results_dir", self.output.results_dir)
            self.output.reports_dir = output_data.get("reports_dir", self.output.reports_dir)
            self.output.format = output_data.get("format", self.output.format)
            self.output.include_metadata = output_data.get("include_metadata", self.output.include_metadata)
            self.output.compress_results = output_data.get("compress_results", self.output.compress_results)

        # Load viewport configurations
        if "viewports" in data:
            self.viewports = []
            for viewport_data in data["viewports"]:
                viewport = ViewportConfig(
                    name=viewport_data["name"],
                    width=viewport_data["width"],
                    height=viewport_data["height"],
                    device_scale_factor=viewport_data.get("device_scale_factor", 1.0),
                    is_mobile=viewport_data.get("is_mobile", False),
                    has_touch=viewport_data.get("has_touch", False),
                    user_agent=viewport_data.get("user_agent"),
                )
                self.viewports.append(viewport)

        # Load custom queries
        if "custom_queries" in data:
            self.custom_queries = data["custom_queries"]

    def _load_from_env(self) -> None:
        """Load configuration from environment variables."""
        # API key from environment
        api_key = os.getenv(self.llm.api_key_env)
        if api_key and not self.llm.api_key:
            self.llm.api_key = api_key

        # Other environment overrides
        model_env = os.getenv("LAYOUTLENS_MODEL")
        if model_env:
            self.llm.model = model_env

        output_dir_env = os.getenv("LAYOUTLENS_OUTPUT_DIR")
        if output_dir_env:
            self.output.base_dir = output_dir_env

        parallel_env = os.getenv("LAYOUTLENS_PARALLEL")
        if parallel_env:
            self.test.parallel_execution = parallel_env.lower() == "true"

    def save_to_file(self, config_path: str) -> None:
        """Save current configuration to YAML file.

        Parameters
        ----------
        config_path : str
            Path where to save the configuration file
        """
        data = {
            "llm": {
                "provider": self.llm.provider,
                "model": self.llm.model,
                "api_key_env": self.llm.api_key_env,
                "max_retries": self.llm.max_retries,
                "timeout": self.llm.timeout,
                "temperature": self.llm.temperature,
                "custom_params": self.llm.custom_params,
            },
            "screenshot": {
                "format": self.screenshot.format,
                "quality": self.screenshot.quality,
                "full_page": self.screenshot.full_page,
                "omit_background": self.screenshot.omit_background,
                "animations": self.screenshot.animations,
                "wait_timeout": self.screenshot.wait_timeout,
                "wait_for_selector": self.screenshot.wait_for_selector,
                "mask_selectors": self.screenshot.mask_selectors,
                "mask_color": self.screenshot.mask_color,
            },
            "test": {
                "auto_generate_queries": self.test.auto_generate_queries,
                "focus_areas": self.test.focus_areas,
                "parallel_execution": self.test.parallel_execution,
                "max_workers": self.test.max_workers,
                "continue_on_error": self.test.continue_on_error,
                "save_screenshots": self.test.save_screenshots,
                "save_detailed_results": self.test.save_detailed_results,
            },
            "output": {
                "base_dir": self.output.base_dir,
                "screenshots_dir": self.output.screenshots_dir,
                "results_dir": self.output.results_dir,
                "reports_dir": self.output.reports_dir,
                "format": self.output.format,
                "include_metadata": self.output.include_metadata,
                "compress_results": self.output.compress_results,
            },
            "viewports": [
                {
                    "name": v.name,
                    "width": v.width,
                    "height": v.height,
                    "device_scale_factor": v.device_scale_factor,
                    "is_mobile": v.is_mobile,
                    "has_touch": v.has_touch,
                    "user_agent": v.user_agent,
                }
                for v in self.viewports
            ],
            "custom_queries": self.custom_queries,
        }

        config_file = Path(config_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)

        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, indent=2)

    def get_output_path(self, subdir: str) -> Path:
        """Get path for output subdirectory.

        Parameters
        ----------
        subdir : str
            Subdirectory name (screenshots, results, reports)

        Returns
        -------
        Path
            Full path to the subdirectory
        """
        base_path = Path(self.output.base_dir)

        if subdir == "screenshots":
            return base_path / self.output.screenshots_dir
        elif subdir == "results":
            return base_path / self.output.results_dir
        elif subdir == "reports":
            return base_path / self.output.reports_dir
        else:
            return base_path / subdir

    def get_viewport_by_name(self, name: str) -> ViewportConfig | None:
        """Get viewport configuration by name.

        Parameters
        ----------
        name : str
            Viewport name

        Returns
        -------
        ViewportConfig, optional
            Viewport configuration if found
        """
        for viewport in self.viewports:
            if viewport.name == name:
                return viewport
        return None

    def add_viewport(self, viewport: ViewportConfig) -> None:
        """Add a new viewport configuration.

        Parameters
        ----------
        viewport : ViewportConfig
            Viewport configuration to add
        """
        # Remove existing viewport with same name
        self.viewports = [v for v in self.viewports if v.name != viewport.name]
        self.viewports.append(viewport)

    def add_custom_queries(self, category: str, queries: list[str]) -> None:
        """Add custom queries for a category.

        Parameters
        ----------
        category : str
            Category name for the queries
        queries : list[str]
            List of query strings
        """
        if category not in self.custom_queries:
            self.custom_queries[category] = []
        self.custom_queries[category].extend(queries)

    def validate(self) -> list[str]:
        """Validate configuration and return any issues.

        Returns
        -------
        list[str]
            List of validation errors (empty if valid)
        """
        errors = []

        # Check API key
        if not self.llm.api_key and not os.getenv(self.llm.api_key_env):
            errors.append(f"No API key found. Set {self.llm.api_key_env} environment variable.")

        # Check viewports
        if not self.viewports:
            errors.append("No viewports configured.")

        for viewport in self.viewports:
            if viewport.width <= 0 or viewport.height <= 0:
                errors.append(f"Invalid viewport size for {viewport.name}: {viewport.width}x{viewport.height}")

        # Check output directory
        try:
            Path(self.output.base_dir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"Cannot create output directory {self.output.base_dir}: {e}")

        return errors


def create_default_config(config_path: str) -> Config:
    """Create a default configuration file.

    Parameters
    ----------
    config_path : str
        Path where to save the default configuration

    Returns
    -------
    Config
        The created configuration instance
    """
    config = Config()
    config.save_to_file(config_path)
    return config
