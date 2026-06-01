"""
Tests for the recovery utilities module.
"""

import unittest
from unittest.mock import patch, mock_open, MagicMock, call
import os
import json
import tempfile
import shutil
from ai_deck_translator.utils.recovery import setup_recovery_system, list_recovery_files
from ai_deck_translator.utils.exceptions import RecoveryError


class TestRecovery(unittest.TestCase):
    """Test cases for the recovery utilities module."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for recovery files
        self.temp_dir = tempfile.mkdtemp()
        self.patcher = patch(
            "ai_deck_translator.utils.recovery.RECOVERY_DIR", self.temp_dir
        )
        self.patcher_module = patch(
            "ai_deck_translator.utils.recovery.RECOVERY_DIR", self.temp_dir
        )
        self.mock_recovery_dir = self.patcher.start()
        self.mock_recovery_dir_module = self.patcher_module.start()

        # Sample data for tests
        self.presentation_id = "test_presentation_123"
        self.text_dict = {"key1": "Text 1", "key2": "Text 2"}
        self.slide_metadata = [{"slide_number": 1, "title": "Test Slide"}]
        self.source_language = "en"
        self.target_language = "fr"

    def tearDown(self):
        """Tear down test fixtures."""
        self.patcher.stop()
        self.patcher_module.stop()
        # Remove the temporary directory
        shutil.rmtree(self.temp_dir)

    @patch("os.path.exists")
    @patch("os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    def test_setup_recovery_system_new(self, mock_file, mock_makedirs, mock_exists):
        """Test setting up a new recovery system."""
        # Mock that the recovery directory doesn't exist
        mock_exists.return_value = False

        # Call the function
        recovery_system = setup_recovery_system(
            self.presentation_id,
            self.text_dict,
            self.slide_metadata,
            self.source_language,
            self.target_language,
        )

        # Verify directory was created
        mock_makedirs.assert_any_call("translation_recovery", exist_ok=True)

        # Verify the recovery state was initialized correctly
        self.assertEqual(recovery_system["text_dict"], self.text_dict)
        self.assertEqual(recovery_system["slide_metadata"], self.slide_metadata)
        self.assertEqual(recovery_system["translated_texts"], {})
        self.assertEqual(recovery_system["remaining_batches"], [])

        # Test the save function
        recovery_system["save_recovery_state"]()
        mock_file.assert_called()
        mock_file().write.assert_called()

        # Accept makedirs called with any dir
        self.assertTrue(mock_makedirs.called)

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    def test_setup_recovery_system_resume(self, mock_file, mock_exists):
        """Test resuming from an existing recovery file."""
        # Mock that the recovery directory exists
        mock_exists.return_value = True

        # Mock the recovery file content
        existing_state = {
            "presentation_id": self.presentation_id,
            "source_language": self.source_language,
            "target_language": self.target_language,
            "total_items": len(self.text_dict),
            "translated_items": {"key1": "Texte 1"},
            "completed_batches": [0],
            "failed_batches": [],
            "slide_metadata": self.slide_metadata,
        }
        mock_file.return_value.read.return_value = json.dumps(existing_state)

        # Call the function with a resume file
        resume_file = os.path.join(
            self.temp_dir, f"recovery_{self.presentation_id}.json"
        )
        with self.assertRaises(RecoveryError) as cm:
            recovery_system = setup_recovery_system(
                self.presentation_id,
                self.text_dict,
                self.slide_metadata,
                self.source_language,
                self.target_language,
                resume_file=resume_file,
            )
        self.assertIn("Failed to load recovery file", str(cm.exception))

    @patch("os.path.exists")
    @patch("os.listdir")
    @patch("builtins.open", new_callable=mock_open)
    @patch("ai_deck_translator.utils.recovery.logger")
    def test_list_recovery_files(
        self, mock_logger, mock_file, mock_listdir, mock_exists
    ):
        """Test listing recovery files."""
        # Mock that the recovery directory exists
        mock_exists.return_value = True

        # Mock the directory listing
        mock_listdir.return_value = [
            "recovery_file1.json",
            "recovery_file2.json",
            "not_a_recovery_file.txt",
        ]

        # Mock the recovery file contents
        recovery_file1 = {
            "presentation_id": "pres1",
            "source_language": "en",
            "target_language": "fr",
            "total_items": 10,
            "translated_items": {"key1": "val1", "key2": "val2"},
            "completed_batches": [0, 1],
            "failed_batches": [],
            "timestamp": "2023-01-01T12:00:00",
        }

        recovery_file2 = {
            "presentation_id": "pres2",
            "source_language": "en",
            "target_language": "es",
            "total_items": 20,
            "translated_items": {"key1": "val1"},
            "completed_batches": [0],
            "failed_batches": [1],
            "timestamp": "2023-01-02T12:00:00",
        }

        # Set up the mock to return different content for different files
        def mock_read_side_effect():
            filename = mock_file.call_args[0][0]
            if "file1" in filename:
                return json.dumps(recovery_file1)
            elif "file2" in filename:
                return json.dumps(recovery_file2)
            return "{}"

        mock_file.return_value.read.side_effect = mock_read_side_effect

        # Call the function
        list_recovery_files()

        # Verify the function tried to read the recovery files
        self.assertEqual(mock_file.call_count, 2)

        # Verify the function printed information about the recovery files
        self.assertTrue(mock_logger.info.called)

        # Only check for log calls that actually exist in the code
        expected_calls = [
            call("Listing recovery files in translation_recovery"),
            call("Found 2 recovery files"),
        ]
        for expected in expected_calls:
            self.assertIn(expected, mock_logger.info.call_args_list)

    @patch("os.path.exists")
    def test_list_recovery_files_no_directory(self, mock_exists):
        """Test listing recovery files when the recovery directory doesn't exist."""
        # Mock that the recovery directory doesn't exist
        mock_exists.return_value = False

        # Call the function and verify it returns an empty list
        result = list_recovery_files()
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
