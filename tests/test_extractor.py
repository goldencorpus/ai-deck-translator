"""
Tests for the extractor module.
"""

import unittest
from unittest.mock import MagicMock, patch
from ai_deck_translator.core.extractor import extract_text


class TestExtractor(unittest.TestCase):
    """Test cases for the extractor module."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock slides service
        self.mock_service = MagicMock()

        # Mock presentation data
        self.mock_presentation = {
            "slides": [
                {
                    "pageElements": [
                        {
                            "objectId": "title1",
                            "shape": {
                                "text": {
                                    "textElements": [
                                        {"textRun": {"content": "Slide Title"}}
                                    ]
                                }
                            },
                            "transform": {"scaleX": 1.0},
                        },
                        {
                            "objectId": "content1",
                            "shape": {
                                "text": {
                                    "textElements": [
                                        {"textRun": {"content": "Slide Content"}}
                                    ]
                                }
                            },
                        },
                        {
                            "objectId": "table1",
                            "table": {
                                "tableRows": [
                                    {
                                        "tableCells": [
                                            {
                                                "text": {
                                                    "textElements": [
                                                        {
                                                            "textRun": {
                                                                "content": "Table Cell 1"
                                                            }
                                                        }
                                                    ]
                                                }
                                            },
                                            {
                                                "text": {
                                                    "textElements": [
                                                        {
                                                            "textRun": {
                                                                "content": "Table Cell 2"
                                                            }
                                                        }
                                                    ]
                                                }
                                            },
                                        ]
                                    }
                                ]
                            },
                        },
                    ]
                }
            ]
        }

        # Configure the mock service to return the mock presentation
        self.mock_service.presentations().get().execute.return_value = (
            self.mock_presentation
        )

    def test_extract_text(self):
        """Test that text is correctly extracted from a presentation."""
        # Call the function with the mock service
        text_dict, slide_metadata = extract_text(
            self.mock_service, "test_presentation_id"
        )

        # Verify the service was called correctly
        self.mock_service.presentations().get.assert_any_call(
            presentationId="test_presentation_id"
        )

        # Check that the text dictionary contains the expected items
        self.assertEqual(len(text_dict), 4)  # 2 shapes + 2 table cells
        self.assertEqual(text_dict["title1"], "Slide Title")
        self.assertEqual(text_dict["content1"], "Slide Content")
        self.assertEqual(text_dict["table1_r0_c0"], "Table Cell 1")
        self.assertEqual(text_dict["table1_r0_c1"], "Table Cell 2")

        # Check that the slide metadata is correct
        self.assertEqual(len(slide_metadata), 1)  # 1 slide
        self.assertEqual(slide_metadata[0]["slide_number"], 1)
        self.assertEqual(slide_metadata[0]["title"], "Slide Title")
        self.assertEqual(len(slide_metadata[0]["content"]), 4)  # 4 content items

    def test_extract_text_empty_presentation(self):
        """Test extraction from an empty presentation."""
        # Configure the mock service to return an empty presentation
        self.mock_service.presentations().get().execute.return_value = {"slides": []}

        # Call the function with the mock service
        text_dict, slide_metadata = extract_text(
            self.mock_service, "empty_presentation_id"
        )

        # Check that the results are empty
        self.assertEqual(len(text_dict), 0)
        self.assertEqual(len(slide_metadata), 0)

    def test_extract_text_error_handling(self):
        """Test that errors in text extraction are handled gracefully."""
        # Configure the mock service to return a presentation with problematic data
        problematic_presentation = {
            "slides": [
                {
                    "pageElements": [
                        {
                            "objectId": "problem1",
                            "shape": {
                                "text": {
                                    "textElements": [
                                        {
                                            # Missing textRun
                                        }
                                    ]
                                }
                            },
                        }
                    ]
                }
            ]
        }
        self.mock_service.presentations().get().execute.return_value = (
            problematic_presentation
        )

        # Call the function with the mock service
        text_dict, slide_metadata = extract_text(
            self.mock_service, "problematic_presentation_id"
        )

        # Check that the function didn't crash and returned empty results
        self.assertEqual(len(text_dict), 0)
        self.assertEqual(len(slide_metadata), 1)  # Still has the slide, but no content


if __name__ == "__main__":
    unittest.main()
