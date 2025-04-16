"""
Batch processing utilities for handling large translations.

This module provides functions for optimizing the processing of large translation
jobs by splitting content into appropriately sized batches and deduplicating content
to reduce API costs and improve efficiency.

Public Functions:
    split_dict_into_smart_batches: Split a dictionary into batches based on token count
    deduplicate_content: Deduplicate content to reduce translation costs
    create_batches: Create batches of elements for processing
    split_into_batches: Split a list into batches of a specified size
"""

from typing import Dict, List, Any, Tuple, TypeVar, Iterable, Iterator, Generic
from ..utils.logging import get_logger
from ..utils.exceptions import ValidationError
from .. import config

# Set up logging
logger = get_logger(__name__)

T = TypeVar("T")


def split_into_batches(items: List[T], batch_size: int) -> List[List[T]]:
    """
    Split a list into batches of a specified size.

    Args:
        items (List[T]): List of items to split into batches
        batch_size (int): Maximum number of items per batch

    Returns:
        List[List[T]]: List of batches, where each batch is a list of items

    Raises:
        ValidationError: If batch_size is invalid

    Example:
        >>> items = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        >>> batches = split_into_batches(items, 3)
        >>> print(batches)
        [[1, 2, 3], [4, 5, 6], [7, 8, 9], [10]]
    """
    if batch_size <= 0:
        raise ValidationError("Batch size must be a positive integer")

    # Create batches
    batches = []
    for i in range(0, len(items), batch_size):
        batches.append(items[i : i + batch_size])

    logger.debug(
        f"Split {len(items)} items into {len(batches)} batches (batch size: {batch_size})"
    )
    return batches


def create_batches(
    ids: List[str], texts: List[str], batch_size: int
) -> List[Tuple[List[str], List[str]]]:
    """
    Create batches of elements for processing.

    This function takes lists of IDs and texts and splits them into batches of the
    specified size. Each batch contains a tuple of (ids, texts) for that batch.

    Args:
        ids (List[str]): List of element IDs
        texts (List[str]): List of text elements corresponding to the IDs
        batch_size (int): Maximum number of elements per batch

    Returns:
        List[Tuple[List[str], List[str]]]: List of batches, where each batch is a tuple
            containing a list of IDs and a list of texts

    Raises:
        ValidationError: If the input lists have different lengths or batch_size is invalid

    Example:
        >>> ids = ["id1", "id2", "id3", "id4", "id5"]
        >>> texts = ["text1", "text2", "text3", "text4", "text5"]
        >>> batches = create_batches(ids, texts, 2)
        >>> print(f"Created {len(batches)} batches")
    """
    # Validate input
    if len(ids) != len(texts):
        raise ValidationError("IDs and texts lists must have the same length")

    if batch_size <= 0:
        raise ValidationError("Batch size must be a positive integer")

    # Create batches
    batches = []
    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i : i + batch_size]
        batch_texts = texts[i : i + batch_size]
        batches.append((batch_ids, batch_texts))

    logger.debug(
        f"Created {len(batches)} batches from {len(ids)} elements (batch size: {batch_size})"
    )
    return batches


def split_dict_into_smart_batches(
    input_dict: Dict[str, str], max_input_tokens: int = None, prompt_tokens: int = None
) -> List[Dict[str, str]]:
    """
    Split a dictionary into batches based on estimated token count to optimize API usage.

    This function takes a dictionary of text content and splits it into multiple smaller
    dictionaries (batches) to ensure each batch stays within token limits for API calls.
    It uses a simple token estimation heuristic based on character count.

    Args:
        input_dict (dict): Dictionary to split into batches, where keys are IDs and
            values are text content to be translated
        max_input_tokens (int, optional): Maximum tokens per batch. If None, uses the
            value from config.MAX_INPUT_TOKENS
        prompt_tokens (int, optional): Estimated tokens used by the prompt template.
            If None, uses the value from config.PROMPT_TOKENS

    Returns:
        list: List of dictionaries (batches), where each dictionary contains a subset
            of the original input_dict that fits within the token limits

    Raises:
        ValidationError: If input_dict is not a dictionary or is empty

    Example:
        >>> text_dict = {"id1": "Hello world", "id2": "This is a long text...", ...}
        >>> batches = split_dict_into_smart_batches(text_dict, max_input_tokens=1000)
        >>> print(f"Split into {len(batches)} batches")
    """
    # Validate input
    if not isinstance(input_dict, dict):
        raise ValidationError("Input must be a dictionary")

    if not input_dict:
        logger.warning("Empty dictionary provided to split_dict_into_smart_batches")
        return []

    # Use default values from config if not provided
    max_input_tokens = max_input_tokens or getattr(config, "MAX_INPUT_TOKENS", 100000)
    prompt_tokens = prompt_tokens or getattr(config, "PROMPT_TOKENS", 1000)

    logger.info(
        f"Splitting dictionary with {len(input_dict)} items into batches (max {max_input_tokens} tokens per batch)"
    )

    # Function to estimate tokens in a string (roughly 4 characters per token)
    def estimate_tokens(text):
        if text is None:
            return 0
        return len(str(text)) // 4 + 1  # Add 1 to round up

    items = list(input_dict.items())
    batches = []
    current_batch = {}
    current_token_count = prompt_tokens

    # Sort items by estimated token length (largest first to optimize packing)
    items.sort(key=lambda x: estimate_tokens(x[1]), reverse=True)

    for key, value in items:
        item_tokens = (
            estimate_tokens(key) + estimate_tokens(value) + 10
        )  # +10 for JSON formatting

        # If this item would exceed the batch limit and we already have items in the batch,
        # finalize the current batch and start a new one
        if current_token_count + item_tokens > max_input_tokens and current_batch:
            batches.append(current_batch)
            current_batch = {}
            current_token_count = prompt_tokens

        # Add the item to the current batch
        current_batch[key] = value
        current_token_count += item_tokens

    # Add the last batch if it has any items
    if current_batch:
        batches.append(current_batch)

    # Log batch statistics
    total_items = len(input_dict)
    batch_sizes = [len(batch) for batch in batches]
    logger.info(f"Split {total_items} items into {len(batches)} batches")
    logger.info(f"Batch sizes: {batch_sizes}")

    return batches


def deduplicate_content(input_dict: Dict[str, str]) -> Dict[str, Any]:
    """
    Deduplicate content to reduce translation costs.

    This function identifies duplicate text content in the input dictionary and
    creates a mapping to ensure each unique text is only translated once. This
    can significantly reduce API costs for presentations with repeated content.

    Args:
        input_dict (dict): Dictionary where keys are IDs and values are text content

    Returns:
        dict: A dictionary containing:
            - unique_texts (dict): Dictionary of unique text content with new IDs
            - text_to_ids (dict): Mapping from unique text to original IDs
            - id_mapping (dict): Mapping from original IDs to unique text IDs

    Raises:
        ValidationError: If input_dict is not a dictionary or is empty

    Example:
        >>> text_dict = {"id1": "Hello", "id2": "World", "id3": "Hello"}
        >>> result = deduplicate_content(text_dict)
        >>> print(f"Reduced from {len(text_dict)} to {len(result['unique_texts'])} items")
    """
    # Validate input
    if not isinstance(input_dict, dict):
        raise ValidationError("Input must be a dictionary")

    if not input_dict:
        logger.warning("Empty dictionary provided to deduplicate_content")
        return {"unique_texts": {}, "text_to_ids": {}, "id_mapping": {}}

    logger.info(f"Deduplicating content from {len(input_dict)} items")

    # Create mappings
    text_to_ids = {}  # Maps text content to list of IDs with that content
    id_mapping = {}  # Maps original IDs to unique text IDs
    unique_texts = {}  # Dictionary of unique text content with new IDs

    # Group IDs by text content
    for item_id, text in input_dict.items():
        if text in text_to_ids:
            text_to_ids[text].append(item_id)
        else:
            text_to_ids[text] = [item_id]

    # Create unique texts dictionary and ID mapping
    for i, (text, ids) in enumerate(text_to_ids.items()):
        unique_id = f"unique_{i}"
        unique_texts[unique_id] = text

        # Map all original IDs to this unique ID
        for original_id in ids:
            id_mapping[original_id] = unique_id

    # Log deduplication statistics
    original_count = len(input_dict)
    unique_count = len(unique_texts)
    reduction = (1 - unique_count / original_count) * 100 if original_count > 0 else 0

    logger.info(
        f"Reduced from {original_count} to {unique_count} items ({reduction:.1f}% reduction)"
    )

    return {
        "unique_texts": unique_texts,
        "text_to_ids": text_to_ids,
        "id_mapping": id_mapping,
    }
