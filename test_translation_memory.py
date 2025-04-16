#!/usr/bin/env python3
"""
Test script for the translation memory feature.

This script tests the translation memory functionality by:
1. Creating a simple translation memory
2. Adding translations to the memory
3. Looking up translations from the memory
4. Verifying that the memory is working correctly
"""
import os
import json
import tempfile
from ai_deck_translator.utils.translation_memory import (
    TranslationMemory,
    save_translation,
    lookup_translation,
    get_memory_stats,
    clear_memory,
    export_memory,
    import_memory,
)


def test_translation_memory_class():
    """Test the TranslationMemory class directly."""
    print("Testing TranslationMemory class...")

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
        print(f"Exported memory to {export_file}")

        # Clear memory
        memory.clear_memory()
        assert memory.get_entry_count() == 0, "Memory should be empty after clearing"

        # Import memory
        memory.import_memory(export_file)
        assert (
            memory.get_entry_count() > 0
        ), "Memory should not be empty after importing"
        print(f"Imported memory from {export_file}")

        # Clean up
        os.remove(export_file)

        print("TranslationMemory class tests passed!")
    finally:
        # Clean up
        if os.path.exists(memory_file):
            os.remove(memory_file)


def test_translation_memory_functions():
    """Test the translation memory functions."""
    print("\nTesting translation memory functions...")

    # Create a temporary file for the memory
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
        memory_file = temp_file.name

    try:
        # Clear any existing memory
        clear_memory(memory_file=memory_file)

        # Add translations
        save_translation(
            "Hello world",
            "Bonjour le monde",
            "en",
            "fr",
            {"context": "greeting"},
            memory_file,
        )

        save_translation(
            "How are you?",
            "Comment allez-vous?",
            "en",
            "fr",
            {"context": "greeting"},
            memory_file,
        )

        # Look up translations
        fr_translation = lookup_translation("Hello world", "en", "fr", memory_file)
        unknown_translation = lookup_translation("Goodbye", "en", "fr", memory_file)

        # Verify results
        print(f"English to French: 'Hello world' -> '{fr_translation}'")
        print(f"Unknown translation: 'Goodbye' -> '{unknown_translation}'")

        assert fr_translation == "Bonjour le monde", "French translation incorrect"
        assert unknown_translation is None, "Unknown translation should be None"

        # Get memory stats
        stats = get_memory_stats(memory_file)
        print(f"Memory stats: {stats}")

        # Export memory
        export_file = os.path.join(tempfile.gettempdir(), "export_memory_func.json")
        export_memory(export_file, memory_file)
        print(f"Exported memory to {export_file}")

        # Clear memory
        clear_memory(memory_file=memory_file)
        stats = get_memory_stats(memory_file)
        assert stats["total_entries"] == 0, "Memory should be empty after clearing"

        # Import memory
        import_memory(export_file, True, memory_file)
        stats = get_memory_stats(memory_file)
        assert stats["total_entries"] > 0, "Memory should not be empty after importing"
        print(f"Imported memory from {export_file}")

        # Clean up
        os.remove(export_file)

        print("Translation memory functions tests passed!")
    finally:
        # Clean up
        if os.path.exists(memory_file):
            os.remove(memory_file)


def test_with_translator():
    """Test the translation memory with the translator module."""
    print("\nTesting translation memory with translator module...")

    # Import the translator module
    from ai_deck_translator.core.translator import translate_text

    # Create a temporary file for the memory
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
        memory_file = temp_file.name

    try:
        # Clear any existing memory
        clear_memory(memory_file=memory_file)

        # Create a mock translation function
        def mock_translate(texts, target_language):
            """Mock translation function that adds a prefix to the text."""
            print(f"Mock translating {len(texts)} texts to {target_language}")
            return [f"[{target_language}] {text}" for text in texts]

        # Create test data
        text_elements = {
            "slide1_shape1": "Hello world",
            "slide1_shape2": "This is a test",
            "slide2_shape1": "Another test",
            "slide2_shape2": "Hello world",  # Duplicate text
        }

        slide_metadata = [
            {
                "slide_number": 1,
                "layout": "Title Slide",
                "notes": "Speaker notes for slide 1",
            },
            {
                "slide_number": 2,
                "layout": "Content Slide",
                "notes": "Speaker notes for slide 2",
            },
        ]

        # First translation - should use the mock translator for all elements
        print("First translation (no memory hits):")
        translated1 = translate_text(
            text_elements=text_elements,
            slide_metadata=slide_metadata,
            target_language="es",
            translate_func=mock_translate,
            source_language="en",
            use_translation_memory=True,
            update_translation_memory=True,
        )

        # Print results
        for key, value in translated1.items():
            print(f"  {key}: {value}")

        # Second translation - should use the translation memory for all elements
        print("\nSecond translation (should use memory for all elements):")
        translated2 = translate_text(
            text_elements=text_elements,
            slide_metadata=slide_metadata,
            target_language="es",
            translate_func=mock_translate,
            source_language="en",
            use_translation_memory=True,
            update_translation_memory=True,
        )

        # Print results
        for key, value in translated2.items():
            print(f"  {key}: {value}")

        # Verify that the results are the same
        for key in text_elements:
            assert (
                translated1[key] == translated2[key]
            ), f"Translation for {key} doesn't match"

        # Verify that notes were translated
        assert "slide1_notes" in translated1, "Notes for slide 1 not translated"
        assert "slide2_notes" in translated1, "Notes for slide 2 not translated"

        # Get memory stats
        stats = get_memory_stats(memory_file)
        print(f"\nMemory stats: {stats}")

        print("Translation memory with translator module tests passed!")
    finally:
        # Clean up
        if os.path.exists(memory_file):
            os.remove(memory_file)


def main():
    """Main function."""
    print("Testing translation memory feature...\n")

    # Test the TranslationMemory class
    test_translation_memory_class()

    # Test the translation memory functions
    test_translation_memory_functions()

    # Test with translator module
    test_with_translator()

    print("\nAll translation memory tests passed!")


if __name__ == "__main__":
    main()
