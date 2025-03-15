"""
AI Deck Translator - Translate presentation slides while preserving formatting.

This package provides tools to automatically translate presentations (Google Slides and PowerPoint)
between different languages while preserving formatting, images, and slide structure.

Modules:
    auth: Authentication with Google services
    core: Core functionality for extraction and translation of Google Slides
    pptx: Functionality for working with PowerPoint (.pptx) files
    utils: Utility functions for batching, progress tracking, and recovery
    web: Web interface for the translator

Usage:
    # For Google Slides
    from ai_deck_translator.core import translator
    translator.translate_slides(presentation_id, source_lang, target_lang)
    
    # For PowerPoint files
    from ai_deck_translator.pptx import translator as pptx_translator
    pptx_translator.translate_pptx(input_file, output_file, source_lang, target_lang)
"""

__version__ = "2.0.0"
__author__ = "Emmanuel Prouveze"
__license__ = "MIT"

# Import key modules for convenience - commented out to avoid circular imports
# These can be imported directly by users as shown in the usage examples above
# from ai_deck_translator.core.translator import translate_slides
# from ai_deck_translator.core.extractor import extract_text
# from ai_deck_translator.core.updater import update_slides

# These will be available after implementing the PPTX module
# from ai_deck_translator.pptx.translator import translate_pptx
# from ai_deck_translator.pptx.extractor import extract_text as extract_pptx_text
# from ai_deck_translator.pptx.updater import update_slides as update_pptx_slides
