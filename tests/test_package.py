"""
Tests for the package structure.
"""

import unittest
import importlib
import pkgutil
import ai_deck_translator
import pytest

try:
    import openai
except ImportError:
    openai = None

pytestmark = pytest.mark.skipif(openai is None, reason="openai package not installed")


class TestPackage(unittest.TestCase):
    """Test cases for the package structure."""

    def test_package_imports(self):
        """Test that all packages and modules can be imported."""
        # Test main package
        self.assertIsNotNone(ai_deck_translator)

        # Test core modules
        self.assertIsNotNone(
            importlib.import_module("ai_deck_translator.core.extractor")
        )
        self.assertIsNotNone(
            importlib.import_module("ai_deck_translator.core.translator")
        )
        self.assertIsNotNone(importlib.import_module("ai_deck_translator.core.updater"))

        # Test auth modules
        self.assertIsNotNone(
            importlib.import_module("ai_deck_translator.auth.google_auth")
        )

        # Test utils modules
        self.assertIsNotNone(importlib.import_module("ai_deck_translator.utils.batch"))
        self.assertIsNotNone(
            importlib.import_module("ai_deck_translator.utils.progress")
        )
        self.assertIsNotNone(
            importlib.import_module("ai_deck_translator.utils.recovery")
        )

        # Test web modules
        self.assertIsNotNone(importlib.import_module("ai_deck_translator.web.app"))

        # Test config and run modules
        self.assertIsNotNone(importlib.import_module("ai_deck_translator.config"))
        self.assertIsNotNone(importlib.import_module("ai_deck_translator.run"))

    def test_package_structure(self):
        """Test that the package structure is correct."""
        # Get all modules in the package
        package_modules = list(
            pkgutil.walk_packages(
                path=ai_deck_translator.__path__,
                prefix=ai_deck_translator.__name__ + ".",
            )
        )

        # Extract module names
        module_names = [module.name for module in package_modules]

        # Check for required modules and packages
        required_modules = [
            "ai_deck_translator.core",
            "ai_deck_translator.core.extractor",
            "ai_deck_translator.core.translator",
            "ai_deck_translator.core.updater",
            "ai_deck_translator.auth",
            "ai_deck_translator.auth.google_auth",
            "ai_deck_translator.utils",
            "ai_deck_translator.utils.batch",
            "ai_deck_translator.utils.progress",
            "ai_deck_translator.utils.recovery",
            "ai_deck_translator.web",
            "ai_deck_translator.web.app",
            "ai_deck_translator.config",
            "ai_deck_translator.run",
        ]

        for module in required_modules:
            self.assertIn(
                module, module_names, f"Required module {module} not found in package"
            )

    def test_version(self):
        """Test that the package has a version."""
        self.assertTrue(hasattr(ai_deck_translator, "__version__"))
        self.assertIsInstance(ai_deck_translator.__version__, str)

        # Version should be in the format x.y.z
        version_parts = ai_deck_translator.__version__.split(".")
        self.assertEqual(len(version_parts), 3, "Version should be in the format x.y.z")

        # Each part should be a number
        for part in version_parts:
            self.assertTrue(part.isdigit(), f"Version part {part} is not a number")


if __name__ == "__main__":
    unittest.main()
