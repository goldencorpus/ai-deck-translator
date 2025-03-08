#!/usr/bin/env python3
"""
Test script for the glossary feature.

This script tests the glossary functionality by:
1. Creating a simple glossary
2. Adding terms to the glossary
3. Looking up terms from the glossary
4. Finding terms in text
5. Applying glossary terms to translated text
6. Verifying that the glossary is working correctly
"""
import os
import json
import tempfile
from ai_deck_translator.utils.glossary import (
    Glossary,
    save_term,
    lookup_term,
    find_terms_in_text,
    apply_glossary_to_text,
    get_glossary_stats,
    clear_glossary,
    export_glossary,
    import_glossary
)

def test_glossary_class():
    """Test the Glossary class directly."""
    print("Testing Glossary class...")
    
    # Create a temporary file for the glossary
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp_file:
        glossary_file = temp_file.name
    
    try:
        # Create a glossary
        glossary = Glossary(glossary_file)
        
        # Add terms
        glossary.save_term(
            "artificial intelligence",
            "人工知能",
            "en",
            "ja",
            case_sensitive=False,
            notes="AI technology"
        )
        
        glossary.save_term(
            "machine learning",
            "機械学習",
            "en",
            "ja",
            case_sensitive=False,
            notes="ML technology"
        )
        
        glossary.save_term(
            "Python",
            "Python",
            "en",
            "ja",
            case_sensitive=True,
            notes="Programming language"
        )
        
        # Look up terms
        ja_ai = glossary.lookup_term("artificial intelligence", "en", "ja")
        ja_ml = glossary.lookup_term("machine learning", "en", "ja")
        ja_python = glossary.lookup_term("Python", "en", "ja")
        ja_python_lower = glossary.lookup_term("python", "en", "ja")
        unknown_term = glossary.lookup_term("deep learning", "en", "ja")
        
        # Verify results
        print(f"English to Japanese: 'artificial intelligence' -> '{ja_ai}'")
        print(f"English to Japanese: 'machine learning' -> '{ja_ml}'")
        print(f"English to Japanese: 'Python' -> '{ja_python}'")
        print(f"English to Japanese: 'python' -> '{ja_python_lower}'")
        print(f"Unknown term: 'deep learning' -> '{unknown_term}'")
        
        assert ja_ai == "人工知能", "Japanese translation for 'artificial intelligence' incorrect"
        assert ja_ml == "機械学習", "Japanese translation for 'machine learning' incorrect"
        assert ja_python == "Python", "Japanese translation for 'Python' incorrect"
        assert ja_python_lower is None, "Case-sensitive term should not match with different case"
        assert unknown_term is None, "Unknown term should be None"
        
        # Test finding terms in text
        text = "Artificial Intelligence and Machine Learning are important fields in Python programming."
        found_terms = glossary.find_terms_in_text(text, "en", "ja")
        
        print(f"Found terms in text: {found_terms}")
        assert "Artificial Intelligence" in found_terms, "Should find 'Artificial Intelligence' in text"
        assert "Machine Learning" in found_terms, "Should find 'Machine Learning' in text"
        assert "Python" in found_terms, "Should find 'Python' in text"
        
        # Test applying glossary to translated text
        original_text = "Artificial Intelligence and Machine Learning are important fields in Python programming."
        translated_text = "人工知能と機械学習はPythonプログラミングの重要な分野です。"
        modified_text = glossary.apply_glossary_to_text(original_text, "en", "ja", translated_text)
        
        print(f"Original text: {original_text}")
        print(f"Translated text: {translated_text}")
        print(f"Modified text: {modified_text}")
        
        # Get glossary stats
        stats = glossary.get_glossary_stats()
        print(f"Glossary stats: {stats}")
        
        # Export glossary
        export_file = os.path.join(tempfile.gettempdir(), "export_glossary.json")
        glossary.export_glossary(export_file)
        
        # Clear glossary
        glossary.clear_glossary()
        assert glossary.get_term_count() == 0, "Glossary should be empty after clearing"
        
        # Import glossary
        glossary.import_glossary(export_file)
        assert glossary.get_term_count() > 0, "Glossary should not be empty after importing"
        
        # Clean up
        os.remove(export_file)
        
        print("Glossary class tests passed!")
    finally:
        # Clean up
        if os.path.exists(glossary_file):
            os.remove(glossary_file)

def test_glossary_functions():
    """Test the glossary functions."""
    print("\nTesting glossary functions...")
    
    # Create a temporary file for the glossary
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp_file:
        glossary_file = temp_file.name
    
    try:
        # Clear any existing glossary
        clear_glossary(glossary_file=glossary_file)
        
        # Add terms
        save_term(
            "artificial intelligence",
            "人工知能",
            "en",
            "ja",
            case_sensitive=False,
            notes="AI technology",
            glossary_file=glossary_file
        )
        
        save_term(
            "machine learning",
            "機械学習",
            "en",
            "ja",
            case_sensitive=False,
            notes="ML technology",
            glossary_file=glossary_file
        )
        
        # Look up terms
        ja_ai = lookup_term("artificial intelligence", "en", "ja", glossary_file)
        ja_ml = lookup_term("machine learning", "en", "ja", glossary_file)
        unknown_term = lookup_term("deep learning", "en", "ja", glossary_file)
        
        # Verify results
        print(f"English to Japanese: 'artificial intelligence' -> '{ja_ai}'")
        print(f"English to Japanese: 'machine learning' -> '{ja_ml}'")
        print(f"Unknown term: 'deep learning' -> '{unknown_term}'")
        
        assert ja_ai == "人工知能", "Japanese translation for 'artificial intelligence' incorrect"
        assert ja_ml == "機械学習", "Japanese translation for 'machine learning' incorrect"
        assert unknown_term is None, "Unknown term should be None"
        
        # Test finding terms in text
        text = "Artificial Intelligence and Machine Learning are important fields."
        found_terms = find_terms_in_text(text, "en", "ja", glossary_file)
        
        print(f"Found terms in text: {found_terms}")
        assert "Artificial Intelligence" in found_terms, "Should find 'Artificial Intelligence' in text"
        assert "Machine Learning" in found_terms, "Should find 'Machine Learning' in text"
        
        # Test applying glossary to translated text
        original_text = "Artificial Intelligence and Machine Learning are important fields."
        translated_text = "人工知能と機械学習は重要な分野です。"
        modified_text = apply_glossary_to_text(original_text, "en", "ja", translated_text, glossary_file)
        
        print(f"Original text: {original_text}")
        print(f"Translated text: {translated_text}")
        print(f"Modified text: {modified_text}")
        
        # Get glossary stats
        stats = get_glossary_stats(glossary_file)
        print(f"Glossary stats: {stats}")
        
        # Export glossary
        export_file = os.path.join(tempfile.gettempdir(), "export_glossary_func.json")
        export_glossary(export_file, glossary_file)
        
        # Clear glossary
        clear_glossary(glossary_file=glossary_file)
        stats = get_glossary_stats(glossary_file)
        assert stats["total_terms"] == 0, "Glossary should be empty after clearing"
        
        # Import glossary
        import_glossary(export_file, True, glossary_file)
        stats = get_glossary_stats(glossary_file)
        assert stats["total_terms"] > 0, "Glossary should not be empty after importing"
        
        # Clean up
        os.remove(export_file)
        
        print("Glossary functions tests passed!")
    finally:
        # Clean up
        if os.path.exists(glossary_file):
            os.remove(glossary_file)

def test_with_translator():
    """Test the glossary with the translator module."""
    print("\nTesting glossary with translator module...")
    
    # Import the translator module
    from ai_deck_translator.core.translator import translate_text
    
    # Create a temporary file for the glossary
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp_file:
        glossary_file = temp_file.name
    
    try:
        # Clear any existing glossary
        clear_glossary(glossary_file=glossary_file)
        
        # Add terms to the glossary
        save_term(
            "artificial intelligence",
            "人工知能",
            "en",
            "ja",
            case_sensitive=False,
            notes="AI technology",
            glossary_file=glossary_file
        )
        
        save_term(
            "machine learning",
            "機械学習",
            "en",
            "ja",
            case_sensitive=False,
            notes="ML technology",
            glossary_file=glossary_file
        )
        
        # Create a mock translation function
        def mock_translate(texts, target_language):
            """Mock translation function that adds a prefix to the text."""
            print(f"Mock translating {len(texts)} texts to {target_language}")
            
            # Simple mock translations
            translations = []
            for text in texts:
                if "artificial intelligence" in text.lower():
                    translations.append(f"AIと機械学習は重要です")
                elif "machine learning" in text.lower():
                    translations.append(f"機械学習は重要です")
                else:
                    translations.append(f"[{target_language}] {text}")
            
            return translations
        
        # Create test data
        text_elements = {
            "slide1_shape1": "Artificial Intelligence is important",
            "slide1_shape2": "Machine Learning is a subset of AI",
            "slide2_shape1": "This is a test without glossary terms"
        }
        
        slide_metadata = [
            {
                "slide_number": 1,
                "layout": "Title Slide",
                "notes": "Notes about Artificial Intelligence"
            },
            {
                "slide_number": 2,
                "layout": "Content Slide",
                "notes": "Notes about Machine Learning"
            }
        ]
        
        # First translation - with glossary
        print("Translation with glossary:")
        translated1 = translate_text(
            text_elements=text_elements,
            slide_metadata=slide_metadata,
            target_language="ja",
            translate_func=mock_translate,
            source_language="en",
            use_glossary=True
        )
        
        # Print results
        for key, value in translated1.items():
            print(f"  {key}: {value}")
        
        # Second translation - without glossary
        print("\nTranslation without glossary:")
        translated2 = translate_text(
            text_elements=text_elements,
            slide_metadata=slide_metadata,
            target_language="ja",
            translate_func=mock_translate,
            source_language="en",
            use_glossary=False
        )
        
        # Print results
        for key, value in translated2.items():
            print(f"  {key}: {value}")
        
        # Verify that the glossary was applied
        assert "人工知能" in translated1["slide1_shape1"], "Glossary term 'artificial intelligence' should be applied"
        assert "機械学習" in translated1["slide1_shape2"], "Glossary term 'machine learning' should be applied"
        assert "人工知能" in translated1["slide1_notes"], "Glossary term 'artificial intelligence' should be applied to notes"
        assert "機械学習" in translated1["slide2_notes"], "Glossary term 'machine learning' should be applied to notes"
        
        print("Glossary with translator module tests passed!")
    finally:
        # Clean up
        if os.path.exists(glossary_file):
            os.remove(glossary_file)

def main():
    """Main function."""
    print("Testing glossary feature...\n")
    
    # Test the Glossary class
    test_glossary_class()
    
    # Test the glossary functions
    test_glossary_functions()
    
    # Test with translator module
    test_with_translator()
    
    print("\nAll glossary tests passed!")

if __name__ == "__main__":
    main() 