"""Custom exception classes for LayoutLens."""


class LayoutLensError(Exception):
    """Base exception for all LayoutLens errors."""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self):
        base_str = self.message
        if self.details:
            details_str = ", ".join(f"{k}: {v}" for k, v in self.details.items())
            return f"{base_str} ({details_str})"
        return base_str


class APIError(LayoutLensError):
    """Raised when there's an issue with the OpenAI API."""
    
    def __init__(self, message: str, status_code: int = None, response: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response
        self.details = {
            "status_code": status_code,
            "response": response
        }


class ScreenshotError(LayoutLensError):
    """Raised when screenshot capture fails."""
    
    def __init__(self, message: str, source: str = None, viewport: str = None):
        super().__init__(message)
        self.source = source
        self.viewport = viewport
        self.details = {
            "source": source,
            "viewport": viewport
        }


class ConfigurationError(LayoutLensError):
    """Raised when there's a configuration issue."""
    
    def __init__(self, message: str, config_file: str = None, missing_fields: list = None):
        super().__init__(message)
        self.config_file = config_file
        self.missing_fields = missing_fields or []
        self.details = {
            "config_file": config_file,
            "missing_fields": missing_fields
        }


class ValidationError(LayoutLensError):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, field: str = None, value: str = None):
        super().__init__(message)
        self.field = field
        self.value = value
        self.details = {
            "field": field,
            "value": value
        }


class AnalysisError(LayoutLensError):
    """Raised when analysis fails."""
    
    def __init__(self, message: str, query: str = None, source: str = None, confidence: float = 0.0):
        super().__init__(message)
        self.query = query
        self.source = source
        self.confidence = confidence
        self.details = {
            "query": query,
            "source": source,
            "confidence": confidence
        }


class TestSuiteError(LayoutLensError):
    """Raised when test suite execution fails."""
    
    def __init__(self, message: str, suite_name: str = None, test_case: str = None):
        super().__init__(message)
        self.suite_name = suite_name
        self.test_case = test_case
        self.details = {
            "suite_name": suite_name,
            "test_case": test_case
        }


class AuthenticationError(LayoutLensError):
    """Raised when API authentication fails."""
    
    def __init__(self, message: str = "Invalid or missing API key"):
        super().__init__(message)


class RateLimitError(APIError):
    """Raised when API rate limit is exceeded."""
    
    def __init__(self, message: str = "API rate limit exceeded", retry_after: int = None):
        super().__init__(message)
        self.retry_after = retry_after
        self.details["retry_after"] = retry_after


class TimeoutError(LayoutLensError):
    """Raised when an operation times out."""
    
    def __init__(self, message: str, timeout_duration: float = None, operation: str = None):
        super().__init__(message)
        self.timeout_duration = timeout_duration
        self.operation = operation
        self.details = {
            "timeout_duration": timeout_duration,
            "operation": operation
        }


class LayoutFileNotFoundError(LayoutLensError):
    """Raised when a required file is not found."""
    
    def __init__(self, message: str, file_path: str = None):
        super().__init__(message)
        self.file_path = file_path
        self.details = {"file_path": file_path}


class NetworkError(LayoutLensError):
    """Raised when there's a network connectivity issue."""
    
    def __init__(self, message: str, url: str = None, error_code: int = None):
        super().__init__(message)
        self.url = url
        self.error_code = error_code
        self.details = {
            "url": url,
            "error_code": error_code
        }


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
    """Factory function to create appropriate API error based on response code."""
    if response_code == 401:
        return AuthenticationError("Invalid API key")
    elif response_code == 403:
        return AuthenticationError("API key does not have required permissions")
    elif response_code == 429:
        return RateLimitError("API rate limit exceeded")
    else:
        return APIError(message, status_code=response_code, response=response)


def wrap_exception(original_exception: Exception, context: str = None) -> LayoutLensError:
    """Wrap a generic exception in an appropriate LayoutLens exception."""
    message = str(original_exception)
    
    if context:
        message = f"{context}: {message}"
    
    # Map common exception types
    if isinstance(original_exception, (ConnectionError, OSError)):
        return NetworkError(message)
    elif isinstance(original_exception, TimeoutError):
        return TimeoutError(message)
    elif isinstance(original_exception, FileNotFoundError):
        return LayoutFileNotFoundError(message, file_path=getattr(original_exception, 'filename', None))
    else:
        return LayoutLensError(message)