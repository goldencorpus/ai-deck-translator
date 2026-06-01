"""
PPTX module for translating PowerPoint presentations.

This module provides functionality for extracting text from PowerPoint presentations,
translating the text, and updating the presentations with the translated text.
"""

from .extractor import extract_text
from .translator import list_recovery_files, translate_pptx, translate_text
from .updater import update_slides

__all__ = [
    "translate_pptx",
    "translate_text",
    "extract_text",
    "update_slides",
    "list_recovery_files",
]
