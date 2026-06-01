"""
Translation Memory module for AI Deck Translator.

This module provides functionality for storing and retrieving previous translations
to improve consistency and efficiency. It implements a simple translation memory
that can be used to avoid re-translating the same text multiple times.

Public Functions:
    save_translation: Save a translation to the translation memory
    lookup_translation: Look up a translation in the translation memory
    get_memory_stats: Get statistics about the translation memory
    clear_memory: Clear the translation memory
    export_memory: Export the translation memory to a file
    import_memory: Import a translation memory from a file
"""

import hashlib
import json
import os
from typing import Any, Dict, List, Optional, Tuple, cast

from ..utils.logging import get_logger

# Set up logging
logger = get_logger(__name__)


class TranslationMemory:
    """
    Translation Memory class for storing and retrieving previous translations.

    This class provides methods for saving translations to a memory store,
    looking up existing translations, and managing the translation memory.
    """

    def __init__(self, memory_file: Optional[str] = None):
        """
        Initialize the translation memory.

        Args:
            memory_file (str, optional): Path to the memory file. If not provided,
                a default path will be used.
        """
        self.memory_file = memory_file or os.path.join(
            os.path.expanduser("~"), ".ai_deck_translator", "translation_memory.json"
        )

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)

        # Initialize memory
        self.memory: Dict[str, Dict[str, Dict[str, Any]]] = {}

        # Load existing memory if available
        self._load_memory()

        logger.info(
            f"Translation memory initialized with {self.get_entry_count()} entries"
        )

    def _load_memory(self) -> None:
        """
        Load the translation memory from the memory file.
        """
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    self.memory = json.load(f)
                logger.debug(f"Loaded translation memory from {self.memory_file}")
            except Exception as e:
                logger.error(f"Error loading translation memory: {e}")
                self.memory = {}

    def _save_memory(self) -> None:
        """
        Save the translation memory to the memory file.
        """
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self.memory, f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved translation memory to {self.memory_file}")
        except Exception as e:
            logger.error(f"Error saving translation memory: {e}")

    def _get_text_hash(self, text: str) -> str:
        """
        Generate a hash for the text to use as a key in the memory.

        Args:
            text (str): The text to hash

        Returns:
            str: The hash of the text
        """
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def save_translation(
        self,
        source_text: str,
        translated_text: str,
        source_language: str,
        target_language: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Save a translation to the memory.

        Args:
            source_text (str): The original text
            translated_text (str): The translated text
            source_language (str): The source language code
            target_language (str): The target language code
            context (dict, optional): Additional context about the translation
        """
        if not source_text or not translated_text:
            logger.warning("Cannot save empty translation")
            return

        # Initialize language pair if it doesn't exist
        language_pair = f"{source_language}-{target_language}"
        if language_pair not in self.memory:
            self.memory[language_pair] = {}

        # Generate hash for the source text
        text_hash = self._get_text_hash(source_text)

        # Save the translation
        self.memory[language_pair][text_hash] = {
            "source": source_text,
            "translation": translated_text,
            "context": context or {},
            "timestamp": self._get_timestamp(),
        }

        # Save the memory to disk
        self._save_memory()

        logger.debug(f"Saved translation for '{source_text[:30]}...' to memory")

    def lookup_translation(
        self, source_text: str, source_language: str, target_language: str
    ) -> Optional[str]:
        """
        Look up a translation in the memory.

        Args:
            source_text (str): The text to look up
            source_language (str): The source language code
            target_language (str): The target language code

        Returns:
            str or None: The translated text if found, None otherwise
        """
        if not source_text:
            return None

        # Check if language pair exists
        language_pair = f"{source_language}-{target_language}"
        if language_pair not in self.memory:
            logger.debug(f"No translations found for language pair {language_pair}")
            return None

        # Generate hash for the source text
        text_hash = self._get_text_hash(source_text)

        # Look up the translation
        if text_hash in self.memory[language_pair]:
            translation = self.memory[language_pair][text_hash]["translation"]
            logger.debug(f"Found translation for '{source_text[:30]}...' in memory")
            return cast(Optional[str], translation)

        # Try fuzzy matching if exact match not found
        fuzzy_match = self._find_fuzzy_match(source_text, language_pair)
        if fuzzy_match:
            logger.debug(f"Found fuzzy match for '{source_text[:30]}...' in memory")
            return fuzzy_match

        logger.debug(f"No translation found for '{source_text[:30]}...'")
        return None

    def _find_fuzzy_match(self, source_text: str, language_pair: str) -> Optional[str]:
        """
        Find a fuzzy match for the source text in the memory.

        This is a simple implementation that checks if the source text is a substring
        of any entry in the memory, or vice versa. A more sophisticated implementation
        could use techniques like Levenshtein distance or TF-IDF similarity.

        Args:
            source_text (str): The text to look up
            language_pair (str): The language pair to search in

        Returns:
            str or None: The translated text if a fuzzy match is found, None otherwise
        """
        # Simple fuzzy matching: check if source text is a substring of any entry
        # or if any entry is a substring of the source text
        source_text_lower = source_text.lower()

        for entry in self.memory[language_pair].values():
            entry_source = entry["source"].lower()

            # Check if source text is a substring of the entry
            if source_text_lower in entry_source and len(source_text) > 10:
                return cast(Optional[str], entry["translation"])

            # Check if entry is a substring of the source text
            if entry_source in source_text_lower and len(entry["source"]) > 10:
                return cast(Optional[str], entry["translation"])

        return None

    def get_entry_count(self) -> int:
        """
        Get the total number of entries in the translation memory.

        Returns:
            int: The number of entries
        """
        count = 0
        for language_pair in self.memory:
            count += len(self.memory[language_pair])
        return count

    def get_memory_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the translation memory.

        Returns:
            dict: Statistics about the translation memory
        """
        stats: dict = {
            "total_entries": self.get_entry_count(),
            "language_pairs": {},
            "memory_file": self.memory_file,
        }

        for language_pair in self.memory:
            stats["language_pairs"][language_pair] = len(self.memory[language_pair])

        return stats

    def clear_memory(self, language_pair: Optional[str] = None) -> None:
        """
        Clear the translation memory.

        Args:
            language_pair (str, optional): The language pair to clear.
                If not provided, the entire memory will be cleared.
        """
        if language_pair:
            if language_pair in self.memory:
                self.memory[language_pair] = {}
                logger.info(
                    f"Cleared translation memory for language pair {language_pair}"
                )
            else:
                logger.warning(f"Language pair {language_pair} not found in memory")
        else:
            self.memory = {}
            logger.info("Cleared entire translation memory")

        # Save the memory to disk
        self._save_memory()

    def export_memory(self, export_file: str) -> bool:
        """
        Export the translation memory to a file.

        Args:
            export_file (str): Path to the export file

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(export_file, "w", encoding="utf-8") as f:
                json.dump(self.memory, f, ensure_ascii=False, indent=2)
            logger.info(f"Exported translation memory to {export_file}")
            return True
        except Exception as e:
            logger.error(f"Error exporting translation memory: {e}")
            return False

    def import_memory(self, import_file: str, merge: bool = True) -> bool:
        """
        Import a translation memory from a file.

        Args:
            import_file (str): Path to the import file
            merge (bool, optional): Whether to merge with the existing memory.
                If False, the existing memory will be replaced. Defaults to True.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(import_file, "r", encoding="utf-8") as f:
                imported_memory = json.load(f)

            if merge:
                # Merge with existing memory
                for language_pair in imported_memory:
                    if language_pair not in self.memory:
                        self.memory[language_pair] = {}

                    for text_hash, entry in imported_memory[language_pair].items():
                        self.memory[language_pair][text_hash] = entry

                logger.info(f"Merged translation memory from {import_file}")
            else:
                # Replace existing memory
                self.memory = imported_memory
                logger.info(f"Replaced translation memory with {import_file}")

            # Save the memory to disk
            self._save_memory()

            return True
        except Exception as e:
            logger.error(f"Error importing translation memory: {e}")
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
_memory_instance = None


def get_translation_memory(memory_file: Optional[str] = None) -> TranslationMemory:
    """
    Get the translation memory instance.

    Args:
        memory_file (str, optional): Path to the memory file. If not provided,
            a default path will be used.

    Returns:
        TranslationMemory: The translation memory instance
    """
    global _memory_instance

    if _memory_instance is None:
        _memory_instance = TranslationMemory(memory_file)

    return _memory_instance


def save_translation(
    source_text: str,
    translated_text: str,
    source_language: str,
    target_language: str,
    context: Optional[Dict[str, Any]] = None,
    memory_file: Optional[str] = None,
) -> None:
    """
    Save a translation to the memory.

    Args:
        source_text (str): The original text
        translated_text (str): The translated text
        source_language (str): The source language code
        target_language (str): The target language code
        context (dict, optional): Additional context about the translation
        memory_file (str, optional): Path to the memory file
    """
    memory = get_translation_memory(memory_file)
    memory.save_translation(
        source_text, translated_text, source_language, target_language, context
    )


def lookup_translation(
    source_text: str,
    source_language: str,
    target_language: str,
    memory_file: Optional[str] = None,
) -> Optional[str]:
    """
    Look up a translation in the memory.

    Args:
        source_text (str): The text to look up
        source_language (str): The source language code
        target_language (str): The target language code
        memory_file (str, optional): Path to the memory file

    Returns:
        str or None: The translated text if found, None otherwise
    """
    memory = get_translation_memory(memory_file)
    return memory.lookup_translation(source_text, source_language, target_language)


def get_memory_stats(memory_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Get statistics about the translation memory.

    Args:
        memory_file (str, optional): Path to the memory file

    Returns:
        dict: Statistics about the translation memory
    """
    memory = get_translation_memory(memory_file)
    return memory.get_memory_stats()


def clear_memory(
    language_pair: Optional[str] = None, memory_file: Optional[str] = None
) -> None:
    """
    Clear the translation memory.

    Args:
        language_pair (str, optional): The language pair to clear
        memory_file (str, optional): Path to the memory file
    """
    memory = get_translation_memory(memory_file)
    memory.clear_memory(language_pair)


def export_memory(export_file: str, memory_file: Optional[str] = None) -> bool:
    """
    Export the translation memory to a file.

    Args:
        export_file (str): Path to the export file
        memory_file (str, optional): Path to the memory file

    Returns:
        bool: True if successful, False otherwise
    """
    memory = get_translation_memory(memory_file)
    return memory.export_memory(export_file)


def import_memory(
    import_file: str, merge: bool = True, memory_file: Optional[str] = None
) -> bool:
    """
    Import a translation memory from a file.

    Args:
        import_file (str): Path to the import file
        merge (bool, optional): Whether to merge with the existing memory
        memory_file (str, optional): Path to the memory file

    Returns:
        bool: True if successful, False otherwise
    """
    memory = get_translation_memory(memory_file)
    return memory.import_memory(import_file, merge)
