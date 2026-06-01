"""
Translation interface for AI Deck Translator.

This module defines the common interfaces and abstractions for all translation services,
ensuring consistency between Google Slides and PowerPoint (PPTX) translations.

Key components:
- TranslationService: Abstract interface for translation services
- DocumentAdapter: Interface for document-specific operations
- TranslationRequest: Data class for translation requests
- TranslationResult: Data class for translation results

This architecture ensures that regardless of the document type (Google Slides or PPTX),
translations are processed consistently with the same quality standards, caching behavior,
and model selection logic.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

# Type definitions
DocumentId = TypeVar("DocumentId", str, object)
TextElements = Dict[str, str]
MetadataType = List[Dict[str, Any]]


@dataclass
class TranslationRequest:
    """Data structure for translation requests."""

    text_elements: TextElements
    metadata: MetadataType
    source_language: str
    target_language: str
    quality_level: str = "standard"
    use_cache: bool = True
    use_qa: bool = True
    use_glossary: bool = True
    batch_size: int = 5
    max_workers: int = 4
    api_key: Optional[str] = None
    recovery_file: Optional[str] = None
    progress_callback: Optional[Callable[[int, int], None]] = None


@dataclass
class TranslationResult:
    """Data structure for translation results."""

    translated_elements: TextElements
    execution_time: float
    cost: Dict[str, Any]
    success: bool = True
    error: Optional[str] = None
    new_document_id: Optional[str] = None


class DocumentAdapter(ABC):
    """
    Abstract interface for document-specific operations.

    This interface defines the operations needed to extract text from and update
    a specific document format (e.g., Google Slides or PowerPoint).
    """

    @abstractmethod
    def extract_text(
        self, document_id: DocumentId
    ) -> tuple[TextElements, MetadataType]:
        """
        Extract text elements and metadata from a document.

        Args:
            document_id: Identifier for the document (file path or Google ID)

        Returns:
            tuple: (text_elements, metadata)
        """
        pass

    @abstractmethod
    def update_document(
        self,
        document_id: DocumentId,
        translated_elements: TextElements,
        target_language: str,
    ) -> DocumentId:
        """
        Update a document with translated text.

        Args:
            document_id: Identifier for the document
            translated_elements: Dictionary of translated text elements
            target_language: Target language code

        Returns:
            DocumentId: Identifier for the new/updated document
        """
        pass


class TranslationService(ABC):
    """
    Abstract interface for translation services.

    This interface defines the core operations for translating text between languages,
    regardless of the source document type.
    """

    @abstractmethod
    def translate_elements(self, request: TranslationRequest) -> TranslationResult:
        """
        Translate text elements according to the request parameters.

        Args:
            request: A TranslationRequest object containing all translation parameters

        Returns:
            TranslationResult: Results of the translation operation
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def get_supported_languages(self) -> Dict[str, str]:
        """
        Get the languages supported by this translation service.

        Returns:
            Dict[str, str]: Dictionary of language codes to language names
        """
        pass

    @abstractmethod
    def get_supported_quality_levels(self) -> Dict[str, str]:
        """
        Get the quality levels supported by this translation service.

        Returns:
            Dict[str, str]: Dictionary of quality level codes to descriptions
        """
        pass
