"""
Tests for the __main__.py module.
"""
import unittest
from unittest.mock import patch, MagicMock
import sys
import importlib

class TestMain(unittest.TestCase):
    """Test cases for the __main__.py module."""
    
    @patch('gslides_translator.run.main')
    def test_main_module(self, mock_main):
        """Test that the __main__.py module calls the main function."""
        # Import the __main__ module
        with patch.object(sys, 'argv', ['gslides_translator']):
            importlib.import_module('gslides_translator.__main__')
        
        # Verify the main function was called
        mock_main.assert_called_once()

if __name__ == '__main__':
    unittest.main() 