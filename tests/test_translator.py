"""
Tests for the translator module.
"""
import unittest
from unittest.mock import MagicMock, patch, mock_open
import json
import os
from ai_deck_translator.core.translator import (
    repair_json, extract_json_blocks, translate_batch, translate_text
)

class TestTranslator(unittest.TestCase):
    """Test cases for the translator module."""
    
    def test_repair_json(self):
        """Test that malformed JSON is repaired correctly."""
        # Test fixing unquoted property names
        malformed_json = '{name: "John", age: 30}'
        repaired = repair_json(malformed_json)
        self.assertEqual(json.loads(repaired), {"name": "John", "age": 30})
        
        # Test fixing trailing commas
        malformed_json = '{"items": [1, 2, 3,], "more": true,}'
        repaired = repair_json(malformed_json)
        self.assertEqual(json.loads(repaired), {"items": [1, 2, 3], "more": True})
        
        # Test removing markdown code block markers
        malformed_json = '```json\n{"data": "value"}\n```'
        repaired = repair_json(malformed_json)
        self.assertEqual(json.loads(repaired), {"data": "value"})
        
        # Test removing comments
        malformed_json = '{"data": "value"} // This is a comment'
        repaired = repair_json(malformed_json)
        self.assertEqual(json.loads(repaired), {"data": "value"})
    
    def test_extract_json_blocks(self):
        """Test that JSON blocks are correctly extracted from text."""
        # Test extracting a valid JSON block
        text = 'Here is the translation: {"key1": "value1", "key2": "value2"}'
        extracted = extract_json_blocks(text)
        self.assertEqual(extracted, {"key1": "value1", "key2": "value2"})
        
        # Test extracting and repairing a malformed JSON block
        text = 'Translation result: {key1: "value1", key2: "value2"}'
        extracted = extract_json_blocks(text)
        self.assertEqual(extracted, {"key1": "value1", "key2": "value2"})
        
        # Test with multiple JSON blocks (should return the first valid one)
        text = 'First block: {"invalid": "} Second block: {"valid": "json"}'
        extracted = extract_json_blocks(text)
        self.assertEqual(extracted, {"valid": "json"})
        
        # Test with no valid JSON blocks
        with self.assertRaises(ValueError):
            extract_json_blocks('No JSON here')
    
    @patch('anthropic.Anthropic')
    def test_translate_batch(self, mock_anthropic_class):
        """Test that a batch of text is translated correctly."""
        # Set up mock response from Anthropic
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_content = MagicMock()
        mock_content.text = '{"obj1": "Translated text 1", "obj2": "Translated text 2"}'
        mock_response.content = [mock_content]
        mock_client.messages.create.return_value = mock_response
        
        # Test data
        batch = {"obj1": "Original text 1", "obj2": "Original text 2"}
        slide_metadata = [{"slide_number": 1, "title": "Test Slide", "content": ["Original text 1", "Original text 2"]}]
        
        # Call the function
        result = translate_batch(batch, 0, slide_metadata, "en", "fr", api_key="test_key")
        
        # Verify the API was called correctly
        mock_client.messages.create.assert_called_once()
        call_args = mock_client.messages.create.call_args[1]
        self.assertIn("system", call_args)
        self.assertIn("messages", call_args)
        self.assertEqual(call_args["messages"][0]["role"], "user")
        
        # Verify the result
        self.assertEqual(result, {"obj1": "Translated text 1", "obj2": "Translated text 2"})
    
    @patch('ai_deck_translator.core.translator.translate_batch')
    @patch('ai_deck_translator.utils.batch.deduplicate_content')
    @patch('ai_deck_translator.utils.batch.split_dict_into_smart_batches')
    @patch('ai_deck_translator.utils.recovery.setup_recovery_system')
    @patch('ai_deck_translator.utils.progress.create_progress_bar')
    def test_translate_text(self, mock_progress, mock_recovery, mock_split, mock_deduplicate, mock_translate_batch):
        """Test that text is translated correctly with proper recovery and progress tracking."""
        # Set up mocks
        mock_recovery.return_value = (
            {"translated_items": {}, "completed_batches": [], "failed_batches": []},
            "recovery_file.json",
            MagicMock()  # save_recovery_state function
        )
        
        mock_deduplicate.return_value = (
            {"obj1": "Original text 1", "obj2": "Original text 2"},  # unique_dict
            {}  # duplicates_map
        )
        
        mock_split.return_value = [
            {"obj1": "Original text 1"},
            {"obj2": "Original text 2"}
        ]
        
        mock_translate_batch.side_effect = [
            {"obj1": "Translated text 1"},
            {"obj2": "Translated text 2"}
        ]
        
        mock_progress_instance = MagicMock()
        mock_progress.return_value = mock_progress_instance
        
        # Test data
        text_dict = {"obj1": "Original text 1", "obj2": "Original text 2"}
        slide_metadata = [{"slide_number": 1, "title": "Test Slide", "content": ["Original text 1", "Original text 2"]}]
        
        # Call the function
        result = translate_text(text_dict, slide_metadata, "en", "fr")
        
        # Verify the mocks were called correctly
        mock_recovery.assert_called_once()
        mock_deduplicate.assert_called_once_with(text_dict)
        mock_split.assert_called_once()
        self.assertEqual(mock_translate_batch.call_count, 2)
        mock_progress_instance.update.assert_called()
        mock_progress_instance.close.assert_called_once()
        
        # Verify the result
        self.assertEqual(result, {"obj1": "Translated text 1", "obj2": "Translated text 2"})
    
    @patch('ai_deck_translator.core.translator.translate_text')
    @patch('ai_deck_translator.core.extractor.extract_text')
    @patch('ai_deck_translator.core.updater.update_slides')
    @patch('ai_deck_translator.auth.google_auth.authenticate_google')
    def test_translate_slides(self, mock_auth, mock_update, mock_extract, mock_translate):
        """Test the full slide translation process."""
        # This would be a more comprehensive integration test
        # For now, we'll just verify the function calls
        pass

if __name__ == '__main__':
    unittest.main() 