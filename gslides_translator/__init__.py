"""
Google Slides Translator - Translate presentation slides while preserving formatting.

This package provides tools to automatically translate Google Slides presentations
between different languages while preserving formatting, images, and slide structure.

Modules:
    auth: Authentication with Google services
    core: Core functionality for extraction and translation
    utils: Utility functions for batching, progress tracking, and recovery
    web: Web interface for the translator

Usage:
    from gslides_translator import translator
    translator.translate_presentation(presentation_id, source_lang, target_lang)
"""

__version__ = "2.0.0"
__author__ = "Emmanuel Prouveze"
__license__ = "MIT"

# Import key modules for convenience
from gslides_translator.core.translator import translate_presentation
from gslides_translator.core.extractor import extract_text
from gslides_translator.core.updater import update_presentation
