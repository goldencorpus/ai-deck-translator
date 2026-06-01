"""
PPTX Translator module for translating PowerPoint presentations.
"""

import os
import json
import anthropic
import re
import time
from datetime import datetime
from tqdm import tqdm
import sys

from .. import config
from ..utils.batch import split_dict_into_smart_batches, deduplicate_content
from ..utils.recovery import setup_recovery_system
from ..utils.progress import create_progress_bar
from ..utils.logging import get_logger
from ..utils.exceptions import IncompleteTranslationError, TranslationError
from .extractor import extract_text
from .updater import update_slides

# Set up logging
logger = get_logger(__name__)


def repair_json(json_content):
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


def extract_json_blocks(text):
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

    def _valid(candidate):
        try:
            json.loads(candidate)
            return True
        except Exception:
            return False

    for pattern in patterns:
        for match in re.findall(pattern, text):
            # Prefer the model's JSON verbatim. repair_json is a destructive last
            # resort: its regexes mangle valid JSON whose string values contain colons
            # (e.g. "https://...") — only apply it when the JSON is genuinely broken.
            if _valid(match):
                return match
            repaired = repair_json(match)
            if _valid(repaired):
                return repaired

    # If no valid JSON found, try to extract the entire response
    if _valid(text):
        return text
    repaired = repair_json(text)
    if _valid(repaired):
        return repaired
    return None


def standardize_ids(text_dict, slide_metadata):
    """
    Standardize ID formats to ensure consistency between extraction and updating.

    Args:
        text_dict: Dictionary of text elements
        slide_metadata: Metadata about slides

    Returns:
        dict: Dictionary with standardized IDs
    """
    logger.info("Standardizing ID formats...")

    standardized_dict = {}
    id_mapping = {}

    # Pattern detection for various ID formats
    patterns = {
        r"^slide(\d+)_shape(\d+)$": lambda m: f"slide{m.group(1)}_shape{m.group(2)}",
        r"^slide_(\d+)_element_(\d+)$": lambda m: f"slide{m.group(1)}_shape{m.group(2)}",
        r"^slide(\d+)_notes$": lambda m: f"slide{m.group(1)}_notes",
        r"^slide_(\d+)_notes$": lambda m: f"slide{m.group(1)}_notes",
        r"^slide(\d+)_shape(\d+)_table_r(\d+)c(\d+)$": lambda m: f"slide{m.group(1)}_shape{m.group(2)}_table_r{m.group(3)}c{m.group(4)}",
        r"^slide_(\d+)_element_(\d+)_r(\d+)_c(\d+)$": lambda m: f"slide{m.group(1)}_shape{m.group(2)}_table_r{m.group(3)}c{m.group(4)}",
        r"^slide(\d+)_smartart_(.+)$": lambda m: f"slide{m.group(1)}_smartart_{m.group(2)}",
        r"^slide_(\d+)_smartart_(.+)$": lambda m: f"slide{m.group(1)}_smartart_{m.group(2)}",
        r"^slide(\d+)_xml_(.+)$": lambda m: f"slide{m.group(1)}_xml_{m.group(2)}",
        r"^slide_(\d+)_xml_(.+)$": lambda m: f"slide{m.group(1)}_xml_{m.group(2)}",
    }

    # Process each key in the text dictionary
    for old_id, text in text_dict.items():
        standardized_id = old_id

        # Try to match and standardize the ID
        for pattern, formatter in patterns.items():
            match = re.match(pattern, old_id)
            if match:
                standardized_id = formatter(match)
                break

        # Add to the standardized dictionary and track the mapping
        standardized_dict[standardized_id] = text
        if standardized_id != old_id:
            id_mapping[old_id] = standardized_id
            logger.debug(f"Standardized ID: {old_id} -> {standardized_id}")

    # Log results
    if id_mapping:
        logger.info(f"Standardized {len(id_mapping)} IDs to ensure consistency")

    return standardized_dict


def validate_translation_ids(text_dict, translated_dict, slide_metadata):
    """
    Validate that all IDs in the original text dict have corresponding IDs in the translated dict.

    Args:
        text_dict: Dictionary of original text elements
        translated_dict: Dictionary of translated text elements
        slide_metadata: Metadata about slides

    Returns:
        tuple: (bool for success, dict of missing IDs, dict of fixed translations)
    """
    logger.info("Validating translation IDs...")

    missing_ids = {}
    fixed_translations = translated_dict.copy()

    # Check for missing IDs
    for original_id in text_dict:
        if original_id not in translated_dict:
            missing_ids[original_id] = text_dict[original_id]
            logger.warning(f"Missing translation for ID: {original_id}")

    # If there are missing IDs, try to fix them by looking for alternative formats
    if missing_ids:
        logger.warning(
            f"Found {len(missing_ids)} missing translations. Attempting to fix..."
        )

        # Create a mapping of original text to (original_id, text) for content matching
        orig_text_to_id = {text: (id, text) for id, text in text_dict.items()}

        # First, try to match based on key format pattern matches
        patterns = {
            (
                r"^slide(\d+)_shape(\d+)$",
                r"^slide_(\d+)_element_(\d+)$",
            ): lambda old, new: re.sub(
                r"^slide(\d+)_shape(\d+)$", r"slide_\1_element_\2", old
            ),
            (
                r"^slide_(\d+)_element_(\d+)$",
                r"^slide(\d+)_shape(\d+)$",
            ): lambda old, new: re.sub(
                r"^slide_(\d+)_element_(\d+)$", r"slide\1_shape\2", old
            ),
            (r"^slide(\d+)_notes$", r"^slide_(\d+)_notes$"): lambda old, new: re.sub(
                r"^slide(\d+)_notes$", r"slide_\1_notes", old
            ),
            (r"^slide_(\d+)_notes$", r"^slide(\d+)_notes$"): lambda old, new: re.sub(
                r"^slide_(\d+)_notes$", r"slide\1_notes", old
            ),
            (
                r"^slide(\d+)_shape(\d+)_table_r(\d+)c(\d+)$",
                r"^slide_(\d+)_element_(\d+)_r(\d+)_c(\d+)$",
            ): lambda old, new: re.sub(
                r"^slide(\d+)_shape(\d+)_table_r(\d+)c(\d+)$",
                r"slide_\1_element_\2_r\3_c\4",
                old,
            ),
            (
                r"^slide_(\d+)_element_(\d+)_r(\d+)_c(\d+)$",
                r"^slide(\d+)_shape(\d+)_table_r(\d+)c(\d+)$",
            ): lambda old, new: re.sub(
                r"^slide_(\d+)_element_(\d+)_r(\d+)_c(\d+)$",
                r"slide\1_shape\2_table_r\3c\4",
                old,
            ),
        }

        # Apply the pattern-based transformations
        pattern_transformations = {}
        for missing_id in list(missing_ids.keys()):
            for (old_pattern, new_pattern), transformer in patterns.items():
                if re.match(old_pattern, missing_id):
                    transformed_id = transformer(missing_id, new_pattern)
                    if transformed_id in translated_dict:
                        pattern_transformations[missing_id] = transformed_id
                        break

        # Apply transformations and update missing IDs
        for missing_id, transformed_id in pattern_transformations.items():
            if transformed_id in translated_dict:
                fixed_translations[missing_id] = translated_dict[transformed_id]
                logger.debug(
                    f"Fixed missing ID with pattern transform: {missing_id} -> {transformed_id}"
                )
                if missing_id in missing_ids:
                    del missing_ids[missing_id]

        # For any remaining missing IDs, try normalized matching
        if missing_ids:
            # Create normalized keys to help with matching
            def normalize_key(key):
                return re.sub(r"[_\s]", "", key.lower())

            normalized_trans_keys = {
                normalize_key(k): k for k in translated_dict.keys()
            }

            for missing_id in list(missing_ids.keys()):
                if missing_id in fixed_translations:
                    continue

                norm_missing = normalize_key(missing_id)
                if norm_missing in normalized_trans_keys:
                    trans_key = normalized_trans_keys[norm_missing]
                    fixed_translations[missing_id] = translated_dict[trans_key]
                    logger.debug(
                        f"Fixed missing ID with normalized key: {missing_id} -> {trans_key}"
                    )
                    if missing_id in missing_ids:
                        del missing_ids[missing_id]

        # For any still missing IDs, try positional matching based on slide/element numbers
        if missing_ids:
            # Extract slide/shape numbers from IDs for better matching
            def extract_numbers(key):
                slide_match = re.search(r"slide[_]?(\d+)", key)
                element_match = re.search(r"(shape|element)[_]?(\d+)", key)

                slide_num = int(slide_match.group(1)) if slide_match else 0
                element_num = int(element_match.group(2)) if element_match else -1

                return (slide_num, element_num)

            # Group keys by slide/element numbers
            trans_by_position = {}
            for k in translated_dict.keys():
                try:
                    pos = extract_numbers(k)
                    if pos not in trans_by_position:
                        trans_by_position[pos] = []
                    trans_by_position[pos].append(k)
                except (AttributeError, ValueError, IndexError):
                    continue

            # Match missing IDs by position
            for missing_id in list(missing_ids.keys()):
                if missing_id in fixed_translations:
                    continue

                try:
                    pos = extract_numbers(missing_id)
                    if pos in trans_by_position and trans_by_position[pos]:
                        trans_key = trans_by_position[pos][0]
                        fixed_translations[missing_id] = translated_dict[trans_key]
                        logger.debug(
                            f"Fixed missing ID with positional match: {missing_id} -> {trans_key}"
                        )
                        if missing_id in missing_ids:
                            del missing_ids[missing_id]
                except (AttributeError, ValueError, IndexError):
                    continue

        # Check how many IDs we fixed
        fixed_count = len(missing_ids) - len(
            [id for id in missing_ids if id not in fixed_translations]
        )
        if fixed_count > 0:
            logger.info(
                f"Fixed {fixed_count} of {len(missing_ids)} missing translations"
            )

        # Final check for still missing IDs
        still_missing = [id for id in missing_ids if id not in fixed_translations]
        if still_missing:
            logger.warning(
                f"Still missing {len(still_missing)} translations after fixes"
            )
            for id in still_missing[:5]:  # Show only first few to avoid log spam
                logger.warning(f"  Missing: {id}")
            if len(still_missing) > 5:
                logger.warning(f"  ... and {len(still_missing) - 5} more")

    success = len(missing_ids) == 0 or all(
        id in fixed_translations for id in missing_ids
    )
    return success, missing_ids, fixed_translations


def verify_translation_keys(original_keys, translated_keys):
    """
    Verify that translation keys in API response match the input keys exactly.

    Args:
        original_keys: Set of keys in the original request
        translated_keys: Set of keys in the API response

    Returns:
        tuple: (bool for exact match, set of missing keys, set of changed keys)
    """
    # Check for exact matches
    missing_keys = set(original_keys) - set(translated_keys)

    # Check for format changes
    format_changes = {}

    # Create normalized versions of the keys for comparison
    normalized_orig = {k.lower().replace("_", ""): k for k in original_keys}
    normalized_trans = {k.lower().replace("_", ""): k for k in translated_keys}

    # Helper function to normalize key formats for comparison
    def normalize_for_comparison(key):
        # Remove all underscores and convert to lowercase
        basic = key.lower().replace("_", "")
        # Replace common format variations
        for pattern, replacement in [
            ("slide", "s"),
            ("element", "shape"),
            ("shape", "sh"),
            ("notes", "n"),
        ]:
            basic = basic.replace(pattern, replacement)
        return basic

    # Build lookup dictionaries with normalized keys
    advanced_norm_orig = {normalize_for_comparison(k): k for k in original_keys}
    advanced_norm_trans = {normalize_for_comparison(k): k for k in translated_keys}

    # Find format changes - first using simple normalization
    for orig_norm, orig_key in normalized_orig.items():
        # Skip if key is already present in translated keys
        if orig_key in translated_keys:
            continue

        # Skip if key is in missing keys and not found in any normalized form
        if orig_key in missing_keys and orig_norm not in normalized_trans:
            continue

        # Check if normalized key exists in translated keys
        if orig_norm in normalized_trans:
            format_changes[orig_key] = normalized_trans[orig_norm]
            if orig_key in missing_keys:
                missing_keys.remove(orig_key)

    # If we still have missing keys, try advanced normalization
    if missing_keys:
        remaining_missing = set()
        for orig_key in missing_keys:
            norm_key = normalize_for_comparison(orig_key)
            if norm_key in advanced_norm_trans:
                format_changes[orig_key] = advanced_norm_trans[norm_key]
            else:
                remaining_missing.add(orig_key)
        missing_keys = remaining_missing

    # Return the verification result
    exact_match = len(missing_keys) == 0 and len(format_changes) == 0
    return exact_match, missing_keys, format_changes


def translate_batch(
    batch,
    batch_index,
    slide_metadata,
    source_language,
    target_language,
    api_key=None,
    max_retries=3,
    cost_tracker=None,
):
    """
    Translate a batch of text using the Anthropic API.

    Args:
        batch: Dictionary of text elements to translate
        batch_index: Index of the current batch
        slide_metadata: Metadata about slides and text elements
        source_language: Source language code
        target_language: Target language code
        api_key: Anthropic API key (optional)
        max_retries: Maximum number of retries for API calls
        cost_tracker: Dictionary to track API costs

    Returns:
        dict: Dictionary of translated text elements
    """

    def clean_text(text):
        """Clean text for better translation results"""
        return re.sub(r"\s+", " ", text).strip()

    def estimate_cost(prompt_tokens, completion_tokens, model="claude-sonnet-4-6"):
        """Estimate cost of API call based on token counts"""
        # Claude 3.5 Sonnet pricing: $3 per 1M input tokens, $15 per 1M output tokens
        # Claude 3 Sonnet pricing: $3 per 1M input tokens, $15 per 1M output tokens
        input_cost_per_million = 3.0
        output_cost_per_million = 15.0

        input_cost = (prompt_tokens / 1000000) * input_cost_per_million
        output_cost = (completion_tokens / 1000000) * output_cost_per_million

        return input_cost + output_cost

    # Use provided API key or get from environment
    client = anthropic.Anthropic(api_key=api_key or os.environ.get("CLAUDE_API_KEY"))

    # Prepare the batch for translation
    batch_items = list(batch.items())
    batch_keys = [item[0] for item in batch_items]
    batch_values = [clean_text(item[1]) for item in batch_items]

    # Create a JSON structure for the content to translate
    content_to_translate = {key: value for key, value in zip(batch_keys, batch_values)}

    # Create context information about the slides
    context_info = {}
    for key in batch_keys:
        # Find metadata for this element
        for slide in slide_metadata:
            if isinstance(slide, dict) and "elements" in slide:
                for element in slide.get("elements", []):
                    if element.get("id") == key:
                        context_info[key] = {
                            "slide_number": slide.get("slide_number", 0),
                            "type": element.get("type", "unknown"),
                            "context": f"Slide {slide.get('slide_number', 0)}, {element.get('type', 'element')}",
                        }
                        break

    # Allow an "auto" source language so callers don't have to know the deck's language.
    if str(source_language).strip().lower() in ("auto", "autodetect", "detect", ""):
        source_desc = "the source language (auto-detect it)"
    else:
        source_desc = source_language

    # Create the system prompt
    system_prompt = f"""You are a professional translator specializing in PowerPoint presentations.
Your task is to translate the content from {source_desc} to {target_language} while preserving the meaning, tone, and formatting.

IMPORTANT GUIDELINES:
1. Translate all text accurately while maintaining the original meaning and tone.
2. Preserve formatting elements like bullet points, numbering, and paragraph breaks.
3. Maintain any technical terminology appropriately.
4. For tables, preserve the tabular structure in your translation.
5. Respect the context of each text element (slide title, body text, etc.).
6. Do not add or remove content; translate only what is provided.
7. Return your response as a JSON object with the same structure as the input.
8. CRITICAL: You must preserve the exact key format for each item. Do not modify key formats such as "slide1_shape0" or "slide_1_element_0" in any way.

PRIVACY NOTICE:
- Do not store or remember any content from this presentation.
- Do not reference the content in future conversations.
- Treat all content as confidential business information.

The content to translate is provided as a JSON object where each key is a unique identifier and each value is the text to translate.
"""

    # Create the user prompt
    user_prompt = f"""Please translate the following presentation content from {source_desc} to {target_language}.

Here is the content to translate (with context information):
```json
{json.dumps(content_to_translate, ensure_ascii=False, indent=2)}
```

Context information (to help you understand the content better):
```json
{json.dumps(context_info, ensure_ascii=False, indent=2)}
```

IMPORTANT INSTRUCTION:
- Your response must be a JSON object with EXACTLY the same keys as the input.
- Do not modify key formats (like "slide1_shape0" or "slide_1_element_0") in any way.
- Only translate the text values, leaving keys unchanged.

Please return ONLY a JSON object with the same keys and the translated content as values.
Do not include any explanations or notes outside the JSON object.
"""

    # Initialize variables for retry logic
    retry_count = 0
    translated_batch = None

    # Try to translate with retries
    while retry_count <= max_retries:
        try:
            # Call the Anthropic API
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=config.ANTHROPIC_MAX_TOKENS,
                temperature=config.ANTHROPIC_TEMPERATURE,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                metadata={"user_id": "anonymous_user"},
            )

            # Track costs if requested
            if cost_tracker is not None:
                prompt_tokens = response.usage.input_tokens
                completion_tokens = response.usage.output_tokens
                cost = estimate_cost(prompt_tokens, completion_tokens)

                cost_tracker["total_prompt_tokens"] = (
                    cost_tracker.get("total_prompt_tokens", 0) + prompt_tokens
                )
                cost_tracker["total_completion_tokens"] = (
                    cost_tracker.get("total_completion_tokens", 0) + completion_tokens
                )
                cost_tracker["total_cost"] = cost_tracker.get("total_cost", 0) + cost

                logger.info(
                    f"Batch {batch_index}: {prompt_tokens} prompt tokens, {completion_tokens} completion tokens, estimated cost: ${cost:.4f}"
                )

            # Extract the JSON from the response
            json_content = extract_json_blocks(response.content[0].text)

            if json_content:
                try:
                    translated_batch = json.loads(json_content)

                    # Verify that keys match exactly
                    exact_match, missing_keys, format_changes = verify_translation_keys(
                        batch.keys(), translated_batch.keys()
                    )

                    # Log any issues with key matching
                    if not exact_match:
                        if missing_keys:
                            logger.warning(
                                f"API response missing {len(missing_keys)} keys in batch {batch_index}"
                            )
                            for k in list(missing_keys)[
                                :5
                            ]:  # Show only first few to avoid log spam
                                logger.warning(f"  Missing key: {k}")

                        if format_changes:
                            logger.warning(
                                f"API response modified {len(format_changes)} key formats in batch {batch_index}"
                            )
                            for orig, changed in list(format_changes.items())[:5]:
                                logger.warning(
                                    f"  Key format changed: {orig} -> {changed}"
                                )
                                # Fix the format changes by copying values to the correct keys
                                if changed in translated_batch:
                                    translated_batch[orig] = translated_batch[changed]

                    break  # Success, exit the retry loop
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing JSON in batch {batch_index}: {e}")
                    retry_count += 1
            else:
                logger.error(f"No valid JSON found in response for batch {batch_index}")
                retry_count += 1

        except Exception as e:
            logger.error(f"Error in API call for batch {batch_index}: {e}")
            retry_count += 1
            time.sleep(2)  # Wait before retrying

    # If we couldn't translate after all retries, return an empty dict
    if translated_batch is None:
        logger.error(
            f"Failed to translate batch {batch_index} after {max_retries} retries"
        )
        return {}

    return translated_batch


def _is_blank(value):
    """True if a translation value is missing or effectively empty."""
    return value is None or not str(value).strip()


def missing_block_ids(text_dict, translated_texts):
    """Return source IDs that have no usable (non-blank) translation."""
    return [
        block_id for block_id in text_dict if _is_blank(translated_texts.get(block_id))
    ]


def describe_block(block_id, source_text=""):
    """Human-readable description of a text block for completeness reporting."""
    slide_match = re.search(r"slide(\d+)", block_id)
    slide = slide_match.group(1) if slide_match else "?"
    if "_notes" in block_id:
        location = f"slide {slide} speaker notes"
    elif "_table_" in block_id:
        cell = re.search(r"_table_r(\d+)c(\d+)", block_id)
        shape = re.search(r"_shape(\d+)", block_id)
        rc = f"r{cell.group(1)}c{cell.group(2)}" if cell else "?"
        sh = shape.group(1) if shape else "?"
        location = f"slide {slide} table (shape {sh}, cell {rc})"
    else:
        shape = re.search(r"_shape(\d+)", block_id)
        sh = shape.group(1) if shape else "?"
        location = f"slide {slide} shape {sh}"
    snippet = str(source_text).strip().replace("\n", " ")
    if len(snippet) > 60:
        snippet = snippet[:57] + "..."
    return f'{block_id} ({location}): "{snippet}"'


def parse_slide_selection(spec):
    """
    Parse a 1-indexed slide selection like "1-3,5,7" into a set of ints.

    Empty / None / "all" / "*" means "all slides" and returns None. Raises ValueError
    on malformed input so callers can surface a clear error.
    """
    if spec is None or str(spec).strip().lower() in ("", "all", "*"):
        return None
    selected = set()
    for part in str(spec).replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            start_str, end_str = part.split("-", 1)
            start, end = int(start_str), int(end_str)
            if start > end:
                start, end = end, start
            selected.update(range(start, end + 1))
        else:
            selected.add(int(part))
    return selected or None


def filter_blocks_by_slides(text_dict, selected_slides):
    """Keep only blocks whose slide number is in selected_slides (None → unchanged)."""
    if selected_slides is None:
        return text_dict
    kept = {}
    for block_id, text in text_dict.items():
        match = re.match(r"slide(\d+)", block_id)
        if match and int(match.group(1)) in selected_slides:
            kept[block_id] = text
    return kept


def _retry_missing_blocks(
    missing_ids,
    text_dict,
    slide_metadata,
    source_language,
    target_language,
    api_key=None,
    cost_tracker=None,
):
    """
    Re-translate genuinely-missing blocks in small batches and map results back.

    Small batches (config.BLOCKS_PER_BATCH) keep responses short enough to avoid the
    truncation that drops blocks on large batches. Returns {id: translation} for the
    blocks that were successfully recovered.
    """
    retry_dict = {bid: text_dict[bid] for bid in missing_ids if bid in text_dict}
    if not retry_dict:
        return {}

    recovered = {}
    batches = split_dict_into_smart_batches(
        retry_dict, max_items=config.BLOCKS_PER_BATCH
    )
    for idx, batch in enumerate(batches):
        result = translate_batch(
            batch,
            f"retry-{idx}",
            slide_metadata,
            source_language,
            target_language,
            api_key=api_key,
            cost_tracker=cost_tracker,
        )
        # Exact-key matches first
        for bid in batch:
            if not _is_blank(result.get(bid)):
                recovered[bid] = result[bid]
        # Salvage any id-format changes the API introduced on the retry response
        leftover = [bid for bid in batch if bid not in recovered]
        if leftover:
            _, _, fixed = validate_translation_ids(
                {bid: batch[bid] for bid in leftover}, result, slide_metadata
            )
            for bid in leftover:
                if not _is_blank(fixed.get(bid)):
                    recovered[bid] = fixed[bid]
    return recovered


def translate_text(
    text_dict,
    slide_metadata,
    source_language,
    target_language,
    resume_file=None,
    api_key=None,
    progress_callback=None,
):
    """
    Translate text from a PowerPoint presentation.

    Args:
        text_dict: Dictionary of text elements to translate
        slide_metadata: Metadata about slides and text elements
        source_language: Source language code
        target_language: Target language code
        resume_file: Path to a recovery file to resume from (optional)
        api_key: Anthropic API key (optional)

    Returns:
        dict: Dictionary of translated text elements
    """
    # Standardize IDs in the text dictionary
    text_dict = standardize_ids(text_dict, slide_metadata)

    # Set up recovery system
    file_id = f"pptx_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    recovery_system = setup_recovery_system(
        file_id,
        text_dict,
        slide_metadata,
        source_language,
        target_language,
        resume_file,
    )

    # If resuming, use the recovered state
    if recovery_system.get("is_resuming"):
        logger.info(f"Resuming translation from {resume_file}")
        text_dict = recovery_system.get("text_dict", {})
        translated_texts = recovery_system.get("translated_texts", {})
        remaining_batches = recovery_system.get("remaining_batches", [])
    else:
        # Deduplicate content to reduce translation costs
        logger.info("Deduplicating content to optimize translation...")
        dedup_result = deduplicate_content(text_dict)
        unique_texts = dedup_result["unique_texts"]
        text_to_ids = dedup_result["text_to_ids"]

        # Split into batches for efficient translation
        logger.info("Splitting content into batches...")
        batches = split_dict_into_smart_batches(
            unique_texts, max_input_tokens=100000, max_items=config.BLOCKS_PER_BATCH
        )

        translated_texts = {}
        remaining_batches = list(enumerate(batches))

    # Set up progress tracking
    total_batches = len(remaining_batches)
    progress_bar = create_progress_bar(total_batches, desc="Translating")

    # Track API costs
    cost_tracker = {
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
        "total_cost": 0,
    }

    # Process each batch
    completed_batches = 0
    if progress_callback:
        try:
            progress_callback(0, total_batches)
        except Exception:
            pass

    while remaining_batches:
        batch_index, batch = remaining_batches.pop(0)

        logger.info(
            f"Translating batch {batch_index + 1}/{total_batches} ({len(batch)} items)"
        )

        # Translate the batch
        batch_translations = translate_batch(
            batch,
            batch_index,
            slide_metadata,
            source_language,
            target_language,
            api_key=api_key,
            cost_tracker=cost_tracker,
        )

        # Update translated texts
        translated_texts.update(batch_translations)

        # Save recovery state
        recovery_system["translated_texts"] = translated_texts
        recovery_system["remaining_batches"] = remaining_batches
        recovery_system["save_recovery_state"]()

        # Update progress
        progress_bar.update(1)
        completed_batches += 1
        if progress_callback:
            try:
                progress_callback(completed_batches, total_batches)
            except Exception:
                pass

    # If we deduplicated content, expand the translations back to all IDs
    if recovery_system.get("is_resuming"):
        # For resumed translations, we already have the full set
        pass
    else:
        # For new translations, expand the deduplicated content
        logger.info("Expanding translations to all text elements...")

        expanded_translations = {}
        for text, ids in text_to_ids.items():
            # Find the translation for this text
            translation = None
            for unique_id, unique_text in unique_texts.items():
                if unique_text == text and unique_id in translated_texts:
                    translation = translated_texts[unique_id]
                    break

            # Apply the translation to all IDs with this text
            if translation:
                for id in ids:
                    expanded_translations[id] = translation

        translated_texts = expanded_translations

    # --- Completeness: retry genuinely-missing blocks before any best-effort mapping ---
    genuine_missing = missing_block_ids(text_dict, translated_texts)
    if genuine_missing:
        logger.warning(
            f"{len(genuine_missing)}/{len(text_dict)} blocks missing after first pass; "
            f"retrying in small batches of {config.BLOCKS_PER_BATCH}..."
        )
        recovered = _retry_missing_blocks(
            genuine_missing,
            text_dict,
            slide_metadata,
            source_language,
            target_language,
            api_key=api_key,
            cost_tracker=cost_tracker,
        )
        translated_texts.update(recovered)
        logger.info(
            f"Retry pass recovered {len(recovered)}/{len(genuine_missing)} missing blocks"
        )

    # Best-effort id-format mapping for any remaining stragglers
    success, missing_ids, fixed_translations = validate_translation_ids(
        text_dict, translated_texts, slide_metadata
    )
    if not success:
        logger.warning(
            f"Some translations ({len(missing_ids)}) could not be mapped correctly"
        )
        translated_texts = fixed_translations

    # Log cost information
    if cost_tracker["total_cost"] > 0:
        logger.info(
            f"Translation complete. Total tokens: {cost_tracker['total_prompt_tokens']} input, {cost_tracker['total_completion_tokens']} output"
        )
        logger.info(f"Estimated cost: ${cost_tracker['total_cost']:.2f}")

    progress_bar.close()
    return translated_texts


def translate_pptx(
    input_file,
    output_file,
    source_language="en",
    target_language="fr",
    resume_file=None,
    api_key=None,
    progress_callback=None,
    slides=None,
):
    """
    Translate a PowerPoint presentation from one language to another.

    Args:
        input_file: Path to the input PPTX file
        output_file: Path to save the translated PPTX file
        source_language: Source language code (default: en)
        target_language: Target language code (default: fr)
        resume_file: Path to a recovery file to resume from (optional)
        api_key: Anthropic API key (optional)

    Returns:
        bool: True if successful, False otherwise
    """
    logger.info(f"Translating {input_file} from {source_language} to {target_language}")

    # Extract text from the presentation
    logger.info("Extracting text from presentation...")
    text_dict, slide_metadata = extract_text(input_file)

    logger.info(
        f"Extracted {len(text_dict)} text elements from {len(slide_metadata)} slides"
    )

    # Optional slide selection: translate only the chosen slides; the rest of the deck
    # is left untouched (update_slides only writes the blocks we hand it).
    try:
        selected_slides = parse_slide_selection(slides)
    except ValueError:
        raise TranslationError(
            f"Invalid slide selection {slides!r}. Use formats like '1-3,5,7'."
        )
    if selected_slides is not None:
        before = len(text_dict)
        text_dict = filter_blocks_by_slides(text_dict, selected_slides)
        logger.info(
            f"Slide selection {sorted(selected_slides)}: translating "
            f"{len(text_dict)}/{before} text blocks"
        )
        if not text_dict:
            raise TranslationError(
                f"No translatable text found on the selected slides: "
                f"{sorted(selected_slides)}"
            )

    # Translate the text
    logger.info("Translating text...")
    translated_texts = translate_text(
        text_dict,
        slide_metadata,
        source_language,
        target_language,
        resume_file=resume_file,
        api_key=api_key,
        progress_callback=progress_callback,
    )

    # Validate the translations before updating
    logger.info("Validating translations before updating presentation...")
    success, missing, fixed = validate_translation_ids(
        text_dict, translated_texts, slide_metadata
    )
    if not success:
        translated_texts = fixed

    # --- Completeness gate: never write a partially-translated deck ---
    total_blocks = len(text_dict)
    still_missing = missing_block_ids(text_dict, translated_texts)
    if still_missing:
        details = [describe_block(bid, text_dict.get(bid, "")) for bid in still_missing]
        logger.error(
            f"Incomplete translation: {len(still_missing)}/{total_blocks} blocks were "
            f"not translated. Refusing to write a partial deck."
        )
        for line in details:
            logger.error(f"  UNTRANSLATED: {line}")
        raise IncompleteTranslationError(
            message=(
                f"{len(still_missing)}/{total_blocks} text blocks were not translated; "
                f"refusing to write a partial deck to {output_file}.\n"
                "Untranslated blocks:\n" + "\n".join(f"  - {d}" for d in details)
            ),
            missing_ids=still_missing,
            total=total_blocks,
        )

    logger.info(
        f"Completeness check: {total_blocks}/{total_blocks} blocks translated (100%)"
    )

    # Update the presentation with translated text
    logger.info("Updating presentation with translated text...")
    success = update_slides(input_file, output_file, translated_texts)

    if success:
        logger.info(f"Translation complete. Saved to {output_file}")
        return True

    logger.error("Failed to update presentation with translated text")
    raise TranslationError(
        f"Failed to write the translated presentation to {output_file}"
    )


def list_recovery_files():
    """
    List available recovery files for PPTX translations.

    Returns:
        list: List of recovery files with metadata
    """
    recovery_dir = os.path.join(os.getcwd(), "translation_recovery")
    if not os.path.exists(recovery_dir):
        return []

    recovery_files = [
        f
        for f in os.listdir(recovery_dir)
        if f.startswith("recovery_pptx_") and f.endswith(".json")
    ]

    result = []
    for file in recovery_files:
        try:
            file_path = os.path.join(recovery_dir, file)
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

                result.append(
                    {
                        "file": file,
                        "path": file_path,
                        "timestamp": data.get("timestamp", "Unknown"),
                        "source_language": data.get("source_language", "Unknown"),
                        "target_language": data.get("target_language", "Unknown"),
                        "progress": f"{len(data.get('translated_texts', {}))} / {len(data.get('text_dict', {}))}",
                    }
                )
        except:
            # Skip files that can't be parsed
            pass

    return sorted(result, key=lambda x: x["timestamp"], reverse=True)
