"""
AI Deck Translator Library

A robust toolkit for translating presentation decks with AI-powered
language translation capabilities.
"""

__version__ = "2.0.0"
__author__ = "Emmanuel Prouveze"
__license__ = "MIT"

# Core translator modules
from .core.translator import translate_slides as translate

# PPTX-specific modules
from .pptx.translator import translate_pptx
from .pptx.enhanced import (
    translate_presentation,
    translate_text,
    translate_batch,
    QUALITY_PROFESSIONAL,
    QUALITY_STANDARD,
    QUALITY_DRAFT,
    QUALITY_ECONOMY,
    MODEL_CLAUDE_35_SONNET,
    MODEL_CLAUDE_35_HAIKU,
    MODEL_GPT_4O,
    MODEL_GPT_4O_MINI,
    MODEL_GEMINI_15_PRO,
    MODEL_GEMINI_15_FLASH,
)

# Utility functions
from .utils.logging import get_logger, set_log_level
from .utils.batch import split_into_batches

__all__ = [
    # Core modules
    "translate",
    # PPTX modules
    "translate_pptx",
    "translate_presentation",
    "translate_text",
    "translate_batch",
    # Quality and model constants
    "QUALITY_PROFESSIONAL",
    "QUALITY_STANDARD",
    "QUALITY_DRAFT",
    "QUALITY_ECONOMY",
    "MODEL_CLAUDE_35_SONNET",
    "MODEL_CLAUDE_35_HAIKU",
    "MODEL_GPT_4O",
    "MODEL_GPT_4O_MINI",
    "MODEL_GEMINI_15_PRO",
    "MODEL_GEMINI_15_FLASH",
    # Utility functions
    "get_logger",
    "set_log_level",
    "split_into_batches",
]
