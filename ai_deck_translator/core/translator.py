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
from .. import config
from ..auth.google_auth import authenticate_google
from ..core.extractor import extract_text
from ..core.updater import update_slides
from ..utils.batch import split_dict_into_smart_batches, deduplicate_content
from ..utils.recovery import setup_recovery_system
from ..utils.progress import create_progress_bar
from ..utils.logging import get_logger

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
    json_content = re.sub(r'```json\s*', '', json_content)
    json_content = re.sub(r'```\s*$', '', json_content)
    
    # Remove any comments
    json_content = re.sub(r'//.*$', '', json_content, flags=re.MULTILINE)
    
    # Fix trailing commas in objects and arrays
    json_content = re.sub(r',\s*}', '}', json_content)
    json_content = re.sub(r',\s*]', ']', json_content)
    
    # Fix property names that aren't in quotes
    def fix_property_names(match):
        # Add quotes around property names that aren't quoted
        return f'"{match.group(1)}":'
    
    json_content = re.sub(r'([a-zA-Z0-9_]+):', fix_property_names, json_content)
    
    # Replace single quotes with double quotes (careful with apostrophes in text)
    cleaned = ""
    in_string = False
    escape_next = False
    
    for char in json_content:
        if char == '\\' and not escape_next:
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
    json_block_pattern = r'({[\s\S]*?})'
    
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

def translate_batch(batch, batch_index, slide_metadata, source_language, target_language, api_key=None, max_retries=None):
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
        return re.sub(r'\n{3,}', '\n\n', text).strip()
    
    # Set up the Claude client
    client = anthropic.Anthropic(api_key=api_key)
    
    batch_items = list(batch.items())
    object_ids = [item[0] for item in batch_items]
    text_contents = [item[1] for item in batch_items]
    
    # Build a comprehensive context of what we're translating
    context = []
    for item_id in object_ids:
        # For slide elements, try to find which slide they belong to
        if '_r' in item_id and '_c' in item_id:
            # This is a table cell
            base_id = item_id.split('_r')[0]
            for i, slide in enumerate(slide_metadata):
                found = False
                for element_text in slide["content"]:
                    if base_id in element_text:
                        context.append(f"Table in Slide {i+1}: {slide.get('title', '')}")
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
    input_json = json.dumps({id: text for id, text in zip(object_ids, text_contents)}, ensure_ascii=False, indent=2)
    
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
                max_tokens=100000
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
                print(f"Warning: {len(missing_keys)} keys missing in translation response")
                if retry < max_retries - 1:
                    print(f"Retrying batch {batch_index} due to missing keys ({retry + 1}/{max_retries})")
                    time.sleep(2)  # Brief pause before retry
                    continue
                else:
                    # Last retry, return what we have
                    print(f"Final retry reached, returning partial translations for batch {batch_index}")
            
            return translated_batch
            
        except Exception as e:
            print(f"Error translating batch {batch_index}: {str(e)}")
            if retry < max_retries - 1:
                wait_time = 2 ** retry  # Exponential backoff
                print(f"Retrying in {wait_time} seconds... ({retry + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                print(f"Max retries reached for batch {batch_index}")
                raise
    
    # This should only happen if all retries fail
    raise Exception(f"Failed to translate batch {batch_index} after {max_retries} attempts")

def translate_text(text_dict, slide_metadata, source_language, target_language, resume_file=None, api_key=None, web_state=None):
    """
    Translate all text in a presentation.
    
    Args:
        text_dict: Dictionary of text to translate
        slide_metadata: Metadata about slides
        source_language: Source language code
        target_language: Target language code
        resume_file: Optional file path to resume from
        api_key: Optional Claude API key
        web_state: Optional dictionary for web UI state
        
    Returns:
        dict: Dictionary of translated text
    """
    # Set up the recovery system
    recovery_state, recovery_file, save_recovery_state = setup_recovery_system(
        "presentation", text_dict, slide_metadata, source_language, target_language, resume_file
    )
    
    # Skip already translated items if resuming
    if resume_file:
        # Update the text_dict to exclude already translated items
        for key in recovery_state["translated_items"]:
            if key in text_dict:
                text_dict.pop(key)
        
        print(f"Resuming translation: {len(recovery_state['translated_items'])} items already translated, {len(text_dict)} remaining")
    
    # Deduplicate content to reduce translation costs
    unique_dict, duplicates_map = deduplicate_content(text_dict)
    
    # Split the deduplicated content into manageable batches
    batches = split_dict_into_smart_batches(unique_dict)
    
    # Track which batches are already completed (if resuming)
    completed_batch_indices = set(recovery_state.get("completed_batches", []))
    
    # Create a progress bar
    progress = create_progress_bar(
        total=len(unique_dict),
        desc=f"Translating {source_language} → {target_language}",
        web_state=web_state
    )
    
    # Process batches
    unique_translated_dict = recovery_state.get("translated_items", {})
    
    for batch_index, batch in enumerate(batches):
        # Skip already completed batches
        if batch_index in completed_batch_indices:
            progress.update(len(batch))
            continue
        
        try:
            # Translate this batch
            progress.set_description(f"Translating batch {batch_index+1}/{len(batches)}")
            translated_batch = translate_batch(
                batch, batch_index, slide_metadata, 
                source_language, target_language, api_key
            )
            
            # Add the translated items to our results
            unique_translated_dict.update(translated_batch)
            
            # Update the recovery state
            recovery_state["translated_items"].update(translated_batch)
            recovery_state["completed_batches"].append(batch_index)
            save_recovery_state()
            
            # Update progress bar
            progress.update(len(batch))
            
        except Exception as e:
            print(f"Error processing batch {batch_index}: {str(e)}")
            recovery_state["failed_batches"].append(batch_index)
            save_recovery_state()
    
    # Close the progress bar
    progress.close()
    
    # Try to recover any failed batches
    while recovery_state.get("failed_batches", []):
        print(f"Attempting to recover {len(recovery_state['failed_batches'])} failed batches")
        failed_batch_index = recovery_state["failed_batches"][0]
        
        try:
            # Get the batch data
            if failed_batch_index < len(batches):
                failed_batch = batches[failed_batch_index]
                
                # Try to translate with smaller batches
                smaller_batches = split_dict_into_smart_batches(
                    failed_batch, 
                    max_input_tokens=config.MAX_INPUT_TOKENS // 2  # Use smaller batches
                )
                
                for i, small_batch in enumerate(smaller_batches):
                    translated_small_batch = translate_batch(
                        small_batch, f"{failed_batch_index}.{i}", slide_metadata,
                        source_language, target_language, api_key,
                        max_retries=config.MAX_RETRIES + 1  # Extra retry for failed batches
                    )
                    
                    # Add the translated items to our results
                    unique_translated_dict.update(translated_small_batch)
                    
                    # Update the recovery state
                    recovery_state["translated_items"].update(translated_small_batch)
                
                # Mark the batch as completed
                recovery_state["completed_batches"].append(failed_batch_index)
                recovery_state["failed_batches"].remove(failed_batch_index)
                save_recovery_state()
                
            else:
                print(f"Invalid batch index: {failed_batch_index}")
                recovery_state["failed_batches"].remove(failed_batch_index)
                save_recovery_state()
                
        except Exception as e:
            print(f"Failed to recover batch {failed_batch_index}: {str(e)}")
            # Move to the next failed batch
            recovery_state["failed_batches"].remove(failed_batch_index)
            recovery_state["failed_batches"].append(failed_batch_index)  # Move to the end
            save_recovery_state()
    
    # Reconstruct the full translation dictionary
    print("Reconstructing full translation dictionary...")
    full_translated_dict = {}
    
    # Add all unique translations
    for key, value in unique_translated_dict.items():
        full_translated_dict[key] = value
    
    # Add all duplicates using the mapping
    for original_key, rep_key in duplicates_map.items():
        if rep_key in unique_translated_dict:
            full_translated_dict[original_key] = unique_translated_dict[rep_key]
    
    print(f"Translation complete: {len(full_translated_dict)} items translated")
    
    # Check for any missing translations
    missing_keys = set(text_dict.keys()) - set(full_translated_dict.keys())
    if missing_keys:
        print(f"Warning: {len(missing_keys)} items were not translated")
    
    return full_translated_dict

def translate_slides(presentation_id, source_language=None, target_language=None, resume_file=None, api_key=None, web_state=None):
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
        web_state['console_output'] += f"Found {len(text_dict)} text elements across {len(slide_metadata)} slides\n"
    
    # Translate the text
    print(f"Translating from {source_language} to {target_language}...")
    translated_texts = translate_text(
        text_dict, slide_metadata, source_language, target_language, 
        resume_file, api_key, web_state
    )
    
    # Update the presentation with translated text
    print("Creating and updating presentation with translated text...")
    new_presentation_id = update_slides(
        slides_service, drive_service, presentation_id, 
        translated_texts, target_language
    )
    
    # If web state is provided, update it with the result
    if web_state:
        web_state['result_url'] = f"https://docs.google.com/presentation/d/{new_presentation_id}/edit"
        web_state['console_output'] += f"Translation completed! Presentation available at: {web_state['result_url']}\n"
    
    print(f"Translation completed!")
    print(f"Translated presentation ID: {new_presentation_id}")
    
    return new_presentation_id 