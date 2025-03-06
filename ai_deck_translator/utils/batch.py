"""
Batch processing utilities for handling large translations.
"""
from .. import config

def split_dict_into_smart_batches(input_dict, max_input_tokens=None, prompt_tokens=None):
    """
    Split a dictionary into batches based on estimated token count to optimize API usage.
    
    Args:
        input_dict: Dictionary to split into batches
        max_input_tokens: Maximum tokens per batch (default from config)
        prompt_tokens: Estimated prompt tokens (default from config)
        
    Returns:
        list: List of dictionaries (batches)
    """
    max_input_tokens = max_input_tokens or config.MAX_INPUT_TOKENS
    prompt_tokens = prompt_tokens or config.PROMPT_TOKENS
    
    # Function to estimate tokens in a string (roughly 4 characters per token)
    def estimate_tokens(text):
        if text is None:
            return 0
        return len(str(text)) // 4 + 1  # Add 1 to round up
    
    items = list(input_dict.items())
    batches = []
    current_batch = {}
    current_token_count = prompt_tokens
    
    # Sort items by estimated token length (optional)
    items.sort(key=lambda x: estimate_tokens(x[1]), reverse=True)
    
    for key, value in items:
        item_tokens = estimate_tokens(key) + estimate_tokens(value) + 10  # +10 for JSON formatting
        
        if current_token_count + item_tokens > max_input_tokens and current_batch:
            batches.append(current_batch)
            current_batch = {}
            current_token_count = prompt_tokens
        
        current_batch[key] = value
        current_token_count += item_tokens
    
    if current_batch:
        batches.append(current_batch)
    
    total_items = len(input_dict)
    batch_sizes = [len(batch) for batch in batches]
    avg_batch_size = sum(batch_sizes) / len(batches) if batches else 0
    
    print(f"Created {len(batches)} batches from {total_items} items")
    print(f"Batch sizes: min={min(batch_sizes) if batches else 0}, max={max(batch_sizes) if batches else 0}, avg={avg_batch_size:.1f}")
    print(f"Estimated token usage efficiency: {(sum(batch_sizes)/total_items)*100:.1f}%")
    
    return batches

def deduplicate_content(input_dict):
    """
    Deduplicate content to reduce translation costs.
    
    Args:
        input_dict: Dictionary of content to deduplicate
        
    Returns:
        tuple: (unique_dict, duplicates_map)
            - unique_dict: Dictionary with only unique content
            - duplicates_map: Dictionary mapping duplicate keys to representative keys
    """
    # Create a reverse mapping of content -> keys
    content_to_keys = {}
    for key, content in input_dict.items():
        if content in content_to_keys:
            content_to_keys[content].append(key)
        else:
            content_to_keys[content] = [key]
    
    # Create a map of duplicate keys to their representative key
    duplicates_map = {}
    unique_dict = {}
    
    for content, keys in content_to_keys.items():
        representative_key = keys[0]
        unique_dict[representative_key] = content
        
        # Map all duplicate keys to the representative key
        for key in keys[1:]:
            duplicates_map[key] = representative_key
    
    print(f"Deduplication: {len(input_dict)} items → {len(unique_dict)} unique items")
    print(f"Saved {len(duplicates_map)} duplicate items ({len(duplicates_map)/len(input_dict)*100:.1f}%)")
    
    return unique_dict, duplicates_map 