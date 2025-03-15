"""
Tests for the web interface module.
"""
import unittest
from unittest.mock import patch, MagicMock, call
import io
import sys
import json
import threading
import time
from ai_deck_translator.web.app import create_app, translate_with_progress, CaptureStdout

class TestWebInterface(unittest.TestCase):
    """Test cases for the web interface module."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a Flask test client
        app = create_app()
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test_key'
        self.client = app.test_client()
        
        # Reset the global translation state
        from ai_deck_translator.web.app import translation_state
        translation_state.clear()
        translation_state.update({
            'running': False,
            'progress': 0,
            'console_output': [],
            'result_url': None
        })
    
    def test_index_route(self):
        """Test that the index route returns the correct template."""
        # Make a request to the index route
        response = self.client.get('/')
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Google Slides Translator', response.data)
        self.assertIn(b'Translation Settings', response.data)
    
    @patch('ai_deck_translator.web.app.translate_with_progress')
    def test_start_translation_valid(self, mock_translate):
        """Test starting a translation with valid input."""
        # Set up the mock
        mock_translate.return_value = None
        
        # Make a request to start a translation
        response = self.client.post('/start_translation', data={
            'presentation_id': 'test_presentation_123',
            'source_language': 'en',
            'target_language': 'fr',
            'api_key': 'test_api_key'
        }, follow_redirects=True)
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Translation started', response.data)
        
        # Verify the translation was started
        mock_translate.assert_called_once()
        args, kwargs = mock_translate.call_args
        self.assertEqual(kwargs['presentation_id'], 'test_presentation_123')
        self.assertEqual(kwargs['source_language'], 'en')
        self.assertEqual(kwargs['target_language'], 'fr')
        self.assertEqual(kwargs['api_key'], 'test_api_key')
    
    def test_start_translation_invalid(self):
        """Test starting a translation with invalid input."""
        # Make a request with missing presentation_id
        response = self.client.post('/start_translation', data={
            'source_language': 'en',
            'target_language': 'fr'
        }, follow_redirects=True)
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Please provide a valid Google Slides presentation ID', response.data)
    
    def test_start_translation_already_running(self):
        """Test starting a translation when one is already running."""
        # Set the translation state to running
        from ai_deck_translator.web.app import translation_state
        translation_state['running'] = True
        
        # Make a request to start a translation
        response = self.client.post('/start_translation', data={
            'presentation_id': 'test_presentation_123',
            'source_language': 'en',
            'target_language': 'fr'
        }, follow_redirects=True)
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'A translation is already running', response.data)
    
    def test_get_progress(self):
        """Test getting the translation progress."""
        # Set the translation state
        from ai_deck_translator.web.app import translation_state
        translation_state.update({
            'running': True,
            'progress': 50,
            'console_output': ['Processing...', 'Translating...'],
            'result_url': 'https://docs.google.com/presentation/d/test'
        })
        
        # Make a request to get the progress
        response = self.client.get('/get_progress')
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['running'], True)
        self.assertEqual(data['progress'], 50)
        self.assertEqual(data['console_output'], ['Processing...', 'Translating...'])
        self.assertEqual(data['result_url'], 'https://docs.google.com/presentation/d/test')
    
    @patch('ai_deck_translator.utils.recovery.list_recovery_files')
    def test_list_recovery_files(self, mock_list_recovery):
        """Test listing recovery files."""
        # Set up the mock
        mock_list_recovery.return_value = [
            {
                'filename': 'recovery_file1.json',
                'path': '/path/to/recovery_file1.json',
                'presentation_id': 'pres1',
                'source_language': 'en',
                'target_language': 'fr',
                'progress': '50%',
                'timestamp': '2023-01-01T12:00:00'
            }
        ]
        
        # Make a request to list recovery files
        response = self.client.get('/list_recovery_files')
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['filename'], 'recovery_file1.json')
    
    def test_capture_stdout(self):
        """Test that CaptureStdout captures stdout correctly."""
        # Create a CaptureStdout instance
        console_output = []
        capture = CaptureStdout(console_output)
        
        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = capture
        
        # Print something
        print("Test output")
        print("Another line")
        
        # Restore stdout
        sys.stdout = old_stdout
        
        # Verify the output was captured
        self.assertEqual(console_output, ["Test output", "Another line"])
    
    @patch('ai_deck_translator.core.translator.translate_slides')
    def test_translate_with_progress(self, mock_translate_slides):
        """Test that translate_with_progress updates the translation state correctly."""
        # Set up the mock
        mock_translate_slides.return_value = "https://docs.google.com/presentation/d/test"
        
        # Get the translation state
        from ai_deck_translator.web.app import translation_state
        
        # Call the function in a thread so it doesn't block
        thread = threading.Thread(target=translate_with_progress, kwargs={
            'presentation_id': 'test_presentation_123',
            'source_language': 'en',
            'target_language': 'fr',
            'api_key': 'test_api_key'
        })
        thread.daemon = True
        thread.start()
        
        # Wait a bit for the thread to start
        time.sleep(0.1)
        
        # Verify the translation state was updated
        self.assertEqual(translation_state['running'], True)
        
        # Wait for the thread to finish
        thread.join(timeout=1.0)
        
        # Verify the translation state was updated again
        self.assertEqual(translation_state['running'], False)
        self.assertEqual(translation_state['result_url'], "https://docs.google.com/presentation/d/test")

if __name__ == '__main__':
    unittest.main() 