"""
Enhanced PPTX translator module with improved quality and performance.

This module provides enhanced translation capabilities for PowerPoint presentations,
utilizing multiple AI models for optimal quality and cost efficiency.
"""

import os
import sys
import time
import json
import logging
import concurrent.futures
from typing import List, Dict, Any, Union, Optional, Tuple, Callable
from pptx import Presentation

# Import our module components
from .models import get_translator_for_model
from .models.base import (
    MODEL_CLAUDE_35_SONNET,
    MODEL_CLAUDE_35_HAIKU,
    MODEL_GPT_4O,
    MODEL_GPT_4O_MINI,
    MODEL_GEMINI_15_PRO,
    MODEL_GEMINI_15_FLASH,
)
from .cache import (
    get_from_translation_cache,
    save_to_translation_cache,
    get_cache_stats,
    clear_translation_cache,
)
from .utils import (
    repair_json,
    extract_json_blocks,
    get_model_pricing,
    estimate_cost,
    clean_text,
)

# Configure logger
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Supported language codes
SUPPORTED_LANGUAGES = {
    "en": "English",
    "ja": "Japanese",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "ko": "Korean",
    "zh": "Chinese",
    "pt": "Portuguese",
    "ru": "Russian",
    "ar": "Arabic",
    "nl": "Dutch",
    "tr": "Turkish",
    "hi": "Hindi",
    "th": "Thai",
}

# Quality level constants
QUALITY_DRAFT = "draft"
QUALITY_STANDARD = "standard"
QUALITY_PROFESSIONAL = "professional"
QUALITY_ECONOMY = "economy"  # For future use

# Quality levels and their corresponding models
QUALITY_LEVELS = {
    QUALITY_DRAFT: [MODEL_CLAUDE_35_HAIKU, MODEL_GPT_4O_MINI, MODEL_GEMINI_15_FLASH],
    QUALITY_STANDARD: [MODEL_CLAUDE_35_HAIKU, MODEL_GPT_4O_MINI, MODEL_GEMINI_15_PRO],
    QUALITY_PROFESSIONAL: [MODEL_CLAUDE_35_SONNET, MODEL_GPT_4O, MODEL_GEMINI_15_PRO],
    QUALITY_ECONOMY: [MODEL_GEMINI_15_FLASH],  # Fallback to most economical model
}


# Cost tracking class
class CostTracker:
    """Track API costs across multiple models and calls."""

    def __init__(self):
        self.total_cost = 0.0
        self.model_costs = {}
        self.call_count = 0

    def add_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """
        Add cost for an API call.

        Args:
            model: Model identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            float: Cost for this call
        """
        pricing = get_model_pricing(model)

        # Calculate cost
        input_cost = (input_tokens / 1_000_000) * pricing["input_cost_per_million"]
        output_cost = (output_tokens / 1_000_000) * pricing["output_cost_per_million"]
        call_cost = input_cost + output_cost

        # Update trackers
        self.total_cost += call_cost
        self.call_count += 1

        if model not in self.model_costs:
            self.model_costs[model] = {
                "cost": 0.0,
                "calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
            }

        self.model_costs[model]["cost"] += call_cost
        self.model_costs[model]["calls"] += 1
        self.model_costs[model]["input_tokens"] += input_tokens
        self.model_costs[model]["output_tokens"] += output_tokens

        return call_cost

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of costs.

        Returns:
            dict: Cost summary
        """
        return {
            "total_cost": round(self.total_cost, 4),
            "call_count": self.call_count,
            "models": {
                model: {
                    "cost": round(data["cost"], 4),
                    "calls": data["calls"],
                    "input_tokens": data["input_tokens"],
                    "output_tokens": data["output_tokens"],
                    "avg_cost_per_call": (
                        round(data["cost"] / data["calls"], 4)
                        if data["calls"] > 0
                        else 0
                    ),
                }
                for model, data in self.model_costs.items()
            },
        }


def perform_quality_check(
    original_text: str, translated_text: str, source_language: str, target_language: str
) -> Tuple[float, List[str]]:
    """
    Perform quality checks on the translation.

    Args:
        original_text: The original text
        translated_text: The translated text
        source_language: Source language code
        target_language: Target language code

    Returns:
        tuple: (quality_score, list_of_issues)
    """
    issues = []

    # Check 1: Length ratio (extreme differences might indicate issues)
    orig_len = len(original_text)
    trans_len = len(translated_text)

    # Different languages have different expected length ratios
    # These are approximations and can be refined
    expected_ratios = {
        "ja-en": 0.5,  # Japanese to English - Japanese is often more compact
        "en-ja": 2.0,  # English to Japanese
        "en-de": 1.3,  # German tends to be longer than English
        "de-en": 0.8,
        "en-fr": 1.2,  # French slightly longer than English
        "fr-en": 0.8,
        "en-zh": 0.7,  # Chinese is more compact than English
        "zh-en": 1.4,
    }

    # Default ratio expectation if not in the above mapping
    default_ratio = 1.0
    lang_pair = f"{source_language}-{target_language}"
    reverse_lang_pair = f"{target_language}-{source_language}"

    if lang_pair in expected_ratios:
        expected_ratio = expected_ratios[lang_pair]
    elif reverse_lang_pair in expected_ratios:
        expected_ratio = 1 / expected_ratios[reverse_lang_pair]
    else:
        expected_ratio = default_ratio

    # Calculate the actual ratio
    actual_ratio = trans_len / orig_len if orig_len > 0 else 0

    # Check if the ratio is significantly off
    ratio_tolerance = 0.5  # Allow 50% deviation from expected
    if actual_ratio < expected_ratio * (
        1 - ratio_tolerance
    ) or actual_ratio > expected_ratio * (1 + ratio_tolerance):
        issues.append(
            f"Length ratio issue: Expected around {expected_ratio:.1f}, got {actual_ratio:.1f}"
        )

    # Check 2: Formatting preservation (bullet points, numbering, etc.)
    format_markers = [
        "•",
        "-",
        "*",
        "1.",
        "2.",
        "3.",
        "I.",
        "II.",
        "III.",
        "A.",
        "B.",
        "C.",
    ]

    for marker in format_markers:
        orig_count = original_text.count(marker)
        trans_count = translated_text.count(marker)

        if orig_count > 0 and trans_count != orig_count:
            issues.append(
                f"Format marker '{marker}' count mismatch: {orig_count} in original, {trans_count} in translation"
            )

    # Check 3: Technical term preservation
    # This is a simplified approach; a more robust solution would use a terminology database
    technical_terms = []

    # Extract potential technical terms (capitalized words/phrases, acronyms)
    import re

    # Find acronyms (all caps words)
    acronyms = re.findall(r"\b[A-Z]{2,}\b", original_text)
    technical_terms.extend(acronyms)

    # Find proper nouns (capitalized words not at sentence start)
    proper_nouns = re.findall(r"(?<=[.!?]\s|\s)[A-Z][a-zA-Z]*\b", " " + original_text)
    technical_terms.extend(proper_nouns)

    # Check if these terms are preserved in the translation
    missing_terms = []
    for term in technical_terms:
        # Skip very short terms as they might be common words
        if len(term) <= 1:
            continue

        # For non-Latin target languages like Japanese, Chinese, etc.,
        # we can't directly check for the term
        if target_language in ["ja", "zh", "ko", "th", "ar"]:
            continue

        if term.lower() not in translated_text.lower():
            missing_terms.append(term)

    if missing_terms:
        issues.append(f"Missing technical terms: {', '.join(missing_terms)}")

    # Check 4: Placeholder preservation (e.g., {0}, {name}, etc.)
    placeholders_original = re.findall(r"\{[^}]+\}", original_text)
    placeholders_translated = re.findall(r"\{[^}]+\}", translated_text)

    if len(placeholders_original) != len(placeholders_translated):
        issues.append(
            f"Placeholder count mismatch: {len(placeholders_original)} in original, {len(placeholders_translated)} in translation"
        )
    else:
        # Check each placeholder
        for placeholder in placeholders_original:
            if placeholder not in translated_text:
                issues.append(f"Missing placeholder: {placeholder}")

    # Calculate quality score - starts at 100 and deducts points for each issue
    quality_score = 100.0
    deduction_per_issue = 100.0 / max(10, len(issues) + 1) if issues else 0
    quality_score -= len(issues) * deduction_per_issue

    # Ensure the score is in the 0-100 range
    quality_score = max(0, min(100, quality_score))

    return quality_score, issues


def fix_translation_issues(
    original_text: str,
    translated_text: str,
    source_language: str,
    target_language: str,
    issues: List[str],
    model: str,
) -> str:
    """
    Attempt to fix identified translation issues.

    Args:
        original_text: The original text
        translated_text: The translated text with issues
        source_language: Source language code
        target_language: Target language code
        issues: List of identified issues
        model: Model to use for fixing

    Returns:
        str: Improved translation
    """
    # If no issues, return the original translation
    if not issues:
        return translated_text

    # Extract missing technical terms if any
    missing_terms = []
    for issue in issues:
        if issue.startswith("Missing technical terms:"):
            terms_str = issue.replace("Missing technical terms:", "").strip()
            missing_terms = [term.strip() for term in terms_str.split(",")]

    # Create a prompt for the model to fix the issues
    system_prompt = f"""You are a professional translator specializing in {SUPPORTED_LANGUAGES.get(source_language, source_language)} to {SUPPORTED_LANGUAGES.get(target_language, target_language)} translation.

Your task is to fix issues in a translation. Here are the specific problems that need to be addressed:
{chr(10).join(f"- {issue}" for issue in issues)}

The following technical terms should be preserved in the translation: {', '.join(missing_terms) if missing_terms else 'N/A'}

Please provide ONLY the corrected translation, maintaining the meaning and style of the original text while fixing the identified issues.
"""

    user_prompt = f"""Original text ({SUPPORTED_LANGUAGES.get(source_language, source_language)}):
{original_text}

Current translation with issues ({SUPPORTED_LANGUAGES.get(target_language, target_language)}):
{translated_text}

Please fix the issues and provide the corrected translation, maintaining the original formatting and style.
"""

    # Initialize the appropriate translator
    translator = get_translator_for_model(model, api_key=None)

    try:
        # Call the model to fix the translation
        if "claude" in model.lower():
            from anthropic import Anthropic

            client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
            response = client.messages.create(
                model=model,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=1000,
            )
            fixed_translation = response.content[0].text
        elif "gpt" in model.lower():
            from openai import OpenAI

            client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=1000,
            )
            fixed_translation = response.choices[0].message.content
        elif "gemini" in model.lower():
            import google.generativeai as genai

            genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))
            model_obj = genai.GenerativeModel(model)
            response = model_obj.generate_content([system_prompt, user_prompt])
            fixed_translation = response.text
        else:
            # Fallback - return original translation if model not supported
            logger.warning(
                f"Model {model} not supported for fixing issues. Returning original translation."
            )
            return translated_text

        return fixed_translation
    except Exception as e:
        logger.error(f"Error fixing translation issues: {str(e)}")
        # Return the original translation if there's an error
        return translated_text


def translate_batch(
    batch: List[Dict[str, str]],
    batch_index: int,
    slide_metadata: Dict[int, Dict[str, Any]],
    source_language: str,
    target_language: str,
    quality_level: str = "standard",
    use_cache: bool = True,
    qa_enabled: bool = True,
    api_key: Optional[str] = None,
    max_retries: int = 3,
    cost_tracker: Optional[CostTracker] = None,
) -> List[Dict[str, str]]:
    """
    Translate a batch of text using an appropriate AI model.

    Args:
        batch: List of dicts with 'id', 'text', and 'type' keys
        batch_index: Index of the current batch
        slide_metadata: Dictionary with slide information
        source_language: Source language code
        target_language: Target language code
        quality_level: 'draft', 'standard', or 'professional'
        use_cache: Whether to use the translation cache
        qa_enabled: Whether to perform quality assurance
        api_key: API key for the translation service
        max_retries: Maximum number of retries for API calls
        cost_tracker: Optional cost tracker

    Returns:
        List of dicts with 'id', 'text', and 'translation' keys
    """

    def clean_text(text: str) -> str:
        """Clean text for better translation results."""
        if not text:
            return text
        return " ".join(text.split())

    # Check if batch is empty
    if not batch:
        logger.warning(f"Empty batch {batch_index} - nothing to translate")
        return []

    # Prepare batch for translation
    content_to_translate = []
    batch_items = []

    for item in batch:
        item_id = item.get("id", "")
        text = item.get("text", "")
        item_type = item.get("type", "text")

        # Skip empty text
        if not text.strip():
            continue

        # Clean the text
        cleaned_text = clean_text(text)

        # Prepare item for our data structure
        batch_item = {
            "id": item_id,
            "text": cleaned_text,
            "type": item_type,
            "translation": None,
            "cached": False,
        }

        batch_items.append(batch_item)

        # Check if we have this in cache
        if use_cache:
            cached_translation = get_from_translation_cache(
                cleaned_text, source_language, target_language
            )

            if cached_translation:
                batch_item["translation"] = cached_translation
                batch_item["cached"] = True
                continue

        # If we reach here, we need to translate this item
        content_to_translate.append(
            {
                "index": len(content_to_translate),
                "id": item_id,
                "text": cleaned_text,
                "type": item_type,
            }
        )

    # Check if we have any items to translate
    cached_items = sum(1 for item in batch_items if item["cached"])
    logger.info(
        f"Batch {batch_index}: Found {cached_items}/{len(batch_items)} items in cache"
    )

    # If all items are cached, return the results immediately
    if len(content_to_translate) == 0:
        return batch_items

    # Prepare context about the slides
    slide_context = []
    for item in content_to_translate:
        item_id = item["id"]
        slide_number = None

        # Extract slide number from item ID (format: slide_X_element_Y)
        if "_" in item_id:
            parts = item_id.split("_")
            if len(parts) >= 3 and parts[0] == "slide":
                try:
                    slide_number = int(parts[1])
                except ValueError:
                    pass

        if slide_number and slide_number in slide_metadata:
            # Get information about this slide
            slide_info = slide_metadata[slide_number]
            element_type = item["type"]

            slide_context.append(f"Slide {slide_number}: {element_type}")

    # Select an appropriate model based on content length, quality level, and language codes
    models = QUALITY_LEVELS.get(quality_level, QUALITY_LEVELS["standard"])

    # Default model selection strategy - use the first model in the list for the given quality level
    selected_model = models[0]

    # Log the selected model and batch size
    logger.info(
        f"Batch {batch_index}: Using {selected_model} for translation with {len(content_to_translate)} items"
    )

    # Create content for the model
    content_json = [
        {"index": item["index"], "text": item["text"], "type": item["type"]}
        for item in content_to_translate
    ]

    # Initialize the appropriate translator
    translator = get_translator_for_model(selected_model, api_key)

    # Prepare system and user prompts
    system_prompt, user_prompt = translator.generate_prompts(
        content_json,
        source_language,
        target_language,
        slide_context if slide_context else None,
    )

    # Translate with retries
    result = None
    for attempt in range(max_retries):
        try:
            # Call the translation API
            result = translator.translate(system_prompt, user_prompt, cost_tracker)
            break  # Success, exit retry loop
        except Exception as e:
            logger.error(
                f"Batch {batch_index}: Translation error (attempt {attempt+1}/{max_retries}): {str(e)}"
            )
            if attempt == max_retries - 1:
                # Last attempt failed, raise the exception
                raise
            # Wait before retrying
            time.sleep(2**attempt)  # Exponential backoff

    if not result:
        raise Exception(
            f"Failed to translate batch {batch_index} after {max_retries} attempts"
        )

    # Extract the JSON content
    translated_items = result.content

    # Match translations with batch items
    for translated_item in translated_items:
        index = translated_item.get("index")
        translation = translated_item.get("translation")

        if index is not None and translation and index < len(content_to_translate):
            original_item = content_to_translate[index]

            # Find the corresponding batch item
            for batch_item in batch_items:
                if (
                    batch_item["id"] == original_item["id"]
                    and batch_item["text"] == original_item["text"]
                ):
                    batch_item["translation"] = translation

                    # Save to cache if enabled
                    if use_cache:
                        save_to_translation_cache(
                            batch_item["text"],
                            translation,
                            source_language,
                            target_language,
                            selected_model,
                        )

    # Perform quality checks if enabled
    if qa_enabled:
        issues_requiring_fixes = []

        for batch_item in batch_items:
            # Skip items that were retrieved from cache
            if batch_item["cached"]:
                continue

            # Skip items that weren't translated
            if not batch_item["translation"]:
                continue

            # Perform quality check
            quality_score, issues = perform_quality_check(
                batch_item["text"],
                batch_item["translation"],
                source_language,
                target_language,
            )

            # If quality score is too low or critical issues were found, fix the translation
            if quality_score < 70 or any(
                issue.startswith("Missing placeholder") for issue in issues
            ):
                issues_requiring_fixes.append(
                    {"batch_item": batch_item, "issues": issues, "score": quality_score}
                )

        # Fix translations with issues
        for issue_data in issues_requiring_fixes:
            batch_item = issue_data["batch_item"]
            issues = issue_data["issues"]

            logger.info(
                f"Fixing translation issues for item {batch_item['id']} (score: {issue_data['score']:.1f})"
            )

            # Fix the translation
            fixed_translation = fix_translation_issues(
                batch_item["text"],
                batch_item["translation"],
                source_language,
                target_language,
                issues,
                selected_model,
            )

            # Update the translation
            batch_item["translation"] = fixed_translation

            # Update cache with fixed translation
            if use_cache:
                save_to_translation_cache(
                    batch_item["text"],
                    fixed_translation,
                    source_language,
                    target_language,
                    selected_model,
                )

    return batch_items


def translate_text(
    texts: List[str],
    source_language: str,
    target_language: str,
    quality_level: str = "standard",
    use_cache: bool = True,
    qa_enabled: bool = True,
    max_workers: int = 4,
    api_key: Optional[str] = None,
    max_retries: int = 3,
) -> List[str]:
    """
    Translate a list of texts with parallel processing.

    Args:
        texts: List of texts to translate
        source_language: Source language code
        target_language: Target language code
        quality_level: 'draft', 'standard', or 'professional'
        use_cache: Whether to use the translation cache
        qa_enabled: Whether to perform quality assurance
        max_workers: Maximum number of parallel workers
        api_key: API key for the translation service
        max_retries: Maximum number of retries for API calls

    Returns:
        List of translated texts
    """
    # Skip if no texts to translate
    if not texts:
        return []

    # Track costs
    cost_tracker = CostTracker()

    # Prepare batches - each text is its own batch
    batches = []
    for i, text in enumerate(texts):
        if not text.strip():
            continue

        batch = [{"id": f"text_{i}", "text": text, "type": "text"}]
        batches.append(
            (
                batch,
                i,
                {},
                source_language,
                target_language,
                quality_level,
                use_cache,
                qa_enabled,
                api_key,
                max_retries,
                cost_tracker,
            )
        )

    # Initialize results array
    results = [None] * len(texts)

    # Translate batches in parallel
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=min(max_workers, len(batches))
    ) as executor:
        # Start translation tasks
        future_to_index = {
            executor.submit(translate_batch, *batch_args): i
            for i, batch_args in enumerate(batches)
        }

        # Process results as they complete
        for future in concurrent.futures.as_completed(future_to_index):
            index = future_to_index[future]

            try:
                batch_result = future.result()

                if batch_result and len(batch_result) > 0:
                    original_index = int(batch_result[0]["id"].split("_")[1])
                    results[original_index] = batch_result[0]["translation"]

            except Exception as e:
                logger.error(f"Error processing batch {index}: {str(e)}")
                # Keep the original text for failed translations
                results[index] = texts[index]

    # Log cost summary
    cost_summary = cost_tracker.get_summary()
    logger.info(
        f"Translation completed - Total cost: ${cost_summary['total_cost']:.4f}, Calls: {cost_summary['call_count']}"
    )

    # Fill in any missing results with original text
    for i in range(len(results)):
        if results[i] is None:
            results[i] = texts[i]

    return results


def translate_pptx(
    input_file: str,
    output_file: str,
    source_language: str,
    target_language: str,
    quality_level: str = "standard",
    use_cache: bool = True,
    qa_enabled: bool = True,
    batch_size: int = 5,
    max_workers: int = 4,
    api_key: Optional[str] = None,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    Translate a PPTX file with parallel processing.

    Args:
        input_file: Path to the input PPTX file
        output_file: Path to save the translated PPTX file
        source_language: Source language code
        target_language: Target language code
        quality_level: 'draft', 'standard', or 'professional'
        use_cache: Whether to use the translation cache
        qa_enabled: Whether to perform quality assurance
        batch_size: Number of text elements per batch
        max_workers: Maximum number of parallel workers
        api_key: API key for the translation service
        max_retries: Maximum number of retries for API calls

    Returns:
        Dict with translation statistics
    """
    # Track costs
    cost_tracker = CostTracker()

    # Load the presentation
    start_time = time.time()
    prs = Presentation(input_file)

    logger.info(f"Loaded presentation: {input_file} with {len(prs.slides)} slides")

    # Extract text from slides
    slide_texts = []
    slide_metadata = {}

    for slide_index, slide in enumerate(prs.slides):
        slide_number = slide_index + 1
        slide_metadata[slide_number] = {"elements": []}

        # Process each shape in the slide
        for shape_index, shape in enumerate(slide.shapes):
            if not hasattr(shape, "text"):
                continue

            text = shape.text.strip()
            if not text:
                continue

            # Add text to our list
            text_id = f"slide_{slide_number}_element_{shape_index}"

            slide_texts.append(
                {
                    "id": text_id,
                    "text": text,
                    "type": "text",
                    "slide": slide,
                    "shape": shape,
                }
            )

            # Add to slide metadata
            slide_metadata[slide_number]["elements"].append(
                {"id": text_id, "type": "text", "text_length": len(text)}
            )

    # Calculate total text elements and characters
    total_elements = len(slide_texts)
    total_chars = sum(len(item["text"]) for item in slide_texts)

    logger.info(f"Extracted {total_elements} text elements ({total_chars} characters)")

    # Create batches
    batches = []
    current_batch = []
    current_batch_char_count = 0

    for item in slide_texts:
        item_char_count = len(item["text"])

        # Start a new batch if current one is full
        if (
            len(current_batch) >= batch_size
            or current_batch_char_count + item_char_count > 2000
        ):
            if current_batch:
                batches.append(current_batch)
            current_batch = []
            current_batch_char_count = 0

        # Add item to current batch
        current_batch.append({"id": item["id"], "text": item["text"], "type": "text"})
        current_batch_char_count += item_char_count

    # Add the last batch if not empty
    if current_batch:
        batches.append(current_batch)

    # Translate batches in parallel
    translated_texts = {}

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=min(max_workers, len(batches))
    ) as executor:
        # Start translation tasks
        future_to_batch_index = {
            executor.submit(
                translate_batch,
                batch,
                batch_index,
                slide_metadata,
                source_language,
                target_language,
                quality_level,
                use_cache,
                qa_enabled,
                api_key,
                max_retries,
                cost_tracker,
            ): batch_index
            for batch_index, batch in enumerate(batches)
        }

        # Process results as they complete
        for future in concurrent.futures.as_completed(future_to_batch_index):
            batch_index = future_to_batch_index[future]

            try:
                batch_result = future.result()

                # Add translated texts to our dictionary
                for item in batch_result:
                    if item["translation"]:
                        translated_texts[item["id"]] = item["translation"]
                    else:
                        # Fallback to original text if translation failed
                        for original_item in slide_texts:
                            if original_item["id"] == item["id"]:
                                translated_texts[item["id"]] = original_item["text"]
                                break

                logger.info(f"Batch {batch_index} completed: {len(batch_result)} items")

            except Exception as e:
                logger.error(f"Error processing batch {batch_index}: {str(e)}")

                # Fallback to original text for the entire batch
                batch = batches[batch_index]
                for item in batch:
                    for original_item in slide_texts:
                        if original_item["id"] == item["id"]:
                            translated_texts[item["id"]] = original_item["text"]
                            break

    # Update the presentation with translations
    for item in slide_texts:
        item_id = item["id"]

        if item_id in translated_texts:
            # Replace text in the shape
            shape = item["shape"]
            if hasattr(shape, "text"):
                shape.text = translated_texts[item_id]

    # Save the translated presentation
    prs.save(output_file)

    end_time = time.time()
    execution_time = end_time - start_time

    # Log cost summary
    cost_summary = cost_tracker.get_summary()
    logger.info(
        f"Translation completed - Total cost: ${cost_summary['total_cost']:.4f}, Calls: {cost_summary['call_count']}"
    )

    # Prepare statistics
    translation_stats = {
        "input_file": input_file,
        "output_file": output_file,
        "slides": len(prs.slides),
        "text_elements": total_elements,
        "characters": total_chars,
        "execution_time": execution_time,
        "cost": cost_summary,
    }

    logger.info(f"Translation completed in {execution_time:.2f} seconds")

    return translation_stats


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
        except Exception:
            # Skip files that can't be parsed
            pass

    return sorted(result, key=lambda x: x["timestamp"], reverse=True)


# Create alias for translate_pptx as translate_presentation for backward compatibility
translate_presentation = translate_pptx

if __name__ == "__main__":
    """
    Command-line interface for the enhanced PPTX translator.

    Usage:
        python -m ai_deck_translator.pptx.enhanced.translator <input_file> <output_file> [options]

    Options:
        --source-lang CODE    Source language code (default: en)
        --target-lang CODE    Target language code (default: fr)
        --quality LEVEL       Quality level: professional, standard, draft, economy (default: standard)
        --resume FILE         Resume from a recovery file
        --no-cache            Disable translation cache
        --no-qa               Disable quality assurance
        --workers NUM         Number of parallel workers (default: auto)
        --batch-size SIZE     Number of text elements per batch (default: 5)
        --api-key KEY         API key for translation service
        --cache-stats         Show cache statistics and exit
        --clear-cache         Clear translation cache and exit
        --list-recovery       List available recovery files and exit
    """
    import argparse

    parser = argparse.ArgumentParser(description="Enhanced PPTX Translator")
    parser.add_argument("input_file", nargs="?", help="Input PPTX file to translate")
    parser.add_argument("output_file", nargs="?", help="Output PPTX file")
    parser.add_argument(
        "--source-lang", default="en", help="Source language code (default: en)"
    )
    parser.add_argument(
        "--target-lang", default="fr", help="Target language code (default: fr)"
    )
    parser.add_argument(
        "--quality",
        default=QUALITY_STANDARD,
        choices=[
            QUALITY_PROFESSIONAL,
            QUALITY_STANDARD,
            QUALITY_DRAFT,
            QUALITY_ECONOMY,
        ],
        help="Translation quality level (default: standard)",
    )
    parser.add_argument("--resume", help="Resume from a recovery file")
    parser.add_argument(
        "--no-cache", action="store_true", help="Disable translation cache"
    )
    parser.add_argument(
        "--no-qa", action="store_true", help="Disable quality assurance"
    )
    parser.add_argument(
        "--workers", type=int, help="Number of parallel workers (default: auto)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Number of text elements per batch (default: 5)",
    )
    parser.add_argument("--api-key", help="API key for translation service")
    parser.add_argument(
        "--cache-stats", action="store_true", help="Show cache statistics and exit"
    )
    parser.add_argument(
        "--clear-cache", action="store_true", help="Clear translation cache and exit"
    )
    parser.add_argument(
        "--list-recovery",
        action="store_true",
        help="List available recovery files and exit",
    )

    args = parser.parse_args()

    # Handle utility commands
    if args.cache_stats:
        stats = get_cache_stats()
        print("Translation Cache Statistics:")
        print(f"Entries: {stats['entry_count']}")
        print(f"Total size: {stats['total_size_mb']:.2f} MB")
        print(f"Average entry size: {stats['avg_entry_size_kb']:.2f} KB")
        sys.exit(0)

    if args.clear_cache:
        count = clear_translation_cache()
        print(f"Cleared {count} entries from translation cache.")
        sys.exit(0)

    if args.list_recovery:
        recovery_files = list_recovery_files()
        if not recovery_files:
            print("No recovery files found.")
        else:
            print("Available recovery files:")
            for i, file_info in enumerate(recovery_files):
                print(f"{i+1}. {file_info['file']}")
                print(f"   Path: {file_info['path']}")
                print(f"   Timestamp: {file_info['timestamp']}")
                print(
                    f"   Languages: {file_info['source_language']} → {file_info['target_language']}"
                )
                print(f"   Progress: {file_info['progress']}")
                print()
        sys.exit(0)

    # Check required arguments for translation
    if not args.input_file or not args.output_file:
        parser.print_help()
        sys.exit(1)

    # Run the translation
    try:
        result = translate_pptx(
            args.input_file,
            args.output_file,
            source_language=args.source_lang,
            target_language=args.target_lang,
            quality_level=args.quality,
            use_cache=not args.no_cache,
            qa_enabled=not args.no_qa,
            batch_size=args.batch_size,
            max_workers=args.workers,
            api_key=args.api_key,
        )

        # Print result summary
        print(
            f"Translation completed successfully in {result['execution_time']:.2f} seconds."
        )
        print(f"Translated {result['text_elements']} text elements.")
        print(f"Output file: {result['output_file']}")
    except Exception as e:
        print(f"Translation failed: {str(e)}")
        sys.exit(1)
