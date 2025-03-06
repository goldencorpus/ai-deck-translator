"""
AI Deck Translator - Translate presentation decks while preserving formatting.

This package provides tools to automatically translate presentation decks
between different languages while preserving formatting, images, and structure.

Modules:
    auth: Authentication with Google and other services
    core: Core functionality for extraction and translation
    utils: Utility functions for batching, progress tracking, and recovery
    web: Web interface for the translator

Usage:
    from ai_deck_translator import translator
    translator.translate_presentation(presentation_id, source_lang, target_lang)
"""

__version__ = "2.0.0"
__author__ = "Emmanuel Prouveze"
__license__ = "MIT"

# Import key modules for convenience
from ai_deck_translator.core.translator import translate_presentation
from ai_deck_translator.core.extractor import extract_text
from ai_deck_translator.core.updater import update_presentation
