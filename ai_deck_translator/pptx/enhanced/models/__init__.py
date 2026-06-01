"""
Model implementations for the enhanced PPTX translator.
"""

from .anthropic import AnthropicTranslator

# Export model factory function
from .base import ModelResponse, TranslationModel, get_translator_for_model
from .gemini import GeminiTranslator
from .openai import OpenAITranslator

__all__ = [
    "TranslationModel",
    "ModelResponse",
    "AnthropicTranslator",
    "OpenAITranslator",
    "GeminiTranslator",
    "get_translator_for_model",
]
