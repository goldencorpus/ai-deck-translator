#!/usr/bin/env python3
"""
Simple verification script to test ID format standardization and validation.
"""
import os
import re
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Mock slide metadata for testing
MOCK_SLIDE_METADATA = [
    {"slide_number": 1, "elements": []},
    {"slide_number": 2, "elements": []},
]


def standardize_ids(text_dict, slide_metadata):
    """Standardize ID formats to ensure consistency."""
    logger.info("Standardizing ID formats...")

    standardized_dict = {}
    id_mapping = {}

    # Pattern detection for various ID formats
    patterns = {
        r"^slide(\d+)_shape(\d+)$": lambda m: f"slide{m.group(1)}_shape{m.group(2)}",
        r"^slide_(\d+)_element_(\d+)$": lambda m: f"slide{m.group(1)}_shape{m.group(2)}",
        r"^slide(\d+)_notes$": lambda m: f"slide{m.group(1)}_notes",
        r"^slide_(\d+)_notes$": lambda m: f"slide{m.group(1)}_notes",
        r"^slide(\d+)_shape(\d+)_table_r(\d+)c(\d+)$": lambda m: f"slide{m.group(1)}_shape{m.group(2)}_table_r{m.group(3)}c{m.group(4)}",
        r"^slide_(\d+)_element_(\d+)_r(\d+)_c(\d+)$": lambda m: f"slide{m.group(1)}_shape{m.group(2)}_table_r{m.group(3)}c{m.group(4)}",
    }

    # Process each key in the text dictionary
    for old_id, text in text_dict.items():
        standardized_id = old_id

        # Try to match and standardize the ID
        for pattern, formatter in patterns.items():
            match = re.match(pattern, old_id)
            if match:
                standardized_id = formatter(match)
                break

        # Add to the standardized dictionary and track the mapping
        standardized_dict[standardized_id] = text
        if standardized_id != old_id:
            id_mapping[old_id] = standardized_id
            logger.info(f"Standardized ID: {old_id} -> {standardized_id}")

    # Log results
    if id_mapping:
        logger.info(f"Standardized {len(id_mapping)} IDs to ensure consistency")

    return standardized_dict


def validate_translation_ids(text_dict, translated_dict, slide_metadata):
    """Validate that all IDs in the original text dict have corresponding IDs in the translated dict."""
    logger.info("Validating translation IDs...")

    missing_ids = {}
    fixed_translations = translated_dict.copy()

    # Check for missing IDs
    for original_id in text_dict:
        if original_id not in translated_dict:
            missing_ids[original_id] = text_dict[original_id]
            logger.warning(f"Missing translation for ID: {original_id}")

    # If there are missing IDs, try to fix them by looking for alternative formats
    if missing_ids:
        logger.warning(
            f"Found {len(missing_ids)} missing translations. Attempting to fix..."
        )

        # First, try to match IDs based on the text content
        text_to_translation = {
            text: (id, translation)
            for id, translation in translated_dict.items()
            for orig_id, text in text_dict.items()
            if text == text_dict.get(orig_id)
        }

        for missing_id, text in missing_ids.items():
            if text in text_to_translation:
                similar_id, translation = text_to_translation[text]
                fixed_translations[missing_id] = translation
                logger.info(
                    f"Fixed missing ID {missing_id} by matching content with {similar_id}"
                )

        # Next, try pattern-based fixes
        patterns = {
            (
                r"^slide(\d+)_shape(\d+)$",
                r"^slide_(\d+)_element_(\d+)$",
            ): lambda old, new: re.sub(
                r"^slide(\d+)_shape(\d+)$", r"slide_\1_element_\2", old
            ),
            (
                r"^slide_(\d+)_element_(\d+)$",
                r"^slide(\d+)_shape(\d+)$",
            ): lambda old, new: re.sub(
                r"^slide_(\d+)_element_(\d+)$", r"slide\1_shape\2", old
            ),
            (r"^slide(\d+)_notes$", r"^slide_(\d+)_notes$"): lambda old, new: re.sub(
                r"^slide(\d+)_notes$", r"slide_\1_notes", old
            ),
            (r"^slide_(\d+)_notes$", r"^slide(\d+)_notes$"): lambda old, new: re.sub(
                r"^slide_(\d+)_notes$", r"slide\1_notes", old
            ),
        }

        for missing_id in list(missing_ids.keys()):
            if missing_id in fixed_translations:
                continue

            for (old_pattern, new_pattern), transformer in patterns.items():
                if re.match(old_pattern, missing_id):
                    # Try to find a matching ID in the translated dict
                    transformed_id = transformer(missing_id, new_pattern)
                    if transformed_id in translated_dict:
                        fixed_translations[missing_id] = translated_dict[transformed_id]
                        logger.info(
                            f"Fixed missing ID {missing_id} -> {transformed_id}"
                        )
                        break

        # Check how many IDs we fixed
        fixed_count = sum(1 for id in missing_ids if id in fixed_translations)
        if fixed_count > 0:
            logger.info(
                f"Fixed {fixed_count} of {len(missing_ids)} missing translations"
            )

        # Final check for still missing IDs
        still_missing = [id for id in missing_ids if id not in fixed_translations]
        if still_missing:
            logger.warning(
                f"Still missing {len(still_missing)} translations after fixes"
            )
            for id in still_missing[:5]:  # Show only first few to avoid log spam
                logger.warning(f"  Missing: {id}")
            if len(still_missing) > 5:
                logger.warning(f"  ... and {len(still_missing) - 5} more")

    success = len(missing_ids) == 0 or all(
        id in fixed_translations for id in missing_ids
    )
    return success, missing_ids, fixed_translations


def test_standardization():
    """Test the ID standardization function."""
    print("Testing ID standardization...")

    # Original text dictionary (extraction format)
    text_dict = {
        "slide1_shape0": "Test Presentation",
        "slide1_shape1": "Testing ID Format Standardization",
        "slide1_notes": "These are speaker notes for the title slide.",
        "slide2_shape0": "Content Slide",
        "slide2_shape1": "This is a bullet point\nThis is another bullet point",
        "slide2_notes": "These are speaker notes for the content slide.",
    }

    # Translated text dictionary (different format)
    translated_dict = {
        "slide_1_element_0": "[Translated] Test Presentation",
        "slide_1_element_1": "[Translated] Testing ID Format Standardization",
        "slide_1_notes": "[Translated] These are speaker notes for the title slide.",
        "slide_2_element_0": "[Translated] Content Slide",
        "slide_2_element_1": "[Translated] This is a bullet point\nThis is another bullet point",
        "slide_2_notes": "[Translated] These are speaker notes for the content slide.",
    }

    # Print original dictionaries
    print("\nOriginal text dictionary (extraction format):")
    for key, value in text_dict.items():
        print(f"  {key}: {value}")

    print("\nTranslated dictionary (different format):")
    for key, value in translated_dict.items():
        print(f"  {key}: {value}")

    # Standardize the original text dictionary
    standardized_dict = standardize_ids(text_dict, MOCK_SLIDE_METADATA)

    # Validate and fix the translations
    success, missing_ids, fixed_translations = validate_translation_ids(
        standardized_dict, translated_dict, MOCK_SLIDE_METADATA
    )

    # Print results
    print("\nStandardized dictionary:")
    for key, value in standardized_dict.items():
        print(f"  {key}: {value}")

    print(f"\nValidation {'succeeded' if success else 'failed'}")
    if missing_ids:
        print(f"Missing IDs: {len(missing_ids)}")
        for id in missing_ids:
            print(f"  {id}: {text_dict[id]}")

    print("\nFixed translations:")
    for key, value in fixed_translations.items():
        print(f"  {key}: {value}")

    # Summary
    if all(key in fixed_translations for key in text_dict):
        print("\n✅ Success! All text elements have matching translations.")
    else:
        print("\n❌ Failed! Some text elements don't have translations.")
        missing = [key for key in text_dict if key not in fixed_translations]
        for key in missing:
            print(f"  Missing: {key}")


if __name__ == "__main__":
    test_standardization()
