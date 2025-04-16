"""
Tests for the updater module.
"""

import unittest
from unittest.mock import MagicMock, patch
import webbrowser
from ai_deck_translator.core.updater import update_slides


@patch("webbrowser.open")
class TestUpdater(unittest.TestCase):
    """Test cases for the updater module."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock slides service
        self.mock_slides_service = MagicMock()
        # Create mock drive service
        self.mock_drive_service = MagicMock()

        # Sample data for tests
        self.presentation_id = "test_presentation_123"
        self.text_dict = {
            "slide1_title": "Translated Title",
            "slide1_bullet1": "Translated Bullet 1",
            "slide1_bullet2": "Translated Bullet 2",
            "slide2_title": "Another Translated Title",
            "slide2_table_1_1": "Translated Table Cell",
        }
        self.slide_metadata = [
            {
                "slide_number": 1,
                "slide_id": "slide1",
                "title": "Original Title",
                "elements": [
                    {
                        "id": "title",
                        "type": "shape",
                        "content": ["Original Title"],
                        "object_id": "title1",
                    },
                    {
                        "id": "bullet1",
                        "type": "shape",
                        "content": ["Original Bullet 1"],
                        "object_id": "bullet1",
                    },
                    {
                        "id": "bullet2",
                        "type": "shape",
                        "content": ["Original Bullet 2"],
                        "object_id": "bullet2",
                    },
                ],
            },
            {
                "slide_number": 2,
                "slide_id": "slide2",
                "title": "Another Original Title",
                "elements": [
                    {
                        "id": "title",
                        "type": "shape",
                        "content": ["Another Original Title"],
                        "object_id": "title2",
                    },
                    {
                        "id": "table",
                        "type": "table",
                        "content": [["Original Table Cell"]],
                        "object_id": "table1",
                        "table_cells": [
                            {"row": 0, "column": 0, "content": "Original Table Cell"}
                        ],
                    },
                ],
            },
        ]

    @patch("ai_deck_translator.utils.progress.create_progress_bar")
    def test_update_slides(self, mock_progress, mock_webbrowser):
        """Test that slides are updated correctly."""
        # Set up mock batch update response
        self.mock_slides_service.presentations().batchUpdate().execute.return_value = {
            "replies": [{}]
        }

        # Call the function
        update_slides(
            self.mock_slides_service,
            self.mock_drive_service,
            self.presentation_id,
            self.text_dict,
            self.slide_metadata,
        )

        # Verify the batch update was called twice (original and copy)
        self.assertEqual(
            self.mock_slides_service.presentations().batchUpdate.call_count, 2
        )
        # Get the batch update request for the copy (second call)
        batch_update_request = (
            self.mock_slides_service.presentations().batchUpdate.call_args_list[1][1][
                "body"
            ]
        )
        # Verify the request contains the expected number of requests
        self.assertIn("requests", batch_update_request)
        self.assertGreaterEqual(len(batch_update_request["requests"]), 5)
        for request in batch_update_request["requests"]:
            self.assertIn("replaceAllShapesWithText", request)
            self.assertIn("containsText", request["replaceAllShapesWithText"])
            self.assertIn("replaceText", request["replaceAllShapesWithText"])
            self.assertIn("objectIds", request["replaceAllShapesWithText"])

    @patch("ai_deck_translator.utils.progress.create_progress_bar")
    def test_update_slides_with_web_state(self, mock_progress, mock_webbrowser):
        """Test that slides are updated correctly with web state."""
        self.mock_slides_service.presentations().batchUpdate().execute.return_value = {
            "replies": [{}]
        }
        web_state = {"progress": 0}
        update_slides(
            self.mock_slides_service,
            self.mock_drive_service,
            self.presentation_id,
            self.text_dict,
            self.slide_metadata,
            web_state=web_state,
        )
        self.assertEqual(
            self.mock_slides_service.presentations().batchUpdate.call_count, 2
        )

    @patch("ai_deck_translator.utils.progress.create_progress_bar")
    def test_update_slides_empty_text_dict(self, mock_progress, mock_webbrowser):
        """Test that no updates are made when text_dict is empty."""
        # Call the function with empty text_dict
        update_slides(
            self.mock_slides_service,
            self.mock_drive_service,
            self.presentation_id,
            {},
            self.slide_metadata,
        )

        # Verify the batch update was not called
        self.mock_slides_service.presentations().batchUpdate.assert_not_called()

    @patch("ai_deck_translator.utils.progress.create_progress_bar")
    def test_update_slides_missing_metadata(self, mock_progress, mock_webbrowser):
        """Test that slides are updated correctly even with missing metadata."""
        self.mock_slides_service.presentations().batchUpdate().execute.return_value = {
            "replies": [{}]
        }
        text_dict = {
            "slide1_title": "Translated Title",
            "nonexistent_key": "This doesn't match any metadata",
        }
        update_slides(
            self.mock_slides_service,
            self.mock_drive_service,
            self.presentation_id,
            text_dict,
            self.slide_metadata,
        )
        self.assertEqual(
            self.mock_slides_service.presentations().batchUpdate.call_count, 2
        )
        batch_update_request = (
            self.mock_slides_service.presentations().batchUpdate.call_args_list[1][1][
                "body"
            ]
        )
        self.assertGreaterEqual(len(batch_update_request["requests"]), 1)


if __name__ == "__main__":
    unittest.main()
