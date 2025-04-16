#!/usr/bin/env python3
"""
Verification script to test our key format enforcement and detection.
"""
import os
import sys
import json
from ai_deck_translator.pptx.translator import verify_translation_keys


def test_key_verification():
    """Test the key verification function."""
    print("Testing key format verification...")

    # Test case 1: Exact match
    original_keys = ["slide1_shape0", "slide1_shape1", "slide1_notes"]
    translated_keys = ["slide1_shape0", "slide1_shape1", "slide1_notes"]

    exact_match, missing_keys, format_changes = verify_translation_keys(
        original_keys, translated_keys
    )

    print("\nTest Case 1: Exact match")
    print(f"Exact match: {exact_match}")
    print(f"Missing keys: {missing_keys}")
    print(f"Format changes: {format_changes}")
    assert exact_match == True, "Should be an exact match"

    # Test case 2: Missing keys
    original_keys = ["slide1_shape0", "slide1_shape1", "slide1_notes"]
    translated_keys = ["slide1_shape0", "slide1_notes"]

    exact_match, missing_keys, format_changes = verify_translation_keys(
        original_keys, translated_keys
    )

    print("\nTest Case 2: Missing keys")
    print(f"Exact match: {exact_match}")
    print(f"Missing keys: {missing_keys}")
    print(f"Format changes: {format_changes}")
    assert exact_match == False, "Should not be an exact match"
    assert "slide1_shape1" in missing_keys, "slide1_shape1 should be missing"

    # Test case 3: Format changes
    original_keys = ["slide1_shape0", "slide1_shape1", "slide1_notes"]
    translated_keys = ["slide_1_element_0", "slide_1_element_1", "slide_1_notes"]

    exact_match, missing_keys, format_changes = verify_translation_keys(
        original_keys, translated_keys
    )

    print("\nTest Case 3: Format changes")
    print(f"Exact match: {exact_match}")
    print(f"Missing keys: {missing_keys}")
    print(f"Format changes: {format_changes}")
    assert exact_match == False, "Should not be an exact match"
    assert len(format_changes) > 0, "Should detect format changes"

    # Test case 4: Mixed issues
    original_keys = ["slide1_shape0", "slide1_shape1", "slide1_notes", "slide2_shape0"]
    translated_keys = ["slide_1_element_0", "slide1_notes", "slide_2_shape_0"]

    exact_match, missing_keys, format_changes = verify_translation_keys(
        original_keys, translated_keys
    )

    print("\nTest Case 4: Mixed issues")
    print(f"Exact match: {exact_match}")
    print(f"Missing keys: {missing_keys}")
    print(f"Format changes: {format_changes}")
    assert exact_match == False, "Should not be an exact match"
    assert "slide1_shape1" in missing_keys, "slide1_shape1 should be missing"
    assert (
        "slide1_shape0" in format_changes
    ), "slide1_shape0 format change should be detected"

    print("\nAll tests passed!")


if __name__ == "__main__":
    test_key_verification()
