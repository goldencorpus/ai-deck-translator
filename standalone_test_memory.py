#!/usr/bin/env python3
"""
Standalone test script for the translation memory feature.

This script implements a simple translation memory and tests its functionality.
"""
import os
import json
import hashlib
import tempfile
from datetime import datetime
from typing import Dict, Any, Optional


class TranslationMemory:
    """Simple translation memory implementation."""

    def __init__(self, memory_file: str):
        """Initialize the translation memory."""
        self.memory_file = memory_file
        self.memory = {}

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)

        # Load existing memory if available
        self._load_memory()

        print(f"Translation memory initialized with {self.get_entry_count()} entries")

    def _load_memory(self) -> None:
        """Load the translation memory from the memory file."""
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    self.memory = json.load(f)
                print(f"Loaded translation memory from {self.memory_file}")
            except Exception as e:
                print(f"Error loading translation memory: {e}")
                self.memory = {}

    def _save_memory(self) -> None:
        """Save the translation memory to the memory file."""
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self.memory, f, ensure_ascii=False, indent=2)
            print(f"Saved translation memory to {self.memory_file}")
        except Exception as e:
            print(f"Error saving translation memory: {e}")

    def _get_text_hash(self, text: str) -> str:
        """Generate a hash for the text to use as a key in the memory."""
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def save_translation(
        self,
        source_text: str,
        translated_text: str,
        source_language: str,
        target_language: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Save a translation to the memory."""
        if not source_text or not translated_text:
            print("Cannot save empty translation")
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
            "timestamp": datetime.now().isoformat(),
        }

        # Save the memory to disk
        self._save_memory()

        print(f"Saved translation for '{source_text[:30]}...' to memory")

    def lookup_translation(
        self, source_text: str, source_language: str, target_language: str
    ) -> Optional[str]:
        """Look up a translation in the memory."""
        if not source_text:
            return None

        # Check if language pair exists
        language_pair = f"{source_language}-{target_language}"
        if language_pair not in self.memory:
            print(f"No translations found for language pair {language_pair}")
            return None

        # Generate hash for the source text
        text_hash = self._get_text_hash(source_text)

        # Look up the translation
        if text_hash in self.memory[language_pair]:
            translation = self.memory[language_pair][text_hash]["translation"]
            print(f"Found translation for '{source_text[:30]}...' in memory")
            return translation

        # Try fuzzy matching if exact match not found
        fuzzy_match = self._find_fuzzy_match(source_text, language_pair)
        if fuzzy_match:
            print(f"Found fuzzy match for '{source_text[:30]}...' in memory")
            return fuzzy_match

        print(f"No translation found for '{source_text[:30]}...'")
        return None

    def _find_fuzzy_match(self, source_text: str, language_pair: str) -> Optional[str]:
        """Find a fuzzy match for the source text in the memory."""
        # Simple fuzzy matching: check if source text is a substring of any entry
        # or if any entry is a substring of the source text
        source_text_lower = source_text.lower()

        for entry in self.memory[language_pair].values():
            entry_source = entry["source"].lower()

            # Check if source text is a substring of the entry
            if source_text_lower in entry_source and len(source_text) > 10:
                return entry["translation"]

            # Check if entry is a substring of the source text
            if entry_source in source_text_lower and len(entry["source"]) > 10:
                return entry["translation"]

        return None

    def get_entry_count(self) -> int:
        """Get the total number of entries in the translation memory."""
        count = 0
        for language_pair in self.memory:
            count += len(self.memory[language_pair])
        return count

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get statistics about the translation memory."""
        stats = {
            "total_entries": self.get_entry_count(),
            "language_pairs": {},
            "memory_file": self.memory_file,
        }

        for language_pair in self.memory:
            stats["language_pairs"][language_pair] = len(self.memory[language_pair])

        return stats

    def clear_memory(self, language_pair: Optional[str] = None) -> None:
        """Clear the translation memory."""
        if language_pair:
            if language_pair in self.memory:
                self.memory[language_pair] = {}
                print(f"Cleared translation memory for language pair {language_pair}")
            else:
                print(f"Language pair {language_pair} not found in memory")
        else:
            self.memory = {}
            print("Cleared entire translation memory")

        # Save the memory to disk
        self._save_memory()

    def export_memory(self, export_file: str) -> bool:
        """Export the translation memory to a file."""
        try:
            with open(export_file, "w", encoding="utf-8") as f:
                json.dump(self.memory, f, ensure_ascii=False, indent=2)
            print(f"Exported translation memory to {export_file}")
            return True
        except Exception as e:
            print(f"Error exporting translation memory: {e}")
            return False

    def import_memory(self, import_file: str, merge: bool = True) -> bool:
        """Import a translation memory from a file."""
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

                print(f"Merged translation memory from {import_file}")
            else:
                # Replace existing memory
                self.memory = imported_memory
                print(f"Replaced translation memory with {import_file}")

            # Save the memory to disk
            self._save_memory()

            return True
        except Exception as e:
            print(f"Error importing translation memory: {e}")
            return False


def test_translation_memory():
    """Test the translation memory functionality."""
    print("Testing translation memory...")

    # Create a temporary file for the memory
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
        memory_file = temp_file.name

    try:
        # Create a translation memory
        memory = TranslationMemory(memory_file)

        # Add translations
        memory.save_translation(
            "Hello world", "Bonjour le monde", "en", "fr", {"context": "greeting"}
        )

        memory.save_translation(
            "How are you?", "Comment allez-vous?", "en", "fr", {"context": "greeting"}
        )

        memory.save_translation(
            "Hello world", "Hola mundo", "en", "es", {"context": "greeting"}
        )

        # Look up translations
        fr_translation = memory.lookup_translation("Hello world", "en", "fr")
        es_translation = memory.lookup_translation("Hello world", "en", "es")
        unknown_translation = memory.lookup_translation("Goodbye", "en", "fr")

        # Verify results
        print(f"English to French: 'Hello world' -> '{fr_translation}'")
        print(f"English to Spanish: 'Hello world' -> '{es_translation}'")
        print(f"Unknown translation: 'Goodbye' -> '{unknown_translation}'")

        assert fr_translation == "Bonjour le monde", "French translation incorrect"
        assert es_translation == "Hola mundo", "Spanish translation incorrect"
        assert unknown_translation is None, "Unknown translation should be None"

        # Test fuzzy matching
        fuzzy_translation = memory.lookup_translation(
            "Hello beautiful world", "en", "fr"
        )
        print(f"Fuzzy match: 'Hello beautiful world' -> '{fuzzy_translation}'")

        # Get memory stats
        stats = memory.get_memory_stats()
        print(f"Memory stats: {stats}")

        # Export memory
        export_file = os.path.join(tempfile.gettempdir(), "export_memory.json")
        memory.export_memory(export_file)

        # Clear memory
        memory.clear_memory()
        assert memory.get_entry_count() == 0, "Memory should be empty after clearing"

        # Import memory
        memory.import_memory(export_file)
        assert (
            memory.get_entry_count() > 0
        ), "Memory should not be empty after importing"

        # Clean up
        os.remove(export_file)

        print("Translation memory tests passed!")
    finally:
        # Clean up
        if os.path.exists(memory_file):
            os.remove(memory_file)


def test_translator_with_memory():
    """Test a simple translator with translation memory."""
    print("\nTesting translator with memory...")

    # Create a temporary file for the memory
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
        memory_file = temp_file.name

    try:
        # Create a translation memory
        memory = TranslationMemory(memory_file)

        # Create a mock translator function
        def mock_translate(text, source_language, target_language):
            """Mock translation function that adds a prefix to the text."""
            print(
                f"Mock translating '{text[:30]}...' from {source_language} to {target_language}"
            )
            return f"[{target_language}] {text}"

        # Create a translator function that uses the translation memory
        def translate_with_memory(text, source_language, target_language):
            """Translate text using the translation memory if available."""
            # Check if the translation is in the memory
            translation = memory.lookup_translation(
                text, source_language, target_language
            )

            if translation:
                return translation

            # If not in memory, use the mock translator
            translation = mock_translate(text, source_language, target_language)

            # Save the translation to the memory
            memory.save_translation(text, translation, source_language, target_language)

            return translation

        # Test data
        texts = [
            "Hello world",
            "How are you?",
            "This is a test",
            "Hello world",  # Duplicate text
        ]

        # First translation - should use the mock translator for all texts
        print("First translation (no memory hits):")
        translations1 = []
        for text in texts:
            translation = translate_with_memory(text, "en", "fr")
            translations1.append(translation)
            print(f"  '{text}' -> '{translation}'")

        # Second translation - should use the translation memory for all texts
        print("\nSecond translation (should use memory for all texts):")
        translations2 = []
        for text in texts:
            translation = translate_with_memory(text, "en", "fr")
            translations2.append(translation)
            print(f"  '{text}' -> '{translation}'")

        # Verify that the results are the same
        for i, (t1, t2) in enumerate(zip(translations1, translations2)):
            assert t1 == t2, f"Translation for '{texts[i]}' doesn't match"

        # Get memory stats
        stats = memory.get_memory_stats()
        print(f"\nMemory stats: {stats}")

        print("Translator with memory tests passed!")
    finally:
        # Clean up
        if os.path.exists(memory_file):
            os.remove(memory_file)


def main():
    """Main function."""
    print("Testing translation memory feature...\n")

    # Test the translation memory
    test_translation_memory()

    # Test the translator with memory
    test_translator_with_memory()

    print("\nAll translation memory tests passed!")


if __name__ == "__main__":
    main()
