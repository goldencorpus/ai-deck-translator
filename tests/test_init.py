"""
Tests for the __init__.py module.
"""
import unittest
import ai_deck_translator
import pytest
try:
    import openai
except ImportError:
    openai = None

pytestmark = pytest.mark.skipif(openai is None, reason="openai package not installed")

class TestInit(unittest.TestCase):
    """Test cases for the __init__.py module."""
    
    def test_version(self):
        """Test that the __version__ attribute is defined."""
        self.assertTrue(hasattr(gslides_translator, '__version__'))
        self.assertIsInstance(gslides_translator.__version__, str)
    
    def test_author(self):
        """Test that the __author__ attribute is defined."""
        self.assertTrue(hasattr(gslides_translator, '__author__'))
        self.assertIsInstance(gslides_translator.__author__, str)
    
    def test_description(self):
        """Test that the __description__ attribute is defined."""
        self.assertTrue(hasattr(gslides_translator, '__description__'))
        self.assertIsInstance(gslides_translator.__description__, str)
    
    def test_imports(self):
        """Test that the package imports work correctly."""
        # Test importing the main modules
        from ai_deck_translator import config
        from ai_deck_translator import run
        
        # Test importing the core modules
        from ai_deck_translator.core import extractor
        from ai_deck_translator.core import translator
        from ai_deck_translator.core import updater
        
        # Test importing the auth modules
        from ai_deck_translator.auth import google_auth
        
        # Test importing the utils modules
        from ai_deck_translator.utils import batch
        from ai_deck_translator.utils import progress
        from ai_deck_translator.utils import recovery
        
        # Test importing the web modules
        from ai_deck_translator.web import app
        
        # Verify the imports worked
        self.assertIsNotNone(config)
        self.assertIsNotNone(run)
        self.assertIsNotNone(extractor)
        self.assertIsNotNone(translator)
        self.assertIsNotNone(updater)
        self.assertIsNotNone(google_auth)
        self.assertIsNotNone(batch)
        self.assertIsNotNone(progress)
        self.assertIsNotNone(recovery)
        self.assertIsNotNone(app)

if __name__ == '__main__':
    unittest.main() 