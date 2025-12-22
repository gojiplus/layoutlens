"""Logging configuration and utilities for LayoutLens.

This module provides centralized logging configuration with support for
different environments, log levels, and output formats.
"""

import logging
import logging.handlers
import os
import re
from pathlib import Path
from typing import Any

# Default log format with structured information
DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEBUG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s() - %(message)s"
CONSOLE_FORMAT = "%(levelname)s: %(message)s"

# Log level mapping
LOG_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger instance for the given name.

    Parameters
    ----------
    name : str
        Logger name, typically the module name

    Returns
    -------
    logging.Logger
        Configured logger instance
    """
    logger = logging.getLogger(f"layoutlens.{name}")

    return logger


def setup_logging(
    level: str = "INFO",
    console: bool = True,
    file_path: str | None = None,
    file_level: str = "DEBUG",
    format_type: str = "default",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    **kwargs,
) -> None:
    """Configure logging for LayoutLens.

    Parameters
    ----------
    level : str, default "INFO"
        Console logging level
    console : bool, default True
        Whether to enable console logging
    file_path : str, optional
        Path to log file. If None, no file logging
    file_level : str, default "DEBUG"
        File logging level
    format_type : str, default "default"
        Format type: "default", "debug", "console"
    max_bytes : int, default 10MB
        Maximum log file size before rotation
    backup_count : int, default 5
        Number of backup log files to keep
    **kwargs
        Additional configuration options
    """
    # Get root logger for LayoutLens
    root_logger = logging.getLogger("layoutlens")
    root_logger.setLevel(logging.DEBUG)  # Set to lowest level, handlers will filter

    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Choose formatter
    if format_type == "debug":
        formatter = logging.Formatter(DEBUG_FORMAT)
    elif format_type == "console":
        formatter = logging.Formatter(CONSOLE_FORMAT)
    else:
        formatter = logging.Formatter(DEFAULT_FORMAT)

    # Console handler
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(LOG_LEVELS.get(level.upper(), logging.INFO))
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # File handler with rotation
    if file_path:
        # Ensure log directory exists
        log_file = Path(file_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            file_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setLevel(LOG_LEVELS.get(file_level.upper(), logging.DEBUG))
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def configure_from_env() -> None:
    """Configure logging based on environment variables.

    Environment Variables:
    - LAYOUTLENS_LOG_LEVEL: Console log level (default: INFO)
    - LAYOUTLENS_LOG_FILE: Log file path (optional)
    - LAYOUTLENS_LOG_FILE_LEVEL: File log level (default: DEBUG)
    - LAYOUTLENS_LOG_FORMAT: Format type (default: default)
    - LAYOUTLENS_LOG_DISABLE_CONSOLE: Set to "1" to disable console logging
    """
    setup_logging(
        level=os.getenv("LAYOUTLENS_LOG_LEVEL", "INFO"),
        console=os.getenv("LAYOUTLENS_LOG_DISABLE_CONSOLE", "0") != "1",
        file_path=os.getenv("LAYOUTLENS_LOG_FILE"),
        file_level=os.getenv("LAYOUTLENS_LOG_FILE_LEVEL", "DEBUG"),
        format_type=os.getenv("LAYOUTLENS_LOG_FORMAT", "default"),
    )


def configure_for_testing(level: str = "WARNING") -> None:
    """Configure minimal logging for testing environments.

    Parameters
    ----------
    level : str, default "WARNING"
        Minimum log level for test output
    """
    setup_logging(level=level, console=True, file_path=None, format_type="console")


def configure_for_development(output_dir: str | None = None) -> None:
    """Configure verbose logging for development.

    Parameters
    ----------
    output_dir : str, optional
        Directory for log files (default: ./logs)
    """
    if not output_dir:
        output_dir = "./logs"

    log_file = Path(output_dir) / "layoutlens.log"

    setup_logging(level="DEBUG", console=True, file_path=str(log_file), file_level="DEBUG", format_type="debug")


def configure_for_production(output_dir: str, level: str = "INFO") -> None:
    """Configure production logging with file rotation.

    Parameters
    ----------
    output_dir : str
        Directory for log files
    level : str, default "INFO"
        Console log level
    """
    log_file = Path(output_dir) / "layoutlens.log"

    setup_logging(
        level=level,
        console=False,  # No console output in production
        file_path=str(log_file),
        file_level="INFO",
        format_type="default",
        max_bytes=50 * 1024 * 1024,  # 50MB
        backup_count=10,
    )


def get_performance_logger() -> logging.Logger:
    """Get a logger specifically for performance metrics."""
    logger = logging.getLogger("layoutlens.performance")

    # Add performance-specific formatting if needed
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - PERF - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False  # Don't propagate to parent loggers

    return logger


def log_function_call(func_name: str, **kwargs) -> None:
    """Log function call with parameters (sanitized).

    Parameters
    ----------
    func_name : str
        Name of the function being called
    **kwargs
        Function parameters to log (will be sanitized)
    """
    logger = get_logger("api")

    # Sanitize kwargs
    safe_kwargs = {}
    for key, value in kwargs.items():
        if any(sensitive in key.lower() for sensitive in ["key", "token", "password", "secret"]):
            safe_kwargs[key] = "***REDACTED***"
        else:
            safe_kwargs[key] = str(value)[:100]  # Truncate long values

    logger.debug(f"Calling {func_name} with parameters: {safe_kwargs}")


def log_performance_metric(operation: str, duration: float, **metadata) -> None:
    """Log performance metrics.

    Parameters
    ----------
    operation : str
        Operation name
    duration : float
        Duration in seconds
    **metadata
        Additional metadata to include
    """
    perf_logger = get_performance_logger()

    metric_data = {"operation": operation, "duration_seconds": round(duration, 3), **metadata}

    perf_logger.info(f"Performance: {metric_data}")


# Initialize default logging configuration
def _initialize_default_logging():
    """Initialize default logging if not already configured."""
    logger = logging.getLogger("layoutlens")

    # Only configure if no handlers exist
    if not logger.handlers and not logger.parent.handlers:
        configure_from_env()


# Auto-initialize on import
_initialize_default_logging()
