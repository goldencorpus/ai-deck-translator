"""
Tests for the __main__.py module.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import importlib
import runpy


class TestMain(unittest.TestCase):
    """Test cases for the __main__.py module."""

    @patch("ai_deck_translator.cli.main.main")
    def test_main_module(self, mock_main):
        """Test that the __main__.py module calls the main function."""
        import runpy
        import sys
        from unittest.mock import patch as patch_mock

        with patch_mock.object(
            sys,
            "argv",
            [
                "ai_deck_translator",
                "--input",
                "in",
                "--output",
                "out",
                "--target-language",
                "fr",
            ],
        ):
            runpy.run_module("ai_deck_translator", run_name="__main__")
        mock_main.assert_called_once()


if __name__ == "__main__":
    unittest.main()
