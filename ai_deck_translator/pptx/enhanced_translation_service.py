"""
Enhanced PPTX translation service.

This module provides an implementation of the TranslationService interface
specifically for PowerPoint (PPTX) files, utilizing multiple AI models for
optimal quality and cost efficiency.
"""

import os
import time
import concurrent.futures
from typing import Dict, List, Any, Optional, Tuple

from ..core.base_translation_service import BaseTranslationService
from ..core.translation_interface import TextElements, MetadataType
from ..pptx.enhanced.models import get_translator_for_model
from ..pptx.enhanced.models.base import (
    MODEL_CLAUDE_3_HAIKU,
    MODEL_CLAUDE_3_SONNET,
    MODEL_GPT_3_5_TURBO,
    MODEL_GPT_4_TURBO,
    MODEL_GEMINI_PRO,
)
from ..pptx.enhanced.cache import get_from_translation_cache, save_to_translation_cache

# Supported language codes
SUPPORTED_LANGUAGES = {
    "en": "English",
    "ja": "Japanese",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "ko": "Korean",
    "zh": "Chinese",
    "pt": "Portuguese",
    "ru": "Russian",
    "ar": "Arabic",
    "nl": "Dutch",
    "tr": "Turkish",
    "hi": "Hindi",
    "th": "Thai",
}

# Quality level constants
QUALITY_DRAFT = "draft"
QUALITY_STANDARD = "standard"
QUALITY_PROFESSIONAL = "professional"
QUALITY_ECONOMY = "economy"

# Quality levels and their corresponding models
QUALITY_LEVELS = {
    QUALITY_DRAFT: [MODEL_CLAUDE_3_HAIKU, MODEL_GPT_3_5_TURBO, MODEL_GEMINI_PRO],
    QUALITY_STANDARD: [MODEL_CLAUDE_3_HAIKU, MODEL_GPT_3_5_TURBO, MODEL_GEMINI_PRO],
    QUALITY_PROFESSIONAL: [MODEL_CLAUDE_3_SONNET, MODEL_GPT_4_TURBO, MODEL_GEMINI_PRO],
    QUALITY_ECONOMY: [MODEL_GEMINI_PRO],  # Fallback to most economical model
}

# Description of quality levels for user interface
QUALITY_DESCRIPTIONS = {
    QUALITY_DRAFT: "Quick translations suitable for understanding content (most economical)",
    QUALITY_STANDARD: "Balanced quality and cost for general purpose translations",
    QUALITY_PROFESSIONAL: "High-quality translations for important presentations and content",
    QUALITY_ECONOMY: "Most cost-effective option using simplified models",
}


class EnhancedPPTXTranslationService(BaseTranslationService):
    """
    Enhanced translation service for PowerPoint (PPTX) files.

    This service utilizes multiple AI models for translation with advanced
    quality checks, glossary application, and cost tracking.
    """

    def __init__(self):
        """Initialize the enhanced PPTX translation service."""
        super().__init__(
            supported_languages=SUPPORTED_LANGUAGES,
            supported_quality_levels=QUALITY_DESCRIPTIONS,
        )

    def _translate_text_elements(
        self,
        text_elements: TextElements,
        metadata: MetadataType,
        source_language: str,
        target_language: str,
        quality_level: str = QUALITY_STANDARD,
        use_cache: bool = True,
        use_qa: bool = True,
        use_glossary: bool = True,
        batch_size: int = 5,
        max_workers: int = 4,
        api_key: Optional[str] = None,
    ) -> Tuple[TextElements, Dict[str, Dict[str, Any]]]:
        """
        Translate text elements from PowerPoint using the appropriate model(s).

        Args:
            text_elements: Dictionary of text elements to translate
            metadata: Metadata about the document
            source_language: Source language code
            target_language: Target language code
            quality_level: Quality level code
            use_cache: Whether to use the translation cache
            use_qa: Whether to perform quality assurance
            use_glossary: Whether to apply glossary terms
            batch_size: Number of elements per batch
            max_workers: Maximum number of parallel workers
            api_key: API key for the model provider

        Returns:
            Tuple[TextElements, Dict[str, Dict[str, Any]]]: Translated elements and cost data by model
        """
        # Initialize cost tracking
        cost_data = {}

        # Check if we have any text to translate
        if not text_elements:
            return {}, cost_data

        # Process from cache first
        translated_elements = {}
        remaining_elements = {}

        if use_cache:
            for element_id, text in text_elements.items():
                cached_translation = get_from_translation_cache(
                    text, source_language, target_language
                )
                if cached_translation:
                    translated_elements[element_id] = cached_translation
                else:
                    remaining_elements[element_id] = text
        else:
            remaining_elements = text_elements.copy()

        # If all elements were found in cache, return early
        if not remaining_elements:
            return translated_elements, cost_data

        # Create batches for translation
        batches = []
        batch = {}
        batch_chars = 0

        for element_id, text in remaining_elements.items():
            # Start a new batch if current one is full
            text_length = len(text)
            if len(batch) >= batch_size or batch_chars + text_length > 4000:
                if batch:
                    batches.append(batch)
                batch = {}
                batch_chars = 0

            # Add to current batch
            batch[element_id] = text
            batch_chars += text_length

        # Add the last batch if not empty
        if batch:
            batches.append(batch)

        # Get models for the selected quality level
        models = QUALITY_LEVELS.get(quality_level, QUALITY_LEVELS[QUALITY_STANDARD])
        selected_model = models[0]  # Default to first model

        # Initialize translator
        translator = get_translator_for_model(selected_model, api_key)

        # Translate batches in parallel
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(max_workers, len(batches))
        ) as executor:
            # Create arguments for each batch
            batch_args = [
                (
                    batch,
                    batch_index,
                    metadata,
                    source_language,
                    target_language,
                    selected_model,
                    use_qa,
                    use_glossary,
                    api_key,
                )
                for batch_index, batch in enumerate(batches)
            ]

            # Submit translation tasks
            future_to_batch = {
                executor.submit(self._translate_batch, *args): batch_index
                for batch_index, args in enumerate(batch_args)
            }

            # Process results as they come in
            for future in concurrent.futures.as_completed(future_to_batch):
                batch_index = future_to_batch[future]

                try:
                    batch_translations, batch_cost = future.result()

                    # Update translations
                    for element_id, translation in batch_translations.items():
                        translated_elements[element_id] = translation

                        # Save to cache if needed
                        if use_cache:
                            save_to_translation_cache(
                                remaining_elements[element_id],
                                translation,
                                source_language,
                                target_language,
                                selected_model,
                            )

                    # Update cost data
                    model_name = selected_model
                    if model_name not in cost_data:
                        cost_data[model_name] = {
                            "cost": 0.0,
                            "calls": 0,
                            "input_tokens": 0,
                            "output_tokens": 0,
                        }

                    cost_data[model_name]["cost"] += batch_cost["cost"]
                    cost_data[model_name]["calls"] += batch_cost["calls"]
                    cost_data[model_name]["input_tokens"] += batch_cost["input_tokens"]
                    cost_data[model_name]["output_tokens"] += batch_cost[
                        "output_tokens"
                    ]

                except Exception as e:
                    # Log error and continue with other batches
                    print(f"Error processing batch {batch_index}: {str(e)}")

                    # For failed batches, copy original text as fallback
                    batch = batches[batch_index]
                    for element_id, text in batch.items():
                        if element_id not in translated_elements:
                            translated_elements[element_id] = text

        return translated_elements, cost_data

    def _translate_batch(
        self,
        batch: Dict[str, str],
        batch_index: int,
        metadata: MetadataType,
        source_language: str,
        target_language: str,
        model_name: str,
        use_qa: bool,
        use_glossary: bool,
        api_key: Optional[str] = None,
    ) -> Tuple[Dict[str, str], Dict[str, Any]]:
        """
        Translate a batch of text using the specified model.

        Args:
            batch: Dictionary of text to translate
            batch_index: Index of the current batch
            metadata: Metadata about the document
            source_language: Source language code
            target_language: Target language code
            model_name: Model identifier
            use_qa: Whether to perform quality assurance
            use_glossary: Whether to apply glossary terms
            api_key: API key for the model provider

        Returns:
            Tuple[Dict[str, str], Dict[str, Any]]: Translated batch and cost data
        """
        # Prepare context for translation
        context_items = []

        for element_id in batch.keys():
            # Extract slide number from element ID
            if element_id.startswith("slide_"):
                slide_num = int(element_id.split("_")[1])

                # Find corresponding slide metadata
                for slide in metadata:
                    if slide.get("slide_number") == slide_num:
                        context_items.append(
                            f"Slide {slide_num}: {slide.get('title', '')}"
                        )
                        break

        # Prepare content for API
        content_json = [
            {"index": i, "id": element_id, "text": text, "type": "text"}
            for i, (element_id, text) in enumerate(batch.items())
        ]

        # Create a cost tracker object
        class CostTracker:
            def __init__(self):
                self.input_tokens = 0
                self.output_tokens = 0
                self.cost = 0.0
                self.calls = 0

            def add_cost(self, input_tokens, output_tokens, cost):
                self.input_tokens += input_tokens
                self.output_tokens += output_tokens
                self.cost += cost
                self.calls += 1

            def get_summary(self):
                return {
                    "cost": self.cost,
                    "calls": self.calls,
                    "input_tokens": self.input_tokens,
                    "output_tokens": self.output_tokens,
                }

        cost_tracker = CostTracker()

        # Initialize translator
        translator = get_translator_for_model(model_name, api_key)

        # Generate prompts
        system_prompt, user_prompt = translator.generate_prompts(
            content_json, source_language, target_language, context_items
        )

        # Call the model
        result = translator.translate(system_prompt, user_prompt, cost_tracker)

        # Extract results
        translations = {}
        for item in result.content:
            if "index" in item and "id" in item and "translation" in item:
                element_id = item["id"]
                translation = item["translation"]

                # Perform quality checks if needed
                if use_qa:
                    original_text = batch[element_id]
                    quality_score, issues = self._perform_quality_checks(
                        original_text, translation, source_language, target_language
                    )

                    # If there are issues and quality is poor, try to fix
                    if issues and quality_score < 70:
                        fixed_translation = self._fix_translation_issues(
                            original_text,
                            translation,
                            issues,
                            model_name,
                            source_language,
                            target_language,
                            api_key,
                        )
                        if fixed_translation:
                            translation = fixed_translation

                # Apply glossary if needed
                if use_glossary and element_id in batch:
                    translation = self._apply_glossary(
                        batch[element_id], translation, source_language, target_language
                    )

                # Add to results
                translations[element_id] = translation

        return translations, cost_tracker.get_summary()

    def _fix_translation_issues(
        self,
        original_text: str,
        translation: str,
        issues: List[str],
        model_name: str,
        source_language: str,
        target_language: str,
        api_key: Optional[str] = None,
    ) -> Optional[str]:
        """
        Fix issues in a translation using the translation model.

        Args:
            original_text: Original source text
            translation: Translation with issues
            issues: List of identified issues
            model_name: Model identifier
            source_language: Source language code
            target_language: Target language code
            api_key: API key for the model provider

        Returns:
            Optional[str]: Fixed translation or None if unsuccessful
        """
        # Initialize translator
        translator = get_translator_for_model(model_name, api_key)

        # Extract missing technical terms if any
        missing_terms = []
        for issue in issues:
            if issue.startswith("Missing technical terms:"):
                terms_str = issue.replace("Missing technical terms:", "").strip()
                missing_terms = [term.strip() for term in terms_str.split(",")]

        # Create system prompt for fixing issues
        system_prompt = f"""You are a professional translator specializing in {SUPPORTED_LANGUAGES.get(source_language, source_language)} to {SUPPORTED_LANGUAGES.get(target_language, target_language)} translation.

Your task is to fix issues in a translation. Here are the specific problems that need to be addressed:
{chr(10).join(f"- {issue}" for issue in issues)}

The following technical terms should be preserved in the translation: {', '.join(missing_terms) if missing_terms else 'N/A'}

Please provide ONLY the corrected translation, maintaining the meaning and style of the original text while fixing the identified issues."""

        # Create user prompt with original text and current translation
        user_prompt = f"""Original text ({SUPPORTED_LANGUAGES.get(source_language, source_language)}):
{original_text}

Current translation with issues ({SUPPORTED_LANGUAGES.get(target_language, target_language)}):
{translation}

Please fix the issues and provide the corrected translation, maintaining the original formatting and style."""

        # Create a simple cost tracker that doesn't actually track costs
        # since this is a one-off fix
        class DummyCostTracker:
            def add_cost(self, *args, **kwargs):
                pass

        # Call the model
        try:
            result = translator.translate(
                system_prompt, user_prompt, DummyCostTracker()
            )

            # Extract the fixed translation
            if hasattr(result, "content") and isinstance(result.content, str):
                return result.content
            elif (
                hasattr(result, "content")
                and isinstance(result.content, list)
                and len(result.content) > 0
            ):
                if isinstance(result.content[0], str):
                    return result.content[0]
                elif (
                    isinstance(result.content[0], dict)
                    and "translation" in result.content[0]
                ):
                    return result.content[0]["translation"]

            return None
        except Exception:
            # If fixing fails, return the original translation
            return None
