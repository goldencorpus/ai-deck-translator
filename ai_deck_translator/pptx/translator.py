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

from ..utils.batch import split_dict_into_smart_batches, deduplicate_content
from ..utils.recovery import setup_recovery_system
from ..utils.progress import create_progress_bar
from ..utils.logging import get_logger
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
    json_content = re.sub(r'```json\s*', '', json_content)
    json_content = re.sub(r'\s*```', '', json_content)
    
    # Fix missing quotes around property names
    json_content = re.sub(r'(\s*?)(\w+)(:)', r'\1"\2"\3', json_content)
    
    # Fix trailing commas in arrays and objects
    json_content = re.sub(r',\s*}', '}', json_content)
    json_content = re.sub(r',\s*\]', ']', json_content)
    
    # Fix missing quotes around string values
    def fix_property_names(match):
        prop_name = match.group(1)
        colon = match.group(2)
        value = match.group(3).strip()
        
        # If value is not already quoted and not a number, boolean, null, array or object
        if not (value.startswith('"') or value.startswith("'") or 
                value.startswith('[') or value.startswith('{') or 
                value == 'null' or value == 'true' or value == 'false' or 
                re.match(r'^-?\d+(\.\d+)?$', value)):
            return f'"{prop_name}"{colon}"{value}"'
        return f'"{prop_name}"{colon}{value}'
    
    json_content = re.sub(r'"(\w+)"(\s*:)\s*([^",\{\[\]\}\s][^,\{\[\]\}\s]*)', fix_property_names, json_content)
    
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
        r'```json\s*([\s\S]*?)\s*```',  # JSON with markdown code markers
        r'```\s*([\s\S]*?)\s*```',       # Any code block
        r'(\{\s*"[^"]+"\s*:[\s\S]*\})'   # Raw JSON object
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

def translate_batch(batch, batch_index, slide_metadata, source_language, target_language, api_key=None, max_retries=3, cost_tracker=None):
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
        return re.sub(r'\s+', ' ', text).strip()
    
    def estimate_cost(prompt_tokens, completion_tokens, model="claude-3-7-sonnet"):
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
                            "context": f"Slide {slide.get('slide_number', 0)}, {element.get('type', 'element')}"
                        }
                        break
    
    # Create the system prompt
    system_prompt = f"""You are a professional translator specializing in PowerPoint presentations. 
Your task is to translate the content from {source_language} to {target_language} while preserving the meaning, tone, and formatting.

IMPORTANT GUIDELINES:
1. Translate all text accurately while maintaining the original meaning and tone.
2. Preserve formatting elements like bullet points, numbering, and paragraph breaks.
3. Maintain any technical terminology appropriately.
4. For tables, preserve the tabular structure in your translation.
5. Respect the context of each text element (slide title, body text, etc.).
6. Do not add or remove content; translate only what is provided.
7. Return your response as a JSON object with the same structure as the input.

PRIVACY NOTICE:
- Do not store or remember any content from this presentation.
- Do not reference the content in future conversations.
- Treat all content as confidential business information.

The content to translate is provided as a JSON object where each key is a unique identifier and each value is the text to translate.
"""

    # Create the user prompt
    user_prompt = f"""Please translate the following presentation content from {source_language} to {target_language}.

Here is the content to translate (with context information):
```json
{json.dumps(content_to_translate, ensure_ascii=False, indent=2)}
```

Context information (to help you understand the content better):
```json
{json.dumps(context_info, ensure_ascii=False, indent=2)}
```

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
                model="claude-3-7-sonnet",
                max_tokens=150000,
                temperature=0.0,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
                metadata={
                    "user_id": "anonymous_user"
                }
            )
            
            # Track costs if requested
            if cost_tracker is not None:
                prompt_tokens = response.usage.input_tokens
                completion_tokens = response.usage.output_tokens
                cost = estimate_cost(prompt_tokens, completion_tokens)
                
                cost_tracker["total_prompt_tokens"] = cost_tracker.get("total_prompt_tokens", 0) + prompt_tokens
                cost_tracker["total_completion_tokens"] = cost_tracker.get("total_completion_tokens", 0) + completion_tokens
                cost_tracker["total_cost"] = cost_tracker.get("total_cost", 0) + cost
                
                logger.info(f"Batch {batch_index}: {prompt_tokens} prompt tokens, {completion_tokens} completion tokens, estimated cost: ${cost:.4f}")
            
            # Extract the JSON from the response
            json_content = extract_json_blocks(response.content[0].text)
            
            if json_content:
                try:
                    translated_batch = json.loads(json_content)
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
        logger.error(f"Failed to translate batch {batch_index} after {max_retries} retries")
        return {}
    
    return translated_batch

def translate_text(text_dict, slide_metadata, source_language, target_language, resume_file=None, api_key=None):
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
    # Set up recovery system
    file_id = f"pptx_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    recovery_system = setup_recovery_system(file_id, text_dict, slide_metadata, source_language, target_language, resume_file)
    
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
        batches = split_dict_into_smart_batches(unique_texts, max_input_tokens=100000)
        
        translated_texts = {}
        remaining_batches = list(enumerate(batches))
    
    # Set up progress tracking
    total_batches = len(remaining_batches)
    progress_bar = create_progress_bar(total_batches, desc="Translating")
    
    # Track API costs
    cost_tracker = {
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
        "total_cost": 0
    }
    
    # Process each batch
    while remaining_batches:
        batch_index, batch = remaining_batches.pop(0)
        
        logger.info(f"Translating batch {batch_index + 1}/{total_batches} ({len(batch)} items)")
        
        # Translate the batch
        batch_translations = translate_batch(
            batch, 
            batch_index, 
            slide_metadata, 
            source_language, 
            target_language, 
            api_key=api_key,
            cost_tracker=cost_tracker
        )
        
        # Update translated texts
        translated_texts.update(batch_translations)
        
        # Save recovery state
        recovery_system["translated_texts"] = translated_texts
        recovery_system["remaining_batches"] = remaining_batches
        recovery_system["save_recovery_state"]()
        
        # Update progress
        progress_bar.update(1)
    
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
    
    # Log cost information
    if cost_tracker["total_cost"] > 0:
        logger.info(f"Translation complete. Total tokens: {cost_tracker['total_prompt_tokens']} input, {cost_tracker['total_completion_tokens']} output")
        logger.info(f"Estimated cost: ${cost_tracker['total_cost']:.2f}")
    
    progress_bar.close()
    return translated_texts

def translate_pptx(input_file, output_file, source_language="en", target_language="fr", resume_file=None, api_key=None):
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
    
    logger.info(f"Extracted {len(text_dict)} text elements from {len(slide_metadata)} slides")
    
    # Translate the text
    logger.info("Translating text...")
    translated_texts = translate_text(
        text_dict, 
        slide_metadata, 
        source_language, 
        target_language, 
        resume_file=resume_file,
        api_key=api_key
    )
    
    # Update the presentation with translated text
    logger.info("Updating presentation with translated text...")
    success = update_slides(input_file, output_file, translated_texts)
    
    if success:
        logger.info(f"Translation complete. Saved to {output_file}")
        return True
    else:
        logger.error("Failed to update presentation with translated text")
        return False

def list_recovery_files():
    """
    List available recovery files for PPTX translations.
    
    Returns:
        list: List of recovery files with metadata
    """
    recovery_dir = os.path.join(os.getcwd(), "translation_recovery")
    if not os.path.exists(recovery_dir):
        return []
    
    recovery_files = [f for f in os.listdir(recovery_dir) if f.startswith("recovery_pptx_") and f.endswith(".json")]
    
    result = []
    for file in recovery_files:
        try:
            file_path = os.path.join(recovery_dir, file)
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                result.append({
                    "file": file,
                    "path": file_path,
                    "timestamp": data.get("timestamp", "Unknown"),
                    "source_language": data.get("source_language", "Unknown"),
                    "target_language": data.get("target_language", "Unknown"),
                    "progress": f"{len(data.get('translated_texts', {}))} / {len(data.get('text_dict', {}))}"
                })
        except:
            # Skip files that can't be parsed
            pass
    
    return sorted(result, key=lambda x: x["timestamp"], reverse=True)
