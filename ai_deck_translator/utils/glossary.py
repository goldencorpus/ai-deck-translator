"""
Glossary module for AI Deck Translator.

This module provides functionality for managing translation glossaries to ensure
consistent terminology across translations. It allows users to define preferred
translations for specific terms and ensures these terms are consistently translated
throughout presentations.

Public Functions:
    save_term: Save a term to the glossary
    lookup_term: Look up a term in the glossary
    get_glossary_stats: Get statistics about the glossary
    clear_glossary: Clear the glossary
    export_glossary: Export the glossary to a file
    import_glossary: Import a glossary from a file
"""

import os
import json
import re
from typing import Dict, List, Tuple, Optional, Any, Set
from ..utils.logging import get_logger

# Set up logging
logger = get_logger(__name__)


class Glossary:
    """
    Glossary class for managing terminology.

    This class provides methods for saving terms to a glossary,
    looking up terms, and managing the glossary.
    """

    def __init__(self, glossary_file: Optional[str] = None):
        """
        Initialize the glossary.

        Args:
            glossary_file (str, optional): Path to the glossary file. If not provided,
                a default path will be used.
        """
        self.glossary_file = glossary_file or os.path.join(
            os.path.expanduser("~"), ".ai_deck_translator", "glossary.json"
        )

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(self.glossary_file), exist_ok=True)

        # Initialize glossary
        self.glossary: Dict[str, Dict[str, Dict[str, Any]]] = {}

        # Load existing glossary if available
        self._load_glossary()

        logger.info(f"Glossary initialized with {self.get_term_count()} terms")

    def _load_glossary(self) -> None:
        """
        Load the glossary from the glossary file.
        """
        if os.path.exists(self.glossary_file):
            try:
                with open(self.glossary_file, "r", encoding="utf-8") as f:
                    self.glossary = json.load(f)
                logger.debug(f"Loaded glossary from {self.glossary_file}")
            except Exception as e:
                logger.error(f"Error loading glossary: {e}")
                self.glossary = {}

    def _save_glossary(self) -> None:
        """
        Save the glossary to the glossary file.
        """
        try:
            with open(self.glossary_file, "w", encoding="utf-8") as f:
                json.dump(self.glossary, f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved glossary to {self.glossary_file}")
        except Exception as e:
            logger.error(f"Error saving glossary: {e}")

    def save_term(
        self,
        term: str,
        translation: str,
        source_language: str,
        target_language: str,
        case_sensitive: bool = False,
        notes: Optional[str] = None,
    ) -> None:
        """
        Save a term to the glossary.

        Args:
            term (str): The source term
            translation (str): The preferred translation
            source_language (str): The source language code
            target_language (str): The target language code
            case_sensitive (bool, optional): Whether the term is case-sensitive. Defaults to False.
            notes (str, optional): Additional notes about the term. Defaults to None.
        """
        if not term or not translation:
            logger.warning("Cannot save empty term or translation")
            return

        # Initialize language pair if it doesn't exist
        language_pair = f"{source_language}-{target_language}"
        if language_pair not in self.glossary:
            self.glossary[language_pair] = {}

        # Save the term
        term_key = term if case_sensitive else term.lower()
        self.glossary[language_pair][term_key] = {
            "term": term,
            "translation": translation,
            "case_sensitive": case_sensitive,
            "notes": notes or "",
            "timestamp": self._get_timestamp(),
        }

        # Save the glossary to disk
        self._save_glossary()

        logger.debug(f"Saved term '{term}' to glossary")

    def lookup_term(
        self, term: str, source_language: str, target_language: str
    ) -> Optional[str]:
        """
        Look up a term in the glossary.

        Args:
            term (str): The term to look up
            source_language (str): The source language code
            target_language (str): The target language code

        Returns:
            str or None: The preferred translation if found, None otherwise
        """
        if not term:
            return None

        # Check if language pair exists
        language_pair = f"{source_language}-{target_language}"
        if language_pair not in self.glossary:
            logger.debug(f"No terms found for language pair {language_pair}")
            return None

        # Look up the term (case-sensitive)
        if term in self.glossary[language_pair]:
            translation = self.glossary[language_pair][term]["translation"]
            logger.debug(f"Found case-sensitive match for '{term}' in glossary")
            return translation

        # Look up the term (case-insensitive)
        term_lower = term.lower()
        for term_key, entry in self.glossary[language_pair].items():
            if not entry["case_sensitive"] and term_lower == term_key.lower():
                translation = entry["translation"]
                logger.debug(f"Found case-insensitive match for '{term}' in glossary")
                return translation

        logger.debug(f"No match found for '{term}' in glossary")
        return None

    def find_terms_in_text(
        self, text: str, source_language: str, target_language: str
    ) -> Dict[str, str]:
        """
        Find all glossary terms in a text.

        Args:
            text (str): The text to search
            source_language (str): The source language code
            target_language (str): The target language code

        Returns:
            Dict[str, str]: Dictionary mapping found terms to their translations
        """
        if not text:
            return {}

        # Check if language pair exists
        language_pair = f"{source_language}-{target_language}"
        if language_pair not in self.glossary:
            logger.debug(f"No terms found for language pair {language_pair}")
            return {}

        found_terms = {}

        # Find case-sensitive terms
        for term_key, entry in self.glossary[language_pair].items():
            if entry["case_sensitive"]:
                term = entry["term"]
                if term in text:
                    found_terms[term] = entry["translation"]

        # Find case-insensitive terms
        text_lower = text.lower()
        for term_key, entry in self.glossary[language_pair].items():
            if not entry["case_sensitive"]:
                term = entry["term"]
                term_lower = term.lower()
                if term_lower in text_lower:
                    # Find all occurrences with correct casing
                    pattern = re.compile(re.escape(term_lower), re.IGNORECASE)
                    for match in pattern.finditer(text):
                        found_term = text[match.start() : match.end()]
                        found_terms[found_term] = entry["translation"]

        if found_terms:
            logger.debug(f"Found {len(found_terms)} glossary terms in text")

        return found_terms

    def apply_glossary_to_text(
        self,
        text: str,
        source_language: str,
        target_language: str,
        translated_text: str,
    ) -> str:
        """
        Apply glossary terms to a translated text.

        This function finds glossary terms in the source text and ensures their
        preferred translations are used in the translated text.

        Args:
            text (str): The source text
            source_language (str): The source language code
            target_language (str): The target language code
            translated_text (str): The translated text

        Returns:
            str: The translated text with glossary terms applied
        """
        if not text or not translated_text:
            return translated_text

        # Find glossary terms in the source text
        found_terms = self.find_terms_in_text(text, source_language, target_language)

        if not found_terms:
            return translated_text

        # Apply glossary terms to the translated text
        # This is a simple implementation that replaces terms in the translated text
        # A more sophisticated implementation would use machine translation with a glossary
        modified_text = translated_text

        # Sort terms by length (longest first) to avoid partial replacements
        sorted_terms = sorted(found_terms.keys(), key=len, reverse=True)

        for term in sorted_terms:
            translation = found_terms[term]
            # This is a simplistic approach and may not work well for all languages
            # A more sophisticated approach would use a translation API with glossary support
            modified_text = modified_text.replace(term, translation)

        if modified_text != translated_text:
            logger.debug(f"Applied glossary terms to translated text")

        return modified_text

    def get_term_count(self) -> int:
        """
        Get the total number of terms in the glossary.

        Returns:
            int: The number of terms
        """
        count = 0
        for language_pair in self.glossary:
            count += len(self.glossary[language_pair])
        return count

    def get_glossary_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the glossary.

        Returns:
            dict: Statistics about the glossary
        """
        stats = {
            "total_terms": self.get_term_count(),
            "language_pairs": {},
            "glossary_file": self.glossary_file,
        }

        for language_pair in self.glossary:
            stats["language_pairs"][language_pair] = len(self.glossary[language_pair])

        return stats

    def clear_glossary(self, language_pair: Optional[str] = None) -> None:
        """
        Clear the glossary.

        Args:
            language_pair (str, optional): The language pair to clear.
                If not provided, the entire glossary will be cleared.
        """
        if language_pair:
            if language_pair in self.glossary:
                self.glossary[language_pair] = {}
                logger.info(f"Cleared glossary for language pair {language_pair}")
            else:
                logger.warning(f"Language pair {language_pair} not found in glossary")
        else:
            self.glossary = {}
            logger.info("Cleared entire glossary")

        # Save the glossary to disk
        self._save_glossary()

    def export_glossary(self, export_file: str) -> bool:
        """
        Export the glossary to a file.

        Args:
            export_file (str): Path to the export file

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(export_file, "w", encoding="utf-8") as f:
                json.dump(self.glossary, f, ensure_ascii=False, indent=2)
            logger.info(f"Exported glossary to {export_file}")
            return True
        except Exception as e:
            logger.error(f"Error exporting glossary: {e}")
            return False

    def import_glossary(self, import_file: str, merge: bool = True) -> bool:
        """
        Import a glossary from a file.

        Args:
            import_file (str): Path to the import file
            merge (bool, optional): Whether to merge with the existing glossary.
                If False, the existing glossary will be replaced. Defaults to True.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(import_file, "r", encoding="utf-8") as f:
                imported_glossary = json.load(f)

            if merge:
                # Merge with existing glossary
                for language_pair in imported_glossary:
                    if language_pair not in self.glossary:
                        self.glossary[language_pair] = {}

                    for term_key, entry in imported_glossary[language_pair].items():
                        self.glossary[language_pair][term_key] = entry

                logger.info(f"Merged glossary from {import_file}")
            else:
                # Replace existing glossary
                self.glossary = imported_glossary
                logger.info(f"Replaced glossary with {import_file}")

            # Save the glossary to disk
            self._save_glossary()

            return True
        except Exception as e:
            logger.error(f"Error importing glossary: {e}")
            return False

    def _get_timestamp(self) -> str:
        """
        Get the current timestamp in ISO format.

        Returns:
            str: The current timestamp
        """
        from datetime import datetime

        return datetime.now().isoformat()


# Create a singleton instance
_glossary_instance = None


def get_glossary(glossary_file: Optional[str] = None) -> Glossary:
    """
    Get the glossary instance.

    Args:
        glossary_file (str, optional): Path to the glossary file. If not provided,
            a default path will be used.

    Returns:
        Glossary: The glossary instance
    """
    global _glossary_instance

    if _glossary_instance is None:
        _glossary_instance = Glossary(glossary_file)

    return _glossary_instance


def save_term(
    term: str,
    translation: str,
    source_language: str,
    target_language: str,
    case_sensitive: bool = False,
    notes: Optional[str] = None,
    glossary_file: Optional[str] = None,
) -> None:
    """
    Save a term to the glossary.

    Args:
        term (str): The source term
        translation (str): The preferred translation
        source_language (str): The source language code
        target_language (str): The target language code
        case_sensitive (bool, optional): Whether the term is case-sensitive. Defaults to False.
        notes (str, optional): Additional notes about the term. Defaults to None.
        glossary_file (str, optional): Path to the glossary file
    """
    glossary = get_glossary(glossary_file)
    glossary.save_term(
        term, translation, source_language, target_language, case_sensitive, notes
    )


def lookup_term(
    term: str,
    source_language: str,
    target_language: str,
    glossary_file: Optional[str] = None,
) -> Optional[str]:
    """
    Look up a term in the glossary.

    Args:
        term (str): The term to look up
        source_language (str): The source language code
        target_language (str): The target language code
        glossary_file (str, optional): Path to the glossary file

    Returns:
        str or None: The preferred translation if found, None otherwise
    """
    glossary = get_glossary(glossary_file)
    return glossary.lookup_term(term, source_language, target_language)


def find_terms_in_text(
    text: str,
    source_language: str,
    target_language: str,
    glossary_file: Optional[str] = None,
) -> Dict[str, str]:
    """
    Find all glossary terms in a text.

    Args:
        text (str): The text to search
        source_language (str): The source language code
        target_language (str): The target language code
        glossary_file (str, optional): Path to the glossary file

    Returns:
        Dict[str, str]: Dictionary mapping found terms to their translations
    """
    glossary = get_glossary(glossary_file)
    return glossary.find_terms_in_text(text, source_language, target_language)


def apply_glossary_to_text(
    text: str,
    source_language: str,
    target_language: str,
    translated_text: str,
    glossary_file: Optional[str] = None,
) -> str:
    """
    Apply glossary terms to a translated text.

    Args:
        text (str): The source text
        source_language (str): The source language code
        target_language (str): The target language code
        translated_text (str): The translated text
        glossary_file (str, optional): Path to the glossary file

    Returns:
        str: The translated text with glossary terms applied
    """
    glossary = get_glossary(glossary_file)
    return glossary.apply_glossary_to_text(
        text, source_language, target_language, translated_text
    )


def get_glossary_stats(glossary_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Get statistics about the glossary.

    Args:
        glossary_file (str, optional): Path to the glossary file

    Returns:
        dict: Statistics about the glossary
    """
    glossary = get_glossary(glossary_file)
    return glossary.get_glossary_stats()


def clear_glossary(
    language_pair: Optional[str] = None, glossary_file: Optional[str] = None
) -> None:
    """
    Clear the glossary.

    Args:
        language_pair (str, optional): The language pair to clear
        glossary_file (str, optional): Path to the glossary file
    """
    glossary = get_glossary(glossary_file)
    glossary.clear_glossary(language_pair)


def export_glossary(export_file: str, glossary_file: Optional[str] = None) -> bool:
    """
    Export the glossary to a file.

    Args:
        export_file (str): Path to the export file
        glossary_file (str, optional): Path to the glossary file

    Returns:
        bool: True if successful, False otherwise
    """
    glossary = get_glossary(glossary_file)
    return glossary.export_glossary(export_file)


def import_glossary(
    import_file: str, merge: bool = True, glossary_file: Optional[str] = None
) -> bool:
    """
    Import a glossary from a file.

    Args:
        import_file (str): Path to the import file
        merge (bool, optional): Whether to merge with the existing glossary
        glossary_file (str, optional): Path to the glossary file

    Returns:
        bool: True if successful, False otherwise
    """
    glossary = get_glossary(glossary_file)
    return glossary.import_glossary(import_file, merge)
