"""
Tests for the batch utilities module.
"""

import unittest
from ai_deck_translator.utils.batch import (
    split_dict_into_smart_batches,
    deduplicate_content,
)
import pytest

try:
    import openai
except ImportError:
    openai = None

pytestmark = pytest.mark.skipif(openai is None, reason="openai package not installed")


class TestBatch(unittest.TestCase):
    """Test cases for the batch utilities module."""

    def test_split_dict_into_smart_batches(self):
        """Test that dictionaries are correctly split into batches based on token count."""
        # Test with a simple dictionary
        test_dict = {
            "key1": "This is a short text",
            "key2": "This is another short text",
            "key3": "This is a longer text that should take more tokens to process",
            "key4": "Short",
            "key5": "This is a very long text "
            + "word " * 100,  # Approximately 100 more tokens
        }

        # Test with default parameters
        batches = split_dict_into_smart_batches(test_dict)

        # Verify we have at least one batch
        self.assertGreater(len(batches), 0)

        # Verify all keys are included across all batches
        all_keys = set()
        for batch in batches:
            all_keys.update(batch.keys())
        self.assertEqual(all_keys, set(test_dict.keys()))

        # Test with custom parameters
        batches = split_dict_into_smart_batches(
            test_dict, max_input_tokens=50, prompt_tokens=20
        )

        # Verify we have more batches with lower token limits
        self.assertGreater(len(batches), 1)

        # Verify all keys are still included
        all_keys = set()
        for batch in batches:
            all_keys.update(batch.keys())
        self.assertEqual(all_keys, set(test_dict.keys()))

        # Test with empty dictionary
        batches = split_dict_into_smart_batches({})
        self.assertEqual(len(batches), 0)

    def test_deduplicate_content(self):
        """Test that content is correctly deduplicated."""
        # Test with duplicate content
        test_dict = {
            "key1": "Duplicate text",
            "key2": "Unique text 1",
            "key3": "Duplicate text",  # Same as key1
            "key4": "Unique text 2",
            "key5": "Duplicate text",  # Same as key1 and key3
        }

        result = deduplicate_content(test_dict)
        unique_dict = result["unique_texts"]
        text_to_ids = result["text_to_ids"]
        id_mapping = result["id_mapping"]

        # Verify the unique dictionary has only unique content
        self.assertEqual(len(unique_dict), 3)  # 3 unique texts

        # Verify all unique texts are represented in the text_to_ids map
        self.assertEqual(
            set(text_to_ids.keys()),
            {"Duplicate text", "Unique text 1", "Unique text 2"},
        )

        # Verify that all original keys are mapped to a unique_id
        for orig_key in test_dict:
            self.assertIn(orig_key, id_mapping)
            unique_id = id_mapping[orig_key]
            self.assertIn(unique_id, unique_dict)
            self.assertEqual(unique_dict[unique_id], test_dict[orig_key])

        # Test with no duplicates
        test_dict_unique = {"key1": "Text 1", "key2": "Text 2", "key3": "Text 3"}

        result = deduplicate_content(test_dict_unique)
        unique_dict = result["unique_texts"]
        text_to_ids = result["text_to_ids"]
        id_mapping = result["id_mapping"]

        # Verify the unique dictionary has all original content
        self.assertEqual(len(unique_dict), 3)

        # Verify the text_to_ids map has all unique texts
        self.assertEqual(set(text_to_ids.keys()), {"Text 1", "Text 2", "Text 3"})

        # Test with empty dictionary
        result = deduplicate_content({})
        unique_dict = result["unique_texts"]
        text_to_ids = result["text_to_ids"]
        id_mapping = result["id_mapping"]
        self.assertEqual(len(unique_dict), 0)
        self.assertEqual(len(text_to_ids), 0)
        self.assertEqual(len(id_mapping), 0)


if __name__ == "__main__":
    unittest.main()
