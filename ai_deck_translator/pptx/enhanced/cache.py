"""
Translation caching system for the enhanced PPTX translator.
"""

import hashlib
import json
import os
from datetime import datetime
from typing import Any, Dict, Optional, Union

# Set up cache directory
CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "cache",
)
os.makedirs(CACHE_DIR, exist_ok=True)


def get_translation_cache_key(
    text: str, source_language: str, target_language: str, model: Optional[str] = None
) -> str:
    """
    Generate a unique cache key for a translation.

    Args:
        text: Text to translate
        source_language: Source language code
        target_language: Target language code
        model: Optional model identifier for model-specific caching

    Returns:
        str: Unique cache key
    """
    # Create a hash of the text to ensure uniqueness and reasonable key length
    text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()

    # Include model in the key if provided
    model_suffix = f"_{model}" if model else ""

    # Format: text_hash_source-target_model
    return f"{text_hash}_{source_language}-{target_language}{model_suffix}"


def save_to_translation_cache(
    text: str,
    translation: str,
    source_language: str,
    target_language: str,
    model: Optional[str] = None,
) -> bool:
    """
    Save a translation to the cache.

    Args:
        text: Original text
        translation: Translated text
        source_language: Source language code
        target_language: Target language code
        model: Optional model identifier

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Generate a cache key for this translation
        cache_key = get_translation_cache_key(
            text, source_language, target_language, model
        )

        # Create the cache file path
        cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")

        # Prepare the cache data
        cache_data = {
            "original": text,
            "translation": translation,
            "source_language": source_language,
            "target_language": target_language,
            "model": model,
            "timestamp": datetime.now().isoformat(),
        }

        # Save to file
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)

        return True
    except Exception as e:
        return False


def get_from_translation_cache(
    text: str, source_language: str, target_language: str, model: Optional[str] = None
) -> Optional[str]:
    """
    Get a translation from the cache.

    Args:
        text: Text to translate
        source_language: Source language code
        target_language: Target language code
        model: Optional model identifier

    Returns:
        str: Cached translation or None if not found
    """
    try:
        # Generate a cache key for this translation
        cache_key = get_translation_cache_key(
            text, source_language, target_language, model
        )

        # Create the cache file path
        cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")

        # Check if the cache file exists
        if not os.path.exists(cache_file):
            return None

        # Load the cache data
        with open(cache_file, "r", encoding="utf-8") as f:
            cache_data = json.load(f)

        # Return the translation
        return cache_data.get("translation")
    except Exception as e:
        return None


def clear_translation_cache() -> int:
    """
    Clear the translation cache.

    Returns:
        int: Number of cache entries removed
    """
    try:
        # Count the number of cache files
        cache_files = [f for f in os.listdir(CACHE_DIR) if f.endswith(".json")]
        count = len(cache_files)

        # Remove each cache file
        for file in cache_files:
            os.remove(os.path.join(CACHE_DIR, file))

        return count
    except Exception as e:
        return 0


def get_cache_stats() -> Dict[str, Union[int, float]]:
    """
    Get statistics about the translation cache.

    Returns:
        dict: Dictionary with cache statistics
    """
    try:
        # Get all cache files
        cache_files = [f for f in os.listdir(CACHE_DIR) if f.endswith(".json")]

        # Calculate total size
        total_size = 0
        for file in cache_files:
            total_size += os.path.getsize(os.path.join(CACHE_DIR, file))

        # Calculate average size
        avg_size = total_size / len(cache_files) if cache_files else 0

        return {
            "entry_count": len(cache_files),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "avg_entry_size_bytes": avg_size,
            "avg_entry_size_kb": avg_size / 1024,
        }
    except Exception as e:
        return {
            "entry_count": 0,
            "total_size_bytes": 0,
            "total_size_mb": 0,
            "avg_entry_size_bytes": 0,
            "avg_entry_size_kb": 0,
        }
