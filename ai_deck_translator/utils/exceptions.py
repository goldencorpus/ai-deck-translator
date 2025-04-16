"""
Custom exceptions for the AI Deck Translator.

This module defines custom exceptions used throughout the AI Deck Translator
to provide clear error messages and enable proper error handling. Each exception
type corresponds to a specific category of errors that might occur during the
translation process.

Usage:
    try:
        # Some operation that might fail
        result = some_function()
    except AuthenticationError as e:
        # Handle authentication errors
        print(f"Authentication failed: {e}")
    except NetworkError as e:
        # Handle network errors
        print(f"Network error: {e}")
"""


class AIDeckTranslatorError(Exception):
    """
    Base exception for all AI Deck Translator errors.
    
    All other exceptions in this module inherit from this base class,
    allowing for catch-all error handling when needed.
    
    Attributes:
        message (str): The error message
    """
    def __init__(self, message="An error occurred in AI Deck Translator"):
        self.message = message
        super().__init__(self.message)


class AuthenticationError(AIDeckTranslatorError):
    """
    Exception raised for authentication failures.
    
    This exception is raised when authentication with Google or other services fails,
    such as invalid credentials, missing token files, or expired tokens.
    
    Examples:
        - OAuth flow failures
        - Invalid API keys
        - Expired credentials
        - Missing token files
    """
    def __init__(self, message="Authentication failed"):
        super().__init__(message)


class APIError(AIDeckTranslatorError):
    """
    Exception raised for API-related errors.
    
    This exception is raised when there are issues with API calls that are not
    related to authentication or network connectivity.
    
    Examples:
        - Rate limiting
        - Invalid API parameters
        - API version mismatches
        - Unsupported API features
    """
    def __init__(self, message="API error occurred"):
        super().__init__(message)


class RateLimitError(APIError):
    """
    Exception raised when API rate limits are exceeded.
    
    This exception is raised when an API request is rejected due to
    rate limiting or quota restrictions.
    
    Examples:
        - Too many requests in a time period
        - API quota exceeded
        - API usage limits reached
    """
    def __init__(self, message="API rate limit exceeded", retry_after=None):
        self.retry_after = retry_after
        super().__init__(message)


class TranslationError(AIDeckTranslatorError):
    """
    Exception raised for translation failures.
    
    This exception is raised when the translation process fails, such as
    issues with the translation API, invalid language codes, or content
    that cannot be translated.
    
    Examples:
        - Translation API failures
        - Invalid language codes
        - Content too large for translation
        - Malformed translation responses
    """
    def __init__(self, message="Translation failed"):
        super().__init__(message)


class PresentationError(AIDeckTranslatorError):
    """
    Exception raised for errors related to presentation manipulation.
    
    This exception is raised when there are issues with accessing, modifying,
    or creating presentations.
    
    Examples:
        - Presentation not found
        - Permission issues
        - Invalid presentation structure
        - Errors updating presentation content
    """
    def __init__(self, message="Presentation operation failed"):
        super().__init__(message)


class ConfigurationError(AIDeckTranslatorError):
    """
    Exception raised for configuration errors.
    
    This exception is raised when there are issues with the application
    configuration, such as missing required settings or invalid values.
    
    Examples:
        - Missing required environment variables
        - Invalid configuration values
        - Configuration file not found
        - Incompatible configuration settings
    """
    def __init__(self, message="Configuration error"):
        super().__init__(message)


class NetworkError(AIDeckTranslatorError):
    """
    Exception raised for network-related errors.
    
    This exception is raised when there are issues with network connectivity
    or HTTP requests.
    
    Examples:
        - Connection timeouts
        - DNS resolution failures
        - HTTP errors (4xx, 5xx)
        - SSL/TLS errors
    """
    def __init__(self, message="Network error occurred"):
        super().__init__(message)


class ValidationError(AIDeckTranslatorError):
    """
    Exception raised for input validation errors.
    
    This exception is raised when user input or function parameters
    fail validation checks.
    
    Examples:
        - Invalid presentation ID format
        - Unsupported language codes
        - Missing required parameters
        - Invalid file formats
    """
    def __init__(self, message="Validation failed"):
        super().__init__(message)


class RecoveryError(AIDeckTranslatorError):
    """
    Exception raised for recovery operation failures.
    
    This exception is raised when there are issues with the translation
    recovery system, such as corrupted recovery files or incompatible
    recovery data.
    
    Examples:
        - Recovery file not found
        - Corrupted recovery data
        - Incompatible recovery file version
        - Failed to save recovery state
    """
    def __init__(self, message="Recovery operation failed"):
        super().__init__(message) 