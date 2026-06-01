"""
Utility functions for the enhanced PPTX translator.
"""

import hashlib
import json
import os
import re
from typing import Any, Dict, Optional, Union

# Model constants for cost estimation
from .models.base import (
    MODEL_CLAUDE_35_HAIKU,
    MODEL_CLAUDE_35_SONNET,
    MODEL_GEMINI_15_FLASH,
    MODEL_GEMINI_15_PRO,
    MODEL_GPT_4O,
    MODEL_GPT_4O_MINI,
)


def repair_json(json_content: str) -> str:
    """
    Repair malformed JSON returned by the translation API.

    Args:
        json_content: String containing potentially malformed JSON

    Returns:
        str: Repaired JSON string
    """
    # Remove any markdown code block markers
    json_content = re.sub(r"```json\s*", "", json_content)
    json_content = re.sub(r"\s*```", "", json_content)

    # Fix missing quotes around property names
    json_content = re.sub(r"(\s*?)(\w+)(:)", r'\1"\2"\3', json_content)

    # Fix trailing commas in arrays and objects
    json_content = re.sub(r",\s*}", "}", json_content)
    json_content = re.sub(r",\s*\]", "]", json_content)

    # Fix missing quotes around string values
    def fix_property_names(match):
        prop_name = match.group(1)
        colon = match.group(2)
        value = match.group(3).strip()

        # If value is not already quoted and not a number, boolean, null, array or object
        if not (
            value.startswith('"')
            or value.startswith("'")
            or value.startswith("[")
            or value.startswith("{")
            or value == "null"
            or value == "true"
            or value == "false"
            or re.match(r"^-?\d+(\.\d+)?$", value)
        ):
            return f'"{prop_name}"{colon}"{value}"'
        return f'"{prop_name}"{colon}{value}'

    json_content = re.sub(
        r'"(\w+)"(\s*:)\s*([^",\{\[\]\}\s][^,\{\[\]\}\s]*)',
        fix_property_names,
        json_content,
    )

    return json_content


def extract_json_blocks(text: str) -> Optional[str]:
    """
    Extract JSON blocks from text returned by the translation API.

    Args:
        text: Text containing JSON blocks

    Returns:
        str: The first valid JSON block found, or None if none found
    """
    # Try to find JSON blocks with or without code markers
    patterns = [
        r"```json\s*([\s\S]*?)\s*```",  # JSON with markdown code markers
        r"```\s*([\s\S]*?)\s*```",  # Any code block
        r'(\{\s*"[^"]+"\s*:[\s\S]*\})',  # Raw JSON object
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text)
        if matches:
            for match in matches:
                # Try to parse the match as JSON
                try:
                    json_str = repair_json(match)
                    json.loads(json_str)
                    return json_str
                except:
                    continue

    # If no valid JSON found, try to extract the entire response
    try:
        json_str = repair_json(text)
        json.loads(json_str)
        return json_str
    except:
        return None


def get_model_pricing(model: str) -> Dict[str, float]:
    """
    Get pricing information for a specific model.

    Args:
        model: Model identifier

    Returns:
        dict: Dictionary with input and output costs per million tokens
    """
    pricing = {
        MODEL_CLAUDE_35_SONNET: {
            "input": 3.00,
            "output": 15.00,
            "context_window": 200000,
        },
        MODEL_CLAUDE_35_HAIKU: {
            "input": 1.00,
            "output": 5.00,
            "context_window": 200000,
        },
        MODEL_GPT_4O: {"input": 2.50, "output": 10.00, "context_window": 128000},
        MODEL_GPT_4O_MINI: {"input": 0.15, "output": 6.00, "context_window": 128000},
        MODEL_GEMINI_15_PRO: {"input": 1.25, "output": 2.50, "context_window": 1000000},
        MODEL_GEMINI_15_FLASH: {
            "input": 0.075,
            "output": 0.30,
            "context_window": 1000000,
        },
    }

    # Default to Claude 3.5 Sonnet if model not found
    return pricing.get(model, pricing[MODEL_CLAUDE_35_SONNET])


def estimate_cost(
    prompt_tokens: int, completion_tokens: int, model: str = MODEL_CLAUDE_35_SONNET
) -> float:
    """
    Estimate cost of API call based on token counts and model.

    Args:
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens
        model: Model identifier

    Returns:
        float: Estimated cost in USD
    """
    pricing = get_model_pricing(model)

    # For Gemini models, adjust pricing based on context length
    if model.startswith("gemini") and prompt_tokens > 128000:
        input_cost_per_million = pricing["input"] * 2  # Double for longer contexts
        output_cost_per_million = pricing["output"] * 2  # Double for longer contexts
    else:
        input_cost_per_million = pricing["input"]
        output_cost_per_million = pricing["output"]

    input_cost = (prompt_tokens / 1000000) * input_cost_per_million
    output_cost = (completion_tokens / 1000000) * output_cost_per_million

    return input_cost + output_cost


def clean_text(text: str) -> str:
    """
    Clean text for better translation results.

    Args:
        text: Text to clean

    Returns:
        str: Cleaned text
    """
    return re.sub(r"\s+", " ", text).strip()
