"""
Tests for the config module.
"""
import unittest
from unittest.mock import patch, mock_open
import os
import tempfile
from gslides_translator.config import load_config, get_config

class TestConfig(unittest.TestCase):
    """Test cases for the config module."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for config files
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, '.env')
        
        # Sample config data
        self.config_data = """
        ANTHROPIC_API_KEY=test_api_key
        FLASK_SECRET_KEY=test_secret_key
        """
        
        # Reset the config module's state
        from gslides_translator import config
        config._config = {}
    
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_load_config(self, mock_file, mock_exists):
        """Test loading config from a file."""
        # Mock that the config file exists
        mock_exists.return_value = True
        
        # Mock reading the config file
        mock_file.return_value.read.return_value = self.config_data
        
        # Call the function
        config = load_config(self.config_path)
        
        # Verify the config was read
        mock_file.assert_called_with(self.config_path, 'r')
        
        # Verify the config was parsed correctly
        self.assertEqual(config['ANTHROPIC_API_KEY'], 'test_api_key')
        self.assertEqual(config['FLASK_SECRET_KEY'], 'test_secret_key')
    
    @patch('os.path.exists')
    def test_load_config_no_file(self, mock_exists):
        """Test loading config when the file doesn't exist."""
        # Mock that the config file doesn't exist
        mock_exists.return_value = False
        
        # Call the function
        config = load_config(self.config_path)
        
        # Verify an empty config was returned
        self.assertEqual(config, {})
    
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_config(self, mock_file, mock_exists):
        """Test getting a config value."""
        # Mock that the config file exists
        mock_exists.return_value = True
        
        # Mock reading the config file
        mock_file.return_value.read.return_value = self.config_data
        
        # Call the function
        api_key = get_config('ANTHROPIC_API_KEY')
        
        # Verify the config was read
        mock_file.assert_called_with('.env', 'r')
        
        # Verify the correct value was returned
        self.assertEqual(api_key, 'test_api_key')
    
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_config_with_default(self, mock_file, mock_exists):
        """Test getting a config value with a default."""
        # Mock that the config file exists
        mock_exists.return_value = True
        
        # Mock reading the config file
        mock_file.return_value.read.return_value = self.config_data
        
        # Call the function with a key that doesn't exist
        value = get_config('NONEXISTENT_KEY', default='default_value')
        
        # Verify the default value was returned
        self.assertEqual(value, 'default_value')
    
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.environ', {'ANTHROPIC_API_KEY': 'env_api_key'})
    def test_get_config_from_env(self, mock_file, mock_exists):
        """Test getting a config value from environment variables."""
        # Mock that the config file doesn't exist
        mock_exists.return_value = False
        
        # Call the function
        api_key = get_config('ANTHROPIC_API_KEY')
        
        # Verify the correct value was returned from the environment
        self.assertEqual(api_key, 'env_api_key')
    
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.environ', {})
    def test_get_config_missing(self, mock_file, mock_exists):
        """Test getting a missing config value without a default."""
        # Mock that the config file doesn't exist
        mock_exists.return_value = False
        
        # Call the function
        value = get_config('NONEXISTENT_KEY')
        
        # Verify None was returned
        self.assertIsNone(value)

if __name__ == '__main__':
    unittest.main() 