"""
PPTX module for translating PowerPoint presentations.

This module provides functionality for extracting text from PowerPoint presentations,
translating the text, and updating the presentations with the translated text.
"""

from .translator import translate_pptx, translate_text, list_recovery_files
from .extractor import extract_text
from .updater import update_slides

__all__ = [
    'translate_pptx',
    'translate_text',
    'extract_text',
    'update_slides',
    'list_recovery_files'
]
