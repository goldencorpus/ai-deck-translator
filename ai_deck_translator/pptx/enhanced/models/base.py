"""
Base class and interfaces for translation models.
"""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

# Model constants imported from the enhanced translator
MODEL_CLAUDE_35_SONNET = "claude-sonnet-4-6"
MODEL_CLAUDE_35_HAIKU = "claude-haiku-4-5"
MODEL_GPT_4O = "gpt-4o"
MODEL_GPT_4O_MINI = "gpt-4o-mini"
MODEL_GEMINI_15_PRO = "gemini-1.5-pro"
MODEL_GEMINI_15_FLASH = "gemini-1.5-flash"


@dataclass
class ModelResponse:
    """Container for standardized model responses"""

    translated_content: Dict[str, str]
    prompt_tokens: int
    completion_tokens: int
    model: str
    cost: float = 0.0
    raw_response: Any = None


class TranslationModel(ABC):
    """Base class for translation model implementations"""

    def __init__(self, api_key: Optional[str] = None, max_retries: int = 3):
        """
        Initialize the translation model.

        Args:
            api_key: API key for the service (optional)
            max_retries: Maximum number of retries for API calls
        """
        self.api_key = api_key
        self.max_retries = max_retries

    @abstractmethod
    def translate(
        self,
        content_to_translate: Dict[str, str],
        context_info: Dict[str, Any],
        source_language: str,
        target_language: str,
    ) -> ModelResponse:
        """
        Translate content using this model.

        Args:
            content_to_translate: Dictionary of content to translate
            context_info: Dictionary of context information
            source_language: Source language code
            target_language: Target language code

        Returns:
            ModelResponse: Standardized response with translation results
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Get the name of this model"""
        pass

    @abstractmethod
    def generate_prompts(
        self,
        source_language: str,
        target_language: str,
        content_to_translate: Dict[str, str],
        context_info: Dict[str, Any],
    ) -> tuple:
        """
        Generate model-specific prompts.

        Args:
            source_language: Source language code
            target_language: Target language code
            content_to_translate: Dictionary of content to translate
            context_info: Dictionary of context information

        Returns:
            tuple: (system_prompt, user_prompt) for the model
        """
        pass


def get_translator_for_model(
    model: str, api_key: Optional[str] = None, max_retries: int = 3
) -> TranslationModel:
    """
    Factory function to get the appropriate translator for a model.

    Args:
        model: Model identifier
        api_key: API key for the service (optional)
        max_retries: Maximum number of retries for API calls

    Returns:
        TranslationModel: Appropriate translator instance
    """
    from .anthropic import AnthropicTranslator
    from .gemini import GeminiTranslator
    from .openai import OpenAITranslator

    # Determine the appropriate translator based on the model
    if model.startswith("claude"):
        return AnthropicTranslator(
            model, api_key or os.environ.get("CLAUDE_API_KEY"), max_retries
        )
    elif model.startswith("gpt"):
        return OpenAITranslator(
            model, api_key or os.environ.get("OPENAI_API_KEY"), max_retries
        )
    elif model.startswith("gemini"):
        return GeminiTranslator(
            model, api_key or os.environ.get("GOOGLE_AI_API_KEY"), max_retries
        )
    else:
        raise ValueError(f"Unsupported model: {model}")
