"""
Model implementations for the enhanced PPTX translator.
"""

from .base import TranslationModel, ModelResponse
from .anthropic import AnthropicTranslator
from .openai import OpenAITranslator
from .gemini import GeminiTranslator

# Export model factory function
from .base import get_translator_for_model

__all__ = [
    'TranslationModel',
    'ModelResponse',
    'AnthropicTranslator',
    'OpenAITranslator',
    'GeminiTranslator',
    'get_translator_for_model'
] 