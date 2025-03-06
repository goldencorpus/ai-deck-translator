"""
Tests for the progress tracking module.
"""
import unittest
from unittest.mock import patch, MagicMock, call
import io
import sys
from gslides_translator.utils.progress import CustomTqdm, WebUITqdm, create_progress_bar

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
        self.assertEqual(progress_bar.desc, "Test Progress")
        self.assertEqual(progress_bar.n, 0)
        self.assertEqual(progress_bar.callbacks, [])
    
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
        # Create a progress bar
        progress_bar = CustomTqdm(total=100)
        
        # Set the description
        progress_bar.set_description("New Description")
        
        # Verify the description was set correctly
        self.assertEqual(progress_bar.desc, "New Description")
    
    def test_custom_tqdm_register_callback(self):
        """Test that CustomTqdm registers callbacks correctly."""
        # Create a mock callback
        mock_callback = MagicMock()
        
        # Create a progress bar
        progress_bar = CustomTqdm(total=100)
        
        # Register the callback
        progress_bar.register_callback(mock_callback)
        
        # Verify the callback was registered
        self.assertEqual(len(progress_bar.callbacks), 1)
        self.assertEqual(progress_bar.callbacks[0], mock_callback)
        
        # Update the progress bar to trigger the callback
        progress_bar.update(10)
        
        # Verify the callback was called
        mock_callback.assert_called_once_with(10, 100)
    
    def test_custom_tqdm_close(self):
        """Test that CustomTqdm closes correctly."""
        # Create a progress bar
        progress_bar = CustomTqdm(total=100)
        
        # Close the progress bar
        progress_bar.close()
        
        # Verify the progress bar was closed (n should be set to total)
        self.assertEqual(progress_bar.n, 100)
    
    def test_web_ui_tqdm_initialization(self):
        """Test that WebUITqdm initializes correctly."""
        # Create a web state dictionary
        web_state = {"progress": 0}
        
        # Create a progress bar with total=100
        progress_bar = WebUITqdm(total=100, desc="Test Progress", web_state=web_state)
        
        # Verify the progress bar was initialized correctly
        self.assertEqual(progress_bar.total, 100)
        self.assertEqual(progress_bar.desc, "Test Progress")
        self.assertEqual(progress_bar.n, 0)
        self.assertEqual(progress_bar.web_state, web_state)
    
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
        web_state = {"progress": 0}
        
        # Create a progress bar
        progress_bar = WebUITqdm(total=100, web_state=web_state)
        
        # Set the description
        progress_bar.set_description("New Description")
        
        # Verify the description was set correctly
        self.assertEqual(progress_bar.desc, "New Description")
    
    def test_create_progress_bar_custom(self):
        """Test that create_progress_bar creates a CustomTqdm when web_state is not provided."""
        # Create a progress bar
        progress_bar = create_progress_bar(total=100, desc="Test Progress")
        
        # Verify the progress bar is a CustomTqdm
        self.assertIsInstance(progress_bar, CustomTqdm)
        self.assertEqual(progress_bar.total, 100)
        self.assertEqual(progress_bar.desc, "Test Progress")
    
    def test_create_progress_bar_web(self):
        """Test that create_progress_bar creates a WebUITqdm when web_state is provided."""
        # Create a web state dictionary
        web_state = {"progress": 0}
        
        # Create a progress bar
        progress_bar = create_progress_bar(total=100, desc="Test Progress", web_state=web_state)
        
        # Verify the progress bar is a WebUITqdm
        self.assertIsInstance(progress_bar, WebUITqdm)
        self.assertEqual(progress_bar.total, 100)
        self.assertEqual(progress_bar.desc, "Test Progress")
        self.assertEqual(progress_bar.web_state, web_state)

if __name__ == '__main__':
    unittest.main() 