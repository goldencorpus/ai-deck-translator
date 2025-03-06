"""
Tests for the package structure.
"""
import unittest
import importlib
import pkgutil
import gslides_translator

class TestPackage(unittest.TestCase):
    """Test cases for the package structure."""
    
    def test_package_imports(self):
        """Test that all packages and modules can be imported."""
        # Test main package
        self.assertIsNotNone(gslides_translator)
        
        # Test core modules
        self.assertIsNotNone(importlib.import_module('gslides_translator.core.extractor'))
        self.assertIsNotNone(importlib.import_module('gslides_translator.core.translator'))
        self.assertIsNotNone(importlib.import_module('gslides_translator.core.updater'))
        
        # Test auth modules
        self.assertIsNotNone(importlib.import_module('gslides_translator.auth.google_auth'))
        
        # Test utils modules
        self.assertIsNotNone(importlib.import_module('gslides_translator.utils.batch'))
        self.assertIsNotNone(importlib.import_module('gslides_translator.utils.progress'))
        self.assertIsNotNone(importlib.import_module('gslides_translator.utils.recovery'))
        
        # Test web modules
        self.assertIsNotNone(importlib.import_module('gslides_translator.web.app'))
        
        # Test config and run modules
        self.assertIsNotNone(importlib.import_module('gslides_translator.config'))
        self.assertIsNotNone(importlib.import_module('gslides_translator.run'))
    
    def test_package_structure(self):
        """Test that the package structure is correct."""
        # Get all modules in the package
        package_modules = list(pkgutil.walk_packages(
            path=gslides_translator.__path__,
            prefix=gslides_translator.__name__ + '.'
        ))
        
        # Extract module names
        module_names = [module.name for module in package_modules]
        
        # Check for required modules and packages
        required_modules = [
            'gslides_translator.core',
            'gslides_translator.core.extractor',
            'gslides_translator.core.translator',
            'gslides_translator.core.updater',
            'gslides_translator.auth',
            'gslides_translator.auth.google_auth',
            'gslides_translator.utils',
            'gslides_translator.utils.batch',
            'gslides_translator.utils.progress',
            'gslides_translator.utils.recovery',
            'gslides_translator.web',
            'gslides_translator.web.app',
            'gslides_translator.config',
            'gslides_translator.run'
        ]
        
        for module in required_modules:
            self.assertIn(module, module_names, f"Required module {module} not found in package")
    
    def test_version(self):
        """Test that the package has a version."""
        self.assertTrue(hasattr(gslides_translator, '__version__'))
        self.assertIsInstance(gslides_translator.__version__, str)
        
        # Version should be in the format x.y.z
        version_parts = gslides_translator.__version__.split('.')
        self.assertEqual(len(version_parts), 3, "Version should be in the format x.y.z")
        
        # Each part should be a number
        for part in version_parts:
            self.assertTrue(part.isdigit(), f"Version part {part} is not a number")

if __name__ == '__main__':
    unittest.main() 