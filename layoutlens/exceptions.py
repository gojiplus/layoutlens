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

    Args:
        message: Human-readable description of the error.
        details: Optional dictionary containing additional error context.

    Attributes:
        message: The error message string.
        details: Dictionary of additional error context information.
    """

    def __init__(self, message: str, details: dict = None):
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
        logger.error(f"{self.__class__.__name__}: {message}", extra={"details": self.details})

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


class APIError(LayoutLensError):
    """Exception raised when there's an issue with AI provider APIs.

    Covers general API communication errors, including network issues,
    malformed responses, and server errors.

    Args:
        message: Description of the API error.
        status_code: HTTP status code from the API response.
        response: Raw response content from the API.

    Attributes:
        status_code: HTTP status code if available.
        response: Raw API response content if available.
    """

    def __init__(self, message: str, status_code: int = None, response: str = None):
        """Initialize API error with response details.

        Args:
            message: Description of the API error.
            status_code: HTTP status code from the API response.
            response: Raw response content from the API.
        """
        super().__init__(message)
        self.status_code = status_code
        self.response = response
        self.details = {"status_code": status_code, "response": response}


class ScreenshotError(LayoutLensError):
    """Exception raised when screenshot capture fails.

    Occurs when Playwright fails to capture screenshots due to browser issues,
    network problems, invalid URLs, or viewport configuration problems.

    Args:
        message: Description of the screenshot capture failure.
        source: URL or file path being captured.
        viewport: Viewport configuration used during capture.

    Attributes:
        source: The source URL or file path.
        viewport: The viewport configuration string.
    """

    def __init__(self, message: str, source: str = None, viewport: str = None):
        """Initialize screenshot error with capture context.

        Args:
            message: Description of the screenshot capture failure.
            source: URL or file path being captured.
            viewport: Viewport configuration used during capture.
        """
        super().__init__(message)
        self.source = source
        self.viewport = viewport
        self.details = {"source": source, "viewport": viewport}


class ConfigurationError(LayoutLensError):
    """Exception raised when there's a configuration issue.

    Covers invalid configuration files, missing required settings,
    malformed YAML, and incompatible configuration values.

    Args:
        message: Description of the configuration problem.
        config_file: Path to the configuration file with issues.
        missing_fields: List of required fields that are missing.

    Attributes:
        config_file: Path to the problematic configuration file.
        missing_fields: List of missing required configuration fields.
    """

    def __init__(self, message: str, config_file: str = None, missing_fields: list = None):
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

    Args:
        message: Description of the validation failure.
        field: Name of the field that failed validation.
        value: The invalid value that was provided.

    Attributes:
        field: The field name that failed validation.
        value: The invalid value that was rejected.
    """

    def __init__(self, message: str, field: str = None, value: str = None):
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

    Args:
        message: Description of the analysis failure.
        query: The query that was being processed.
        source: URL or file path being analyzed.
        confidence: Confidence score if partial analysis occurred.

    Attributes:
        query: The analysis query that failed.
        source: The source being analyzed.
        confidence: Confidence score (0.0 for failed analyses).
    """

    def __init__(
        self,
        message: str,
        query: str = None,
        source: str = None,
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


class TestSuiteError(LayoutLensError):
    """Exception raised when test suite execution fails.

    Covers test suite loading failures, execution errors, and
    problems with test case definitions or execution.

    Args:
        message: Description of the test suite failure.
        suite_name: Name of the test suite that failed.
        test_case: Name of the specific test case that failed.

    Attributes:
        suite_name: Name of the failed test suite.
        test_case: Name of the specific failed test case if applicable.
    """

    def __init__(self, message: str, suite_name: str = None, test_case: str = None):
        """Initialize test suite error with execution context.

        Args:
            message: Description of the test suite failure.
            suite_name: Name of the test suite that failed.
            test_case: Name of the specific test case that failed.
        """
        super().__init__(message)
        self.suite_name = suite_name
        self.test_case = test_case
        self.details = {"suite_name": suite_name, "test_case": test_case}


class AuthenticationError(APIError):
    """Exception raised when API authentication fails.

    Specific type of APIError for authentication issues, including
    invalid API keys, expired tokens, and permission problems.

    Args:
        message: Description of the authentication failure.
    """

    def __init__(self, message: str = "Invalid or missing API key"):
        """Initialize authentication error.

        Args:
            message: Description of the authentication failure.
        """
        super().__init__(message)


class RateLimitError(APIError):
    """Exception raised when API rate limit is exceeded.

    Specific type of APIError for rate limiting scenarios, including
    information about when to retry the request.

    Args:
        message: Description of the rate limit issue.
        retry_after: Seconds to wait before retrying.

    Attributes:
        retry_after: Number of seconds to wait before retry.
    """

    def __init__(self, message: str = "API rate limit exceeded", retry_after: int = None):
        """Initialize rate limit error with retry information.

        Args:
            message: Description of the rate limit issue.
            retry_after: Seconds to wait before retrying.
        """
        super().__init__(message)
        self.retry_after = retry_after
        self.details["retry_after"] = retry_after


class TimeoutError(LayoutLensError):
    """Exception raised when an operation times out.

    Occurs when operations exceed configured time limits, including
    screenshot capture, API calls, and analysis processing.

    Args:
        message: Description of the timeout.
        timeout_duration: Duration in seconds that was exceeded.
        operation: Name of the operation that timed out.

    Attributes:
        timeout_duration: The timeout duration that was exceeded.
        operation: The specific operation that timed out.
    """

    def __init__(self, message: str, timeout_duration: float = None, operation: str = None):
        """Initialize timeout error with operation context.

        Args:
            message: Description of the timeout.
            timeout_duration: Duration in seconds that was exceeded.
            operation: Name of the operation that timed out.
        """
        super().__init__(message)
        self.timeout_duration = timeout_duration
        self.operation = operation
        self.details = {"timeout_duration": timeout_duration, "operation": operation}


class LayoutFileNotFoundError(LayoutLensError):
    """Exception raised when a required file is not found.

    Occurs when attempting to access screenshots, HTML files, configuration
    files, or other required resources that don't exist.

    Args:
        message: Description of the missing file error.
        file_path: Path to the file that was not found.

    Attributes:
        file_path: The path to the missing file.
    """

    def __init__(self, message: str, file_path: str = None):
        """Initialize file not found error with path context.

        Args:
            message: Description of the missing file error.
            file_path: Path to the file that was not found.
        """
        super().__init__(message)
        self.file_path = file_path
        self.details = {"file_path": file_path}


class NetworkError(LayoutLensError):
    """Exception raised when there's a network connectivity issue.

    Covers DNS resolution failures, connection timeouts, unreachable
    hosts, and other network-related problems.

    Args:
        message: Description of the network issue.
        url: URL that couldn't be reached.
        error_code: Network error code if available.

    Attributes:
        url: The URL that couldn't be accessed.
        error_code: Network error code if available.
    """

    def __init__(self, message: str, url: str = None, error_code: int = None):
        """Initialize network error with connection context.

        Args:
            message: Description of the network issue.
            url: URL that couldn't be reached.
            error_code: Network error code if available.
        """
        super().__init__(message)
        self.url = url
        self.error_code = error_code
        self.details = {"url": url, "error_code": error_code}


# Exception mapping for common error scenarios
ERROR_MAPPING = {
    "401": AuthenticationError,
    "403": AuthenticationError,
    "429": RateLimitError,
    "timeout": TimeoutError,
    "network": NetworkError,
    "file_not_found": LayoutFileNotFoundError,
    "validation": ValidationError,
    "screenshot": ScreenshotError,
    "analysis": AnalysisError,
    "config": ConfigurationError,
    "test_suite": TestSuiteError,
}


def handle_api_error(response_code: int, message: str, response: str = None) -> APIError:
    """Factory function to create appropriate API error based on HTTP response code.

    Maps HTTP status codes to specific exception types for better error handling
    and user experience.

    Args:
        response_code: HTTP status code from the API response.
        message: Error message to include in the exception.
        response: Raw response content from the API.

    Returns:
        Appropriate APIError subclass based on the response code.
    """
    if response_code == 401:
        return AuthenticationError("Invalid API key")
    elif response_code == 403:
        return AuthenticationError("API key does not have required permissions")
    elif response_code == 429:
        return RateLimitError("API rate limit exceeded")
    else:
        return APIError(message, status_code=response_code, response=response)


def wrap_exception(original_exception: Exception, context: str = None) -> LayoutLensError:
    """Wrap a generic exception in an appropriate LayoutLens exception.

    Converts standard Python exceptions into LayoutLens-specific exceptions
    for consistent error handling across the framework.

    Args:
        original_exception: The original exception to wrap.
        context: Optional context description for the error.

    Returns:
        Appropriate LayoutLensError subclass wrapping the original exception.
    """
    logger = get_logger("exceptions")
    message = str(original_exception)

    if context:
        message = f"{context}: {message}"

    logger.debug(f"Wrapping exception: {type(original_exception).__name__} -> {message}")

    # Map common exception types
    if isinstance(original_exception, ConnectionError | OSError):
        return NetworkError(message)
    elif isinstance(original_exception, TimeoutError):
        return TimeoutError(message)
    elif isinstance(original_exception, FileNotFoundError):
        return LayoutFileNotFoundError(message, file_path=getattr(original_exception, "filename", None))
    else:
        return LayoutLensError(message)
