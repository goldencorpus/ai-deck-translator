"""
Base translation service for AI Deck Translator.

This module provides a base implementation of the TranslationService interface
with common functionality shared between Google Slides and PowerPoint (PPTX)
translation services.
"""

import time
from abc import abstractmethod
from typing import Dict, List, Any, Optional, Tuple

from .translation_interface import (
    TranslationService,
    DocumentAdapter,
    TranslationRequest,
    TranslationResult,
    DocumentId,
    TextElements,
    MetadataType,
)
from .shared_utils import (
    perform_quality_check,
    apply_glossary_to_text,
    find_terms_in_text,
)


class BaseTranslationService(TranslationService):
    """
    Base implementation of the TranslationService interface.

    This class provides common functionality for translation services,
    such as document processing, quality checks, and glossary application.
    Concrete implementations must provide model-specific translation logic.
    """

    def __init__(
        self,
        supported_languages: Dict[str, str],
        supported_quality_levels: Dict[str, str],
    ):
        """
        Initialize the base translation service.

        Args:
            supported_languages: Dictionary of supported language codes to names
            supported_quality_levels: Dictionary of supported quality level codes to descriptions
        """
        self._supported_languages = supported_languages
        self._supported_quality_levels = supported_quality_levels

    def get_supported_languages(self) -> Dict[str, str]:
        """
        Get the languages supported by this translation service.

        Returns:
            Dict[str, str]: Dictionary of language codes to language names
        """
        return self._supported_languages

    def get_supported_quality_levels(self) -> Dict[str, str]:
        """
        Get the quality levels supported by this translation service.

        Returns:
            Dict[str, str]: Dictionary of quality level codes to descriptions
        """
        return self._supported_quality_levels

    def translate_document(
        self, document_id: DocumentId, adapter: DocumentAdapter, request_params: dict
    ) -> TranslationResult:
        """
        Translate an entire document using the provided adapter.

        Args:
            document_id: Identifier for the document
            adapter: Document adapter for the specific document type
            request_params: Parameters for the translation request

        Returns:
            TranslationResult: Results of the translation operation
        """
        start_time = time.time()

        try:
            # Extract text from document
            text_elements, metadata = adapter.extract_text(document_id)

            # Create translation request
            request = TranslationRequest(
                text_elements=text_elements, metadata=metadata, **request_params
            )

            # Translate text elements
            translation_result = self.translate_elements(request)

            # Update document with translated text
            new_document_id = adapter.update_document(
                document_id,
                translation_result.translated_elements,
                request.target_language,
            )

            # Calculate execution time
            execution_time = time.time() - start_time

            # Return success result
            return TranslationResult(
                translated_elements=translation_result.translated_elements,
                execution_time=execution_time,
                cost=translation_result.cost,
                success=True,
                new_document_id=new_document_id,
            )

        except Exception as e:
            # Calculate execution time
            execution_time = time.time() - start_time

            # Return error result
            return TranslationResult(
                translated_elements={},
                execution_time=execution_time,
                cost={},
                success=False,
                error=str(e),
            )

    def translate_elements(self, request: TranslationRequest) -> TranslationResult:
        """
        Translate text elements according to the request parameters.

        This is the main entry point for translation that handles quality checks,
        glossary application, and cost tracking.

        Args:
            request: A TranslationRequest object containing all translation parameters

        Returns:
            TranslationResult: Results of the translation operation
        """
        start_time = time.time()

        try:
            # Initialize cost tracker
            cost_data = {"total_cost": 0.0, "call_count": 0, "models": {}}

            # Process translation batches
            translated_elements = {}

            # Apply model-specific translation
            # This calls the concrete implementation's method
            translated_elements, batch_costs = self._translate_text_elements(
                request.text_elements,
                request.metadata,
                request.source_language,
                request.target_language,
                request.quality_level,
                request.use_cache,
                request.use_qa,
                request.use_glossary,
                request.batch_size,
                request.max_workers,
                request.api_key,
            )

            # Update costs
            for model, cost in batch_costs.items():
                if model not in cost_data["models"]:
                    cost_data["models"][model] = {
                        "cost": 0.0,
                        "calls": 0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                    }

                cost_data["models"][model]["cost"] += cost["cost"]
                cost_data["models"][model]["calls"] += cost["calls"]
                cost_data["models"][model]["input_tokens"] += cost.get(
                    "input_tokens", 0
                )
                cost_data["models"][model]["output_tokens"] += cost.get(
                    "output_tokens", 0
                )

                cost_data["total_cost"] += cost["cost"]
                cost_data["call_count"] += cost["calls"]

            # Calculate execution time
            execution_time = time.time() - start_time

            return TranslationResult(
                translated_elements=translated_elements,
                execution_time=execution_time,
                cost=cost_data,
                success=True,
            )

        except Exception as e:
            # Calculate execution time
            execution_time = time.time() - start_time

            return TranslationResult(
                translated_elements={},
                execution_time=execution_time,
                cost={},
                success=False,
                error=str(e),
            )

    @abstractmethod
    def _translate_text_elements(
        self,
        text_elements: TextElements,
        metadata: MetadataType,
        source_language: str,
        target_language: str,
        quality_level: str,
        use_cache: bool,
        use_qa: bool,
        use_glossary: bool,
        batch_size: int,
        max_workers: int,
        api_key: Optional[str],
    ) -> Tuple[TextElements, Dict[str, Dict[str, Any]]]:
        """
        Translate text elements using the appropriate model(s).

        This method must be implemented by concrete subclasses to provide
        model-specific translation logic.

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
        pass

    def _perform_quality_checks(
        self,
        original_text: str,
        translated_text: str,
        source_language: str,
        target_language: str,
    ) -> Tuple[float, List[str]]:
        """
        Perform quality checks on a translation.

        Args:
            original_text: Original source text
            translated_text: Translated text
            source_language: Source language code
            target_language: Target language code

        Returns:
            Tuple[float, List[str]]: Quality score and list of issues
        """
        return perform_quality_check(
            original_text, translated_text, source_language, target_language
        )

    def _apply_glossary(
        self,
        original_text: str,
        translated_text: str,
        source_language: str,
        target_language: str,
    ) -> str:
        """
        Apply glossary terms to a translation.

        Args:
            original_text: Original source text
            translated_text: Translated text
            source_language: Source language code
            target_language: Target language code

        Returns:
            str: Updated translation with glossary terms applied
        """
        return apply_glossary_to_text(
            original_text, source_language, target_language, translated_text
        )
