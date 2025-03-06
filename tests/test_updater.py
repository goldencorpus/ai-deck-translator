"""
Tests for the updater module.
"""
import unittest
from unittest.mock import MagicMock, patch
from gslides_translator.core.updater import update_slides

class TestUpdater(unittest.TestCase):
    """Test cases for the updater module."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock slides service
        self.mock_slides_service = MagicMock()
        
        # Sample data for tests
        self.presentation_id = "test_presentation_123"
        self.text_dict = {
            "slide1_title": "Translated Title",
            "slide1_bullet1": "Translated Bullet 1",
            "slide1_bullet2": "Translated Bullet 2",
            "slide2_title": "Another Translated Title",
            "slide2_table_1_1": "Translated Table Cell"
        }
        self.slide_metadata = [
            {
                "slide_number": 1,
                "slide_id": "slide1",
                "title": "Original Title",
                "elements": [
                    {"id": "title", "type": "shape", "content": ["Original Title"], "object_id": "title1"},
                    {"id": "bullet1", "type": "shape", "content": ["Original Bullet 1"], "object_id": "bullet1"},
                    {"id": "bullet2", "type": "shape", "content": ["Original Bullet 2"], "object_id": "bullet2"}
                ]
            },
            {
                "slide_number": 2,
                "slide_id": "slide2",
                "title": "Another Original Title",
                "elements": [
                    {"id": "title", "type": "shape", "content": ["Another Original Title"], "object_id": "title2"},
                    {
                        "id": "table", 
                        "type": "table", 
                        "content": [["Original Table Cell"]], 
                        "object_id": "table1",
                        "table_cells": [{"row": 0, "column": 0, "content": "Original Table Cell"}]
                    }
                ]
            }
        ]
    
    @patch('gslides_translator.utils.progress.create_progress_bar')
    def test_update_slides(self, mock_progress):
        """Test that slides are updated correctly."""
        # Set up mock progress bar
        mock_progress_instance = MagicMock()
        mock_progress.return_value = mock_progress_instance
        
        # Set up mock batch update response
        self.mock_slides_service.presentations().batchUpdate().execute.return_value = {"replies": [{}]}
        
        # Call the function
        update_slides(self.mock_slides_service, self.presentation_id, self.text_dict, self.slide_metadata)
        
        # Verify the progress bar was created and used
        mock_progress.assert_called_once()
        mock_progress_instance.update.assert_called()
        mock_progress_instance.close.assert_called_once()
        
        # Verify the batch update was called
        self.mock_slides_service.presentations().batchUpdate.assert_called_once()
        
        # Get the batch update request
        batch_update_request = self.mock_slides_service.presentations().batchUpdate.call_args[1]['body']
        
        # Verify the request contains the expected number of requests
        self.assertIn('requests', batch_update_request)
        
        # We should have at least 5 requests (one for each text element)
        self.assertGreaterEqual(len(batch_update_request['requests']), 5)
        
        # Verify each request is for updating text
        for request in batch_update_request['requests']:
            self.assertIn('insertText', request)
            self.assertIn('objectId', request['insertText'])
            self.assertIn('text', request['insertText'])
            self.assertIn('insertionIndex', request['insertText'])
    
    @patch('gslides_translator.utils.progress.create_progress_bar')
    def test_update_slides_with_web_state(self, mock_progress):
        """Test that slides are updated correctly with web state."""
        # Set up mock progress bar
        mock_progress_instance = MagicMock()
        mock_progress.return_value = mock_progress_instance
        
        # Set up mock batch update response
        self.mock_slides_service.presentations().batchUpdate().execute.return_value = {"replies": [{}]}
        
        # Create a web state dictionary
        web_state = {"progress": 0}
        
        # Call the function with web state
        update_slides(self.mock_slides_service, self.presentation_id, self.text_dict, self.slide_metadata, web_state=web_state)
        
        # Verify the progress bar was created with web state
        mock_progress.assert_called_once_with(total=len(self.text_dict), desc="Updating slides", web_state=web_state)
        
        # Verify the batch update was called
        self.mock_slides_service.presentations().batchUpdate.assert_called_once()
    
    @patch('gslides_translator.utils.progress.create_progress_bar')
    def test_update_slides_empty_text_dict(self, mock_progress):
        """Test that no updates are made when text_dict is empty."""
        # Set up mock progress bar
        mock_progress_instance = MagicMock()
        mock_progress.return_value = mock_progress_instance
        
        # Call the function with empty text_dict
        update_slides(self.mock_slides_service, self.presentation_id, {}, self.slide_metadata)
        
        # Verify the progress bar was created but not updated
        mock_progress.assert_called_once()
        mock_progress_instance.update.assert_not_called()
        mock_progress_instance.close.assert_called_once()
        
        # Verify the batch update was not called
        self.mock_slides_service.presentations().batchUpdate.assert_not_called()
    
    @patch('gslides_translator.utils.progress.create_progress_bar')
    def test_update_slides_missing_metadata(self, mock_progress):
        """Test that slides are updated correctly even with missing metadata."""
        # Set up mock progress bar
        mock_progress_instance = MagicMock()
        mock_progress.return_value = mock_progress_instance
        
        # Set up mock batch update response
        self.mock_slides_service.presentations().batchUpdate().execute.return_value = {"replies": [{}]}
        
        # Create a text_dict with a key that doesn't match any metadata
        text_dict = {
            "slide1_title": "Translated Title",
            "nonexistent_key": "This doesn't match any metadata"
        }
        
        # Call the function
        update_slides(self.mock_slides_service, self.presentation_id, text_dict, self.slide_metadata)
        
        # Verify the progress bar was created and used
        mock_progress.assert_called_once()
        
        # We should have at least one update (for slide1_title)
        self.mock_slides_service.presentations().batchUpdate.assert_called_once()
        batch_update_request = self.mock_slides_service.presentations().batchUpdate.call_args[1]['body']
        self.assertGreaterEqual(len(batch_update_request['requests']), 1)

if __name__ == '__main__':
    unittest.main()