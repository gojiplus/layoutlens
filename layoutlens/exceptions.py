"""Custom exception classes for LayoutLens with comprehensive error handling.

This module provides a hierarchy of custom exceptions for different error scenarios
that can occur during LayoutLens operations, including API errors, screenshot failures,
configuration issues, and analysis problems.
"""

from .logger import get_logger


class LayoutLensError(Exception):
    """Base exception class for all LayoutLens-specific errors.

    Provides common functionality for logging, error details storage, and
    string representation across all LayoutLens exceptions.

    Attributes:
        message: The error message string.
        details: Dictionary of additional error context information.
    """

    def __init__(self, message: str, details: dict | None = None):
        """Initialize the base LayoutLens exception.

        Args:
            message: Human-readable description of the error.
            details: Optional dictionary containing additional error context.
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

        # Log the exception when it's created
        logger = get_logger("exceptions")
        logger.error(
            f"{self.__class__.__name__}: {message}", extra={"details": self.details}
        )

    def __str__(self):
        """Return string representation of the exception.

        Returns:
            Formatted error message including details if present.
        """
        base_str = self.message
        if self.details:
            details_str = ", ".join(f"{k}: {v}" for k, v in self.details.items())
            return f"{base_str} ({details_str})"
        return base_str


class ConfigurationError(LayoutLensError):
    """Exception raised when there's a configuration issue.

    Covers invalid configuration files, missing required settings,
    malformed YAML, and incompatible configuration values.

    Attributes:
        config_file: Path to the problematic configuration file.
        missing_fields: List of missing required configuration fields.
    """

    def __init__(
        self,
        message: str,
        config_file: str | None = None,
        missing_fields: list | None = None,
    ):
        """Initialize configuration error with file context.

        Args:
            message: Description of the configuration problem.
            config_file: Path to the configuration file with issues.
            missing_fields: List of required fields that are missing.
        """
        super().__init__(message)
        self.config_file = config_file
        self.missing_fields = missing_fields or []
        self.details = {"config_file": config_file, "missing_fields": missing_fields}


class ValidationError(LayoutLensError):
    """Exception raised when input validation fails.

    Occurs when user-provided inputs don't meet requirements, such as
    empty queries, invalid URLs, or malformed parameters.

    Attributes:
        field: The field name that failed validation.
        value: The invalid value that was rejected.
    """

    def __init__(
        self, message: str, field: str | None = None, value: str | None = None
    ):
        """Initialize validation error with field context.

        Args:
            message: Description of the validation failure.
            field: Name of the field that failed validation.
            value: The invalid value that was provided.
        """
        super().__init__(message)
        self.field = field
        self.value = value
        self.details = {"field": field, "value": value}


class AnalysisError(LayoutLensError):
    """Exception raised when AI analysis fails.

    Occurs when the AI provider fails to analyze screenshots, returns
    malformed responses, or encounters processing errors.

    Attributes:
        query: The analysis query that failed.
        source: The source being analyzed.
        confidence: Confidence score (0.0 for failed analyses).
    """

    def __init__(
        self,
        message: str,
        query: str | None = None,
        source: str | None = None,
        confidence: float = 0.0,
    ):
        """Initialize analysis error with query context.

        Args:
            message: Description of the analysis failure.
            query: The query that was being processed.
            source: URL or file path being analyzed.
            confidence: Confidence score if partial analysis occurred.
        """
        super().__init__(message)
        self.query = query
        self.source = source
        self.confidence = confidence
        self.details = {"query": query, "source": source, "confidence": confidence}


class AuthenticationError(LayoutLensError):
    """Exception raised when API authentication fails.

    Covers invalid API keys, expired tokens, and permission problems.

    """

    def __init__(self, message: str = "Invalid or missing API key"):
        """Initialize authentication error.

        Args:
            message: Description of the authentication failure.
        """
        super().__init__(message)


class LayoutFileNotFoundError(LayoutLensError):
    """Exception raised when a required file is not found.

    Occurs when attempting to access screenshots, HTML files, configuration
    files, or other required resources that don't exist.

    Attributes:
        file_path: The path to the missing file.
    """

    def __init__(self, message: str, file_path: str | None = None):
        """Initialize file not found error with path context.

        Args:
            message: Description of the missing file error.
            file_path: Path to the file that was not found.
        """
        super().__init__(message)
        self.file_path = file_path
        self.details = {"file_path": file_path}
