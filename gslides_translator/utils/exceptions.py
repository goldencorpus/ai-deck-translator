"""
Custom exceptions for the Google Slides Translator.

This module defines custom exceptions used throughout the Google Slides Translator
to provide clear error messages and enable proper error handling.
"""


class GSlidesTranslatorError(Exception):
    """Base exception for all Google Slides Translator errors."""

    pass


class AuthenticationError(GSlidesTranslatorError):
    """Exception raised for authentication failures."""

    pass


class APIError(GSlidesTranslatorError):
    """Exception raised for API-related errors."""

    pass


class TranslationError(GSlidesTranslatorError):
    """Exception raised for translation failures."""

    pass


class PresentationError(GSlidesTranslatorError):
    """Exception raised for errors related to presentation manipulation."""

    pass


class ConfigurationError(GSlidesTranslatorError):
    """Exception raised for configuration errors."""

    pass


class NetworkError(GSlidesTranslatorError):
    """Exception raised for network-related errors."""

    pass


class ValidationError(GSlidesTranslatorError):
    """Exception raised for input validation errors."""

    pass


class RecoveryError(GSlidesTranslatorError):
    """Exception raised for recovery operation failures."""

    pass
