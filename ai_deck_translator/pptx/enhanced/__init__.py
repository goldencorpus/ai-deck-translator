"""
Enhanced PPTX translator module with multi-model support, parallel processing, and quality assurance.
"""

from .translator import (  # Constants
    MODEL_CLAUDE_35_HAIKU,
    MODEL_CLAUDE_35_SONNET,
    MODEL_GEMINI_15_FLASH,
    MODEL_GEMINI_15_PRO,
    MODEL_GPT_4O,
    MODEL_GPT_4O_MINI,
    QUALITY_DRAFT,
    QUALITY_ECONOMY,
    QUALITY_PROFESSIONAL,
    QUALITY_STANDARD,
    clear_translation_cache,
    get_cache_stats,
    list_recovery_files,
    translate_batch,
    translate_presentation,
    translate_text,
)

__all__ = [
    "translate_presentation",
    "translate_text",
    "translate_batch",
    "list_recovery_files",
    "clear_translation_cache",
    "get_cache_stats",
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
]
