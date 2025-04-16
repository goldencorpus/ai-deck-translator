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

        unique_dict, duplicates_map = deduplicate_content(test_dict)

        # Verify the unique dictionary has only unique content
        self.assertEqual(len(unique_dict), 3)  # 3 unique texts

        # Verify all original keys are represented in the duplicates map
        self.assertEqual(set(duplicates_map.keys()), {"key1", "key3", "key5"})

        # Verify that all duplicate keys map to a representative key
        for dup_key, rep_key in duplicates_map.items():
            self.assertEqual(test_dict[dup_key], test_dict[rep_key])

        # Test with no duplicates
        test_dict_unique = {"key1": "Text 1", "key2": "Text 2", "key3": "Text 3"}

        unique_dict, duplicates_map = deduplicate_content(test_dict_unique)

        # Verify the unique dictionary has all original content
        self.assertEqual(len(unique_dict), 3)

        # Verify the duplicates map is empty
        self.assertEqual(len(duplicates_map), 0)

        # Test with empty dictionary
        unique_dict, duplicates_map = deduplicate_content({})
        self.assertEqual(len(unique_dict), 0)
        self.assertEqual(len(duplicates_map), 0)


if __name__ == "__main__":
    unittest.main()
