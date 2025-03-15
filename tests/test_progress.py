"""
Tests for the progress tracking module.
"""
import unittest
from unittest.mock import patch, MagicMock, call
import io
import sys
from ai_deck_translator.utils.progress import CustomTqdm, WebUITqdm, create_progress_bar

class TestProgress(unittest.TestCase):
    """Test cases for the progress tracking module."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Capture stdout to test progress bar output
        self.stdout_capture = io.StringIO()
        self.old_stdout = sys.stdout
        sys.stdout = self.stdout_capture
    
    def tearDown(self):
        """Tear down test fixtures."""
        # Restore stdout
        sys.stdout = self.old_stdout
    
    def test_custom_tqdm_initialization(self):
        """Test that CustomTqdm initializes correctly."""
        # Create a progress bar with total=100
        progress_bar = CustomTqdm(total=100, desc="Test Progress")
        
        # Verify the progress bar was initialized correctly
        self.assertEqual(progress_bar.total, 100)
        self.assertEqual(progress_bar.n, 0)
        self.assertEqual(progress_bar.description, "Test Progress")
    
    def test_custom_tqdm_update(self):
        """Test that CustomTqdm updates correctly."""
        # Create a progress bar with total=100
        progress_bar = CustomTqdm(total=100)
        
        # Update the progress bar
        progress_bar.update(10)
        
        # Verify the progress bar was updated correctly
        self.assertEqual(progress_bar.n, 10)
        
        # Update again
        progress_bar.update(20)
        
        # Verify the progress bar was updated correctly
        self.assertEqual(progress_bar.n, 30)
    
    def test_custom_tqdm_set_description(self):
        """Test that CustomTqdm sets description correctly."""
        # Create a progress bar with total=100 and initial description
        progress_bar = CustomTqdm(total=100, desc="Test Progress")
        
        # Set a new description
        progress_bar.set_description("New Description")
        
        # Verify the description was updated correctly
        self.assertEqual(progress_bar.description, "New Description")
    
    def test_custom_tqdm_register_callback(self):
        """Test that CustomTqdm registers callbacks correctly."""
        # Create a progress bar with total=100
        progress_bar = CustomTqdm(total=100)
        
        # Create a mock callback function
        callback = MagicMock()
        
        # Register the callback
        progress_bar.register_callback(callback)
        
        # Update the progress bar
        progress_bar.update(30)
        
        # Verify the callback was called with the correct arguments
        self.assertTrue(callback.called)
        self.assertEqual(callback.call_args[0][0], 30)
        
        # Update the progress bar again
        progress_bar.update(20)
        
        # Verify the callback was called again with the correct arguments
        self.assertEqual(callback.call_count, 2)
        # Extract the actual arguments from the call_args_list
        call_args = [args[0][0] for args in callback.call_args_list]
        self.assertEqual(call_args, [30, 50])
    
    def test_custom_tqdm_close(self):
        """Test that CustomTqdm closes correctly."""
        # Create a progress bar with total=100
        progress_bar = CustomTqdm(total=100)
        
        # Update the progress bar
        progress_bar.update(30)
        
        # Close the progress bar
        progress_bar.close()
        
        # Verify the progress bar was closed correctly
        # Note: We can't directly test if tqdm.close() was called, but we can verify
        # that the progress bar is still in a valid state after closing
        self.assertEqual(progress_bar.n, 30)
        self.assertEqual(progress_bar.total, 100)
    
    def test_web_ui_tqdm_initialization(self):
        """Test that WebUITqdm initializes correctly."""
        # Create a web state dictionary
        web_state = {"progress": 0, "total": 0, "console_output": ""}
        
        # Create a progress bar with total=100
        progress_bar = WebUITqdm(total=100, desc="Test Progress", web_state=web_state)
        
        # Verify the progress bar was initialized correctly
        self.assertIsInstance(progress_bar, WebUITqdm)
        self.assertEqual(progress_bar.total, 100)
        self.assertEqual(progress_bar.n, 0)
        self.assertEqual(progress_bar.description, "Test Progress")
        self.assertEqual(progress_bar.web_state, web_state)
        self.assertEqual(web_state["progress"], 0)
    
    def test_web_ui_tqdm_update(self):
        """Test that WebUITqdm updates correctly."""
        # Create a web state dictionary
        web_state = {"progress": 0}
        
        # Create a progress bar with total=100
        progress_bar = WebUITqdm(total=100, web_state=web_state)
        
        # Update the progress bar
        progress_bar.update(10)
        
        # Verify the progress bar was updated correctly
        self.assertEqual(progress_bar.n, 10)
        self.assertEqual(web_state["progress"], 10)
        
        # Update again
        progress_bar.update(20)
        
        # Verify the progress bar was updated correctly
        self.assertEqual(progress_bar.n, 30)
        self.assertEqual(web_state["progress"], 30)
    
    def test_web_ui_tqdm_set_description(self):
        """Test that WebUITqdm sets description correctly (should be a no-op)."""
        # Create a web state dictionary
        web_state = {"progress": 0, "total": 0, "console_output": ""}
        
        # Create a progress bar with total=100
        progress_bar = WebUITqdm(total=100, desc="Test Progress", web_state=web_state)
        
        # Set a new description
        progress_bar.set_description("New Description")
        
        # Verify the description was updated correctly
        self.assertEqual(progress_bar.description, "New Description")
        self.assertIn("New Description", web_state["console_output"])
    
    def test_create_progress_bar_custom(self):
        """Test that create_progress_bar creates a CustomTqdm when web_state is not provided."""
        # Create a progress bar with total=100
        progress_bar = create_progress_bar(total=100, desc="Test Progress")
        
        # Verify the progress bar is a CustomTqdm
        self.assertIsInstance(progress_bar, CustomTqdm)
        self.assertEqual(progress_bar.total, 100)
        self.assertEqual(progress_bar.description, "Test Progress")
    
    def test_create_progress_bar_web(self):
        """Test that create_progress_bar creates a WebUITqdm when web_state is provided."""
        # Create a web state dictionary
        web_state = {"progress": 0, "total": 0, "console_output": ""}
        
        # Create a progress bar with total=100
        progress_bar = create_progress_bar(total=100, desc="Test Progress", web_state=web_state)
        
        # Verify the progress bar is a WebUITqdm
        self.assertIsInstance(progress_bar, WebUITqdm)
        self.assertEqual(progress_bar.total, 100)
        self.assertEqual(progress_bar.description, "Test Progress")
        self.assertEqual(progress_bar.web_state, web_state)
    
    def test_web_ui_tqdm_close(self):
        """Test that WebUITqdm closes correctly."""
        # Create a web state dictionary
        web_state = {"progress": 0, "total": 0, "console_output": ""}
        
        # Create a progress bar with total=100
        progress_bar = WebUITqdm(total=100, desc="Test Progress", web_state=web_state)
        
        # Update the progress bar
        progress_bar.update(30)
        
        # Close the progress bar
        progress_bar.close()
        
        # Verify the progress bar was closed correctly
        # Note: We can't directly test if tqdm.close() was called, but we can verify
        # that the progress bar is still in a valid state after closing
        self.assertEqual(progress_bar.n, 30)
        self.assertEqual(progress_bar.total, 100)
        self.assertEqual(web_state["progress"], 30)

if __name__ == '__main__':
    unittest.main() 