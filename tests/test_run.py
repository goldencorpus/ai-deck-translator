"""
Tests for the run module.
"""
import unittest
from unittest.mock import patch, MagicMock
import sys
import argparse
from ai_deck_translator.run import parse_args, main
import pytest
try:
    import openai
except ImportError:
    openai = None

pytestmark = pytest.mark.skipif(openai is None, reason="openai package not installed")

class TestRun(unittest.TestCase):
    """Test cases for the run module."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Save the original sys.argv
        self.original_argv = sys.argv
    
    def tearDown(self):
        """Tear down test fixtures."""
        # Restore the original sys.argv
        sys.argv = self.original_argv
    
    def test_parse_args_translate(self):
        """Test parsing arguments for the translate command."""
        # Set up the command line arguments
        sys.argv = [
            'run.py', 'translate',
            '--presentation-id', 'test_presentation_123',
            '--source-language', 'en',
            '--target-language', 'fr',
            '--api-key', 'test_api_key'
        ]
        
        # Call the function
        args = parse_args()
        
        # Verify the arguments were parsed correctly
        self.assertEqual(args.command, 'translate')
        self.assertEqual(args.presentation_id, 'test_presentation_123')
        self.assertEqual(args.source_language, 'en')
        self.assertEqual(args.target_language, 'fr')
        self.assertEqual(args.api_key, 'test_api_key')
        self.assertIsNone(args.resume_file)
    
    def test_parse_args_translate_with_resume(self):
        """Test parsing arguments for the translate command with resume file."""
        # Set up the command line arguments
        sys.argv = [
            'run.py', 'translate',
            '--presentation-id', 'test_presentation_123',
            '--source-language', 'en',
            '--target-language', 'fr',
            '--resume-file', 'recovery_file.json'
        ]
        
        # Call the function
        args = parse_args()
        
        # Verify the arguments were parsed correctly
        self.assertEqual(args.command, 'translate')
        self.assertEqual(args.presentation_id, 'test_presentation_123')
        self.assertEqual(args.source_language, 'en')
        self.assertEqual(args.target_language, 'fr')
        self.assertIsNone(args.api_key)
        self.assertEqual(args.resume_file, 'recovery_file.json')
    
    def test_parse_args_web(self):
        """Test parsing arguments for the web command."""
        # Set up the command line arguments
        sys.argv = ['run.py', 'web', '--port', '8080']
        
        # Call the function
        args = parse_args()
        
        # Verify the arguments were parsed correctly
        self.assertEqual(args.command, 'web')
        self.assertEqual(args.port, 8080)
    
    def test_parse_args_list_recovery(self):
        """Test parsing arguments for the list-recovery command."""
        # Set up the command line arguments
        sys.argv = ['run.py', 'list-recovery']
        
        # Call the function
        args = parse_args()
        
        # Verify the arguments were parsed correctly
        self.assertEqual(args.command, 'list-recovery')
    
    @patch('ai_deck_translator.core.translator.translate_slides')
    @patch('ai_deck_translator.config.get_config')
    def test_main_translate(self, mock_get_config, mock_translate_slides):
        """Test the main function with the translate command."""
        # Set up the command line arguments
        sys.argv = [
            'run.py', 'translate',
            '--presentation-id', 'test_presentation_123',
            '--source-language', 'en',
            '--target-language', 'fr'
        ]
        
        # Mock the config to return an API key
        mock_get_config.return_value = 'test_api_key'
        
        # Mock the translate_slides function
        mock_translate_slides.return_value = 'https://docs.google.com/presentation/d/test'
        
        # Call the function
        main()
        
        # Verify the translate_slides function was called with the correct arguments
        mock_translate_slides.assert_called_once_with(
            'test_presentation_123',
            'en',
            'fr',
            api_key='test_api_key',
            resume_file=None
        )
    
    @patch('ai_deck_translator.web.app.create_app')
    def test_main_web(self, mock_create_app):
        """Test the main function with the web command."""
        # Set up the command line arguments
        sys.argv = ['run.py', 'web', '--port', '8080']
        
        # Mock the create_app function
        mock_app = MagicMock()
        mock_create_app.return_value = mock_app
        
        # Call the function
        main()
        
        # Verify the app was created and run
        mock_create_app.assert_called_once()
        mock_app.run.assert_called_once_with(host='0.0.0.0', port=8080, debug=True)
    
    @patch('ai_deck_translator.utils.recovery.list_recovery_files')
    def test_main_list_recovery(self, mock_list_recovery):
        """Test the main function with the list-recovery command."""
        # Set up the command line arguments
        sys.argv = ['run.py', 'list-recovery']
        
        # Call the function
        main()
        
        # Verify the list_recovery_files function was called
        mock_list_recovery.assert_called_once()

if __name__ == '__main__':
    unittest.main() 