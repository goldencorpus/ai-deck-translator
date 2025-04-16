"""
Main translator module for the AI Deck Translator application.

This module provides the core functionality for translating Google Slides presentations
while preserving formatting, images, and slide structure. It handles the entire translation
workflow, including text extraction, translation, and updating the presentation.

Public Functions:
    translate_slides: Main entry point for translating a Google Slides presentation
    translate_text: Translate extracted text from a presentation
    extract_json_blocks: Extract JSON blocks from translation API responses
    repair_json: Repair malformed JSON returned by the translation API
    list_recovery_files: List available recovery files for resuming translations
"""

import os
import json
import re
import anthropic
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from .. import config
from ..auth.google_auth import authenticate_google
from ..core.extractor import extract_text
from ..core.updater import update_slides
from ..utils.batch import split_dict_into_smart_batches, deduplicate_content
from ..utils.recovery import setup_recovery_system
from ..utils.progress import create_progress_bar
from ..utils.logging import get_logger
from ..utils.batch import create_batches
from ..utils.progress import ProgressTracker
from ..utils.recovery import save_recovery_file, load_recovery_file
from ..utils.exceptions import TranslationError, NetworkError, RateLimitError
from ..utils.translation_memory import lookup_translation, save_translation
from ..utils.glossary import find_terms_in_text, apply_glossary_to_text

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
    # Fix common JSON errors

    # Remove any markdown code block markers
    json_content = re.sub(r"```json\s*", "", json_content)
    json_content = re.sub(r"```\s*$", "", json_content)

    # Remove any comments
    json_content = re.sub(r"//.*$", "", json_content, flags=re.MULTILINE)

    # Fix trailing commas in objects and arrays
    json_content = re.sub(r",\s*}", "}", json_content)
    json_content = re.sub(r",\s*]", "]", json_content)

    # Fix property names that aren't in quotes
    def fix_property_names(match):
        # Add quotes around property names that aren't quoted
        return f'"{match.group(1)}":'

    json_content = re.sub(r"([a-zA-Z0-9_]+):", fix_property_names, json_content)

    # Replace single quotes with double quotes (careful with apostrophes in text)
    cleaned = ""
    in_string = False
    escape_next = False

    for char in json_content:
        if char == "\\" and not escape_next:
            escape_next = True
            cleaned += char
            continue

        if char == '"' and not escape_next:
            in_string = not in_string

        if char == "'" and not in_string and not escape_next:
            char = '"'

        cleaned += char
        escape_next = False

    return cleaned.strip()


def extract_json_blocks(text):
    """
    Extract JSON blocks from the translator API response.

    Args:
        text: API response text

    Returns:
        dict: Extracted JSON data
    """
    # Find json blocks in text using regex
    json_block_pattern = r"({[\s\S]*?})"

    # Find all potential JSON blocks
    potential_json_blocks = re.findall(json_block_pattern, text)

    for block in potential_json_blocks:
        try:
            # Try to parse the potential JSON block
            data = json.loads(block)
            # If successful, return the data
            return data
        except json.JSONDecodeError:
            # Try to repair the JSON and parse again
            try:
                repaired_json = repair_json(block)
                data = json.loads(repaired_json)
                return data
            except json.JSONDecodeError:
                # If still can't parse, continue to the next block
                continue

    # If no valid JSON blocks found
    raise ValueError("No valid JSON found in the API response")


def translate_batch(
    batch,
    batch_index,
    slide_metadata,
    source_language,
    target_language,
    api_key=None,
    max_retries=None,
):
    """
    Translate a batch of text using the Claude API.

    Args:
        batch: Dictionary of text items to translate
        batch_index: Index of the current batch
        slide_metadata: Metadata about slides
        source_language: Source language code
        target_language: Target language code
        api_key: Optional Claude API key
        max_retries: Maximum number of retries on failure

    Returns:
        dict: Dictionary of translated text
    """
    max_retries = max_retries or config.MAX_RETRIES
    api_key = api_key or config.CLAUDE_API_KEY
    model = config.CLAUDE_MODEL

    def clean_text(text):
        # Remove excessive newlines and whitespace for cleaner prompt
        return re.sub(r"\n{3,}", "\n\n", text).strip()

    # Set up the Claude client
    client = anthropic.Anthropic(api_key=api_key)

    batch_items = list(batch.items())
    object_ids = [item[0] for item in batch_items]
    text_contents = [item[1] for item in batch_items]

    # Build a comprehensive context of what we're translating
    context = []
    for item_id in object_ids:
        # For slide elements, try to find which slide they belong to
        if "_r" in item_id and "_c" in item_id:
            # This is a table cell
            base_id = item_id.split("_r")[0]
            for i, slide in enumerate(slide_metadata):
                found = False
                for element_text in slide["content"]:
                    if base_id in element_text:
                        context.append(
                            f"Table in Slide {i+1}: {slide.get('title', '')}"
                        )
                        found = True
                        break
                if found:
                    break
        else:
            # Regular shape element
            for i, slide in enumerate(slide_metadata):
                found = False
                if item_id in slide.get("content", []):
                    context.append(f"Slide {i+1}: {slide.get('title', '')}")
                    found = True
                    break
                if found:
                    break

    context_str = "\n".join(set(context[:10]))  # Limit to 10 unique context items

    # Create a JSON representation of the content to translate
    input_json = json.dumps(
        {id: text for id, text in zip(object_ids, text_contents)},
        ensure_ascii=False,
        indent=2,
    )

    system_prompt = f"""You are a professional translator specializing in {source_language} to {target_language} translation. 
    
Your task is to translate the provided text items from {source_language} to {target_language}. 
The text comes from a Google Slides presentation and includes slide content, table cells, and other text elements. 

IMPORTANT GUIDELINES:
1. Translate ONLY the text values, preserving all object IDs exactly as provided
2. Maintain a professional tone appropriate for business presentations
3. Preserve any technical terminology, proper names, and formatting
4. The response must be valid JSON with the exact same structure as the input

TRANSLATION CONTEXT:
{clean_text(context_str)}

Privacy notice: Do not store or remember any of this content. This is a one-time translation task.
"""

    user_prompt = f"""Here is the JSON with text to translate from {source_language} to {target_language}:

{input_json}

Please respond with ONLY the translated JSON object, maintaining the exact same structure and object IDs. The entire response must be a valid JSON object without any additional text or explanations."""

    # Retry logic
    for retry in range(max_retries):
        try:
            print(f"Starting translation of batch {batch_index} ({len(batch)} items)")

            # Call the Claude API
            response = client.messages.create(
                model=model,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=100000,
            )

            # Extract the content from the response
            response_text = response.content[0].text

            # Extract JSON from the response
            try:
                translated_batch = json.loads(response_text)
            except json.JSONDecodeError:
                # Try to extract and repair JSON blocks
                translated_batch = extract_json_blocks(response_text)

            # Verify that all keys are present
            missing_keys = set(batch.keys()) - set(translated_batch.keys())
            if missing_keys:
                print(
                    f"Warning: {len(missing_keys)} keys missing in translation response"
                )
                if retry < max_retries - 1:
                    print(
                        f"Retrying batch {batch_index} due to missing keys ({retry + 1}/{max_retries})"
                    )
                    time.sleep(2)  # Brief pause before retry
                    continue
                else:
                    # Last retry, return what we have
                    print(
                        f"Final retry reached, returning partial translations for batch {batch_index}"
                    )

            return translated_batch

        except Exception as e:
            print(f"Error translating batch {batch_index}: {str(e)}")
            if retry < max_retries - 1:
                wait_time = 2**retry  # Exponential backoff
                print(f"Retrying in {wait_time} seconds... ({retry + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                print(f"Max retries reached for batch {batch_index}")
                raise

    # This should only happen if all retries fail
    raise Exception(
        f"Failed to translate batch {batch_index} after {max_retries} attempts"
    )


def translate_text(
    text_elements: Dict[str, str],
    slide_metadata: List[Dict[str, Any]],
    target_language: str,
    translate_func: Callable[[List[str], str], List[str]],
    source_language: str = "en",
    batch_size: int = 50,
    delay: float = 0.5,
    recovery_file: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    use_translation_memory: bool = True,
    update_translation_memory: bool = True,
    use_glossary: bool = True,
) -> Dict[str, str]:
    """
    Translate text elements from a presentation.

    This function translates text elements extracted from a presentation to the target
    language. It handles batching, rate limiting, and error recovery to ensure efficient
    and reliable translation.

    Args:
        text_elements (Dict[str, str]): Dictionary of text elements with IDs as keys
        slide_metadata (List[Dict[str, Any]]): List of slide metadata dictionaries
        target_language (str): Target language code (e.g., 'ja' for Japanese)
        translate_func (Callable): Function to translate a batch of text
            The function should accept a list of strings and a target language code,
            and return a list of translated strings in the same order
        source_language (str, optional): Source language code. Defaults to "en".
        batch_size (int, optional): Maximum number of elements per batch. Defaults to 50.
        delay (float, optional): Delay between batches in seconds. Defaults to 0.5.
        recovery_file (str, optional): Path to save recovery data. Defaults to None.
        progress_callback (Callable, optional): Function to report progress. Defaults to None.
            The function should accept two integers: current progress and total items
        use_translation_memory (bool, optional): Whether to use the translation memory. Defaults to True.
        update_translation_memory (bool, optional): Whether to update the translation memory. Defaults to True.
        use_glossary (bool, optional): Whether to use the glossary for consistent terminology. Defaults to True.

    Returns:
        Dict[str, str]: Dictionary of translated text elements with the same IDs as keys

    Raises:
        TranslationError: If there's an error during translation
        NetworkError: If there's a network error during translation
        RateLimitError: If the translation service rate limit is exceeded

    Example:
        >>> from ai_deck_translator.services.google_translate import translate_batch
        >>> translated = translate_text(
        ...     text_elements={"slide1_shape1": "Hello world"},
        ...     slide_metadata=[{"slide_number": 1, "layout": "Title Slide"}],
        ...     target_language="ja",
        ...     translate_func=translate_batch
        ... )
        >>> print(translated["slide1_shape1"])
        こんにちは世界
    """
    # Initialize progress tracker
    total_elements = len(text_elements)
    progress = ProgressTracker(total_elements, progress_callback)
    logger.info(
        f"Starting translation of {total_elements} elements to {target_language}"
    )

    # Check for recovery file
    translated_elements = {}
    start_index = 0

    if recovery_file and os.path.exists(recovery_file):
        try:
            recovery_data = load_recovery_file(recovery_file)
            if recovery_data and "translated" in recovery_data:
                translated_elements = recovery_data["translated"]
                start_index = recovery_data.get("progress", 0)
                logger.info(
                    f"Loaded recovery data with {len(translated_elements)} translated elements"
                )
                progress.update(len(translated_elements))
        except Exception as e:
            logger.warning(f"Failed to load recovery data: {e}")

    # Create batches of text elements
    element_ids = list(text_elements.keys())
    element_texts = list(text_elements.values())

    # Process slide notes separately to ensure they're included
    notes_ids = []
    notes_texts = []

    for metadata in slide_metadata:
        slide_number = metadata.get("slide_number", 0)
        notes = metadata.get("notes", "")

        if notes and notes.strip():
            notes_id = f"slide{slide_number}_notes"
            notes_ids.append(notes_id)
            notes_texts.append(notes)

    # Add notes to the elements if they're not already included
    for notes_id, notes_text in zip(notes_ids, notes_texts):
        if notes_id not in text_elements:
            element_ids.append(notes_id)
            element_texts.append(notes_text)

    # Check translation memory for existing translations
    if use_translation_memory:
        logger.info("Checking translation memory for existing translations")
        memory_hits = 0

        for i, (element_id, element_text) in enumerate(zip(element_ids, element_texts)):
            if (
                element_id not in translated_elements
            ):  # Skip already translated elements
                # Look up in translation memory
                translation = lookup_translation(
                    element_text, source_language, target_language
                )
                if translation:
                    translated_elements[element_id] = translation
                    memory_hits += 1
                    progress.update(1)

        if memory_hits > 0:
            logger.info(f"Found {memory_hits} translations in memory")

    # Create batches for translation (only for elements not found in memory)
    remaining_ids = []
    remaining_texts = []

    for element_id, element_text in zip(element_ids, element_texts):
        if element_id not in translated_elements:
            remaining_ids.append(element_id)
            remaining_texts.append(element_text)

    if not remaining_ids:
        logger.info(
            "All elements found in translation memory, no need for API translation"
        )
        return translated_elements

    batches = create_batches(remaining_ids, remaining_texts, batch_size)

    # Skip batches that are already translated
    if start_index > 0:
        batches = batches[start_index:]

    # Translate each batch
    for batch_index, (batch_ids, batch_texts) in enumerate(batches):
        batch_num = batch_index + start_index

        # Skip elements that are already translated
        to_translate_indices = []
        to_translate_texts = []

        for i, element_id in enumerate(batch_ids):
            if element_id not in translated_elements:
                to_translate_indices.append(i)
                to_translate_texts.append(batch_texts[i])

        if not to_translate_texts:
            logger.debug(
                f"Skipping batch {batch_num + 1}/{len(batches) + start_index} (already translated)"
            )
            continue

        # Translate the batch
        try:
            logger.debug(
                f"Translating batch {batch_num + 1}/{len(batches) + start_index} ({len(to_translate_texts)} elements)"
            )
            translated_batch = translate_func(to_translate_texts, target_language)

            # Update translated elements
            for i, translated_text in zip(to_translate_indices, translated_batch):
                element_id = batch_ids[i]
                original_text = batch_texts[i]

                # Apply glossary to the translated text if enabled
                if use_glossary:
                    translated_text = apply_glossary_to_text(
                        original_text, source_language, target_language, translated_text
                    )

                translated_elements[element_id] = translated_text

                # Update translation memory
                if update_translation_memory:
                    # Determine context from element_id
                    context = {"element_id": element_id}
                    if element_id.startswith("slide"):
                        slide_number = int(element_id.split("_")[0][5:])
                        context["slide_number"] = slide_number

                        # Add more context from slide metadata
                        for metadata in slide_metadata:
                            if metadata.get("slide_number") == slide_number:
                                context["slide_layout"] = metadata.get("layout", "")
                                break

                    # Save to translation memory
                    save_translation(
                        original_text,
                        translated_text,
                        source_language,
                        target_language,
                        context,
                    )

            # Update progress
            progress.update(len(to_translate_texts))

            # Save recovery file
            if recovery_file:
                save_recovery_file(
                    recovery_file,
                    {"translated": translated_elements, "progress": batch_num + 1},
                )
                logger.debug(
                    f"Saved recovery data with {len(translated_elements)} translated elements"
                )

            # Delay between batches to avoid rate limiting
            if batch_index < len(batches) - 1 and delay > 0:
                time.sleep(delay)

        except Exception as e:
            logger.error(f"Error translating batch {batch_num + 1}: {e}")

            # Save recovery file before raising the exception
            if recovery_file:
                save_recovery_file(
                    recovery_file,
                    {"translated": translated_elements, "progress": batch_num},
                )
                logger.info(
                    f"Saved recovery data with {len(translated_elements)} translated elements"
                )

            # Raise appropriate exception
            if "Network error" in str(e):
                raise NetworkError(f"Network error during translation: {str(e)}")
            elif "Rate limit" in str(e):
                raise RateLimitError(f"Translation rate limit exceeded: {str(e)}")
            else:
                raise TranslationError(f"Error during translation: {str(e)}")

    logger.info(
        f"Translation completed: {len(translated_elements)} elements translated to {target_language}"
    )
    return translated_elements


def translate_slides(
    presentation_id,
    source_language=None,
    target_language=None,
    resume_file=None,
    api_key=None,
    web_state=None,
):
    """
    Translate a Google Slides presentation from one language to another.

    This is the main entry point for translating Google Slides presentations. It handles
    the entire translation workflow, including:
    1. Authentication with Google
    2. Extracting text from the presentation
    3. Translating the text
    4. Creating a new copy of the presentation
    5. Updating the new presentation with translated text

    Args:
        presentation_id (str): The ID of the Google Slides presentation to translate.
            This can be found in the URL: docs.google.com/presentation/d/{PRESENTATION_ID}/edit
        source_language (str, optional): The source language code (e.g., 'en' for English).
            If None, uses the default from config.
        target_language (str, optional): The target language code (e.g., 'ja' for Japanese).
            If None, uses the default from config.
        resume_file (str, optional): Path to a recovery file to resume a previous translation.
            If provided, will attempt to continue from where the previous translation stopped.
        api_key (str, optional): Anthropic API key for Claude. If None, uses the key from
            environment variables.
        web_state (dict, optional): Dictionary for tracking state in the web UI.
            Used to update progress and results in the web interface.

    Returns:
        str: The ID of the new translated presentation

    Raises:
        AuthenticationError: If authentication with Google fails
        NetworkError: If there are network issues during API calls
        TranslationError: If the translation process fails

    Example:
        >>> new_id = translate_slides('1rppKpwoUKmf65wAg7J9gSVpL279IBX4EmbWM7yGiS6s', 'en', 'ja')
        >>> print(f"Translated presentation: https://docs.google.com/presentation/d/{new_id}/edit")
    """
    # Use default languages from config if not specified
    source_language = source_language or config.DEFAULT_SOURCE_LANGUAGE
    target_language = target_language or config.DEFAULT_TARGET_LANGUAGE

    # Authenticate with Google
    print("Authenticating with Google...")
    slides_service, drive_service = authenticate_google()

    # Extract text from the presentation
    print(f"Extracting text from presentation {presentation_id}...")
    text_dict, slide_metadata = extract_text(slides_service, presentation_id)
    print(f"Found {len(text_dict)} text elements across {len(slide_metadata)} slides")

    # If web state is provided, update it with extraction info
    if web_state:
        web_state[
            "console_output"
        ] += f"Found {len(text_dict)} text elements across {len(slide_metadata)} slides\n"

    # Translate the text
    print(f"Translating from {source_language} to {target_language}...")
    translated_texts = translate_text(
        text_dict, slide_metadata, target_language, translate_batch
    )

    # Update the presentation with translated text
    print("Creating and updating presentation with translated text...")
    new_presentation_id = update_slides(
        slides_service,
        drive_service,
        presentation_id,
        translated_texts,
        target_language,
    )

    # If web state is provided, update it with the result
    if web_state:
        web_state["result_url"] = (
            f"https://docs.google.com/presentation/d/{new_presentation_id}/edit"
        )
        web_state[
            "console_output"
        ] += f"Translation completed! Presentation available at: {web_state['result_url']}\n"

    print(f"Translation completed!")
    print(f"Translated presentation ID: {new_presentation_id}")

    return new_presentation_id
