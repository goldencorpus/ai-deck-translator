"""
Enhanced PPTX Translator module with hybrid model selection, optimized strategies,
quality assurance, and parallel processing.
"""
import os
import json
import anthropic
import re
import time
import openai
import google.generativeai as genai
from datetime import datetime
from tqdm import tqdm
import sys
import hashlib
import concurrent.futures
import threading
from typing import Dict, List, Tuple, Any, Optional, Union
import difflib
import queue

from ..utils.batch import split_dict_into_smart_batches, deduplicate_content
from ..utils.recovery import setup_recovery_system
from ..utils.progress import create_progress_bar
from ..utils.logging import get_logger
from .extractor import extract_text
from .updater import update_slides

# Set up logging
logger = get_logger(__name__)

# Define model constants
MODEL_CLAUDE_35_SONNET = "claude-3-5-sonnet"
MODEL_CLAUDE_35_HAIKU = "claude-3-5-haiku"
MODEL_GPT_4O = "gpt-4o"
MODEL_GPT_4O_MINI = "gpt-4o-mini"
MODEL_GEMINI_15_PRO = "gemini-1.5-pro"
MODEL_GEMINI_15_FLASH = "gemini-1.5-flash"

# Translation quality levels
QUALITY_PROFESSIONAL = "professional"  # Highest quality for customer-facing content
QUALITY_STANDARD = "standard"          # Good quality for general business use
QUALITY_DRAFT = "draft"                # Basic quality for internal drafts
QUALITY_ECONOMY = "economy"            # Lowest cost option

# Cache directory for storing translations
CACHE_DIR = os.path.expanduser("~/.translator_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# Thread-safe progress bar and cost tracking
progress_lock = threading.Lock()
cost_tracker_lock = threading.Lock()

# Quality assurance thresholds
QA_LENGTH_RATIO_THRESHOLD = 0.5  # Minimum ratio of translation length to original length
QA_MAX_LENGTH_RATIO_THRESHOLD = 2.0  # Maximum ratio of translation length to original length
QA_SIMILARITY_THRESHOLD = 0.3  # Minimum similarity for technical terms preservation

# Common technical terms that should be preserved across languages
COMMON_TECHNICAL_TERMS = [
    "API", "JSON", "XML", "HTML", "CSS", "HTTP", "HTTPS", "REST", "SDK", 
    "UI", "UX", "CPU", "GPU", "RAM", "SQL", "NoSQL", "URL", "URI", "JWT",
    "OAuth", "AI", "ML", "NLP", "IoT", "AWS", "Azure", "GCP", "Docker", "Kubernetes"
]

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

def get_model_pricing(model):
    """
    Get pricing information for a specific model.
    
    Args:
        model: Model identifier
        
    Returns:
        dict: Dictionary with input and output costs per million tokens
    """
    pricing = {
        MODEL_CLAUDE_35_SONNET: {"input": 3.00, "output": 15.00, "context_window": 200000},
        MODEL_CLAUDE_35_HAIKU: {"input": 1.00, "output": 5.00, "context_window": 200000},
        MODEL_GPT_4O: {"input": 2.50, "output": 10.00, "context_window": 128000},
        MODEL_GPT_4O_MINI: {"input": 0.15, "output": 6.00, "context_window": 128000},
        MODEL_GEMINI_15_PRO: {"input": 1.25, "output": 2.50, "context_window": 1000000},
        MODEL_GEMINI_15_FLASH: {"input": 0.075, "output": 0.30, "context_window": 1000000},
    }
    
    # Default to Claude 3.5 Sonnet if model not found
    return pricing.get(model, pricing[MODEL_CLAUDE_35_SONNET])

def estimate_cost(prompt_tokens, completion_tokens, model=MODEL_CLAUDE_35_SONNET):
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

def select_model_for_content(content, quality_level, source_language, target_language, content_length=None):
    """
    Select the most appropriate model based on content characteristics and quality requirements.
    
    Args:
        content: Dictionary of content to translate or sample of content
        quality_level: Required quality level (professional, standard, draft, economy)
        source_language: Source language code
        target_language: Target language code
        content_length: Optional total content length for better decision making
        
    Returns:
        str: Selected model identifier
    """
    # Check if Japanese translation is involved
    japanese_involved = source_language == "ja" or target_language == "ja"
    
    # Estimate content complexity based on average sentence length and presence of technical terms
    sample_text = next(iter(content.values())) if isinstance(content, dict) else str(content)
    sentences = re.split(r'[.!?]', sample_text)
    avg_sentence_length = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)
    
    # Check for technical content (simplified heuristic)
    technical_terms_pattern = r'\b(API|JSON|XML|HTML|SDK|UI|UX|CPU|GPU|RAM|HTTP|HTTPS|SQL|NoSQL|backend|frontend)\b'
    has_technical_terms = bool(re.search(technical_terms_pattern, sample_text, re.IGNORECASE))
    
    # Model selection based on quality level and content characteristics
    if quality_level == QUALITY_PROFESSIONAL:
        # For professional quality, prioritize accuracy and context understanding
        if japanese_involved:
            return MODEL_CLAUDE_35_SONNET  # Best for Japanese translation
        elif has_technical_terms:
            return MODEL_CLAUDE_35_SONNET  # Good for technical content
        else:
            return MODEL_GPT_4O  # Good general performance
            
    elif quality_level == QUALITY_STANDARD:
        # For standard quality, balance performance and cost
        if japanese_involved:
            return MODEL_CLAUDE_35_HAIKU  # Good for Japanese at lower cost
        elif has_technical_terms:
            return MODEL_GPT_4O  # Good for technical content
        else:
            return MODEL_GEMINI_15_PRO  # Good balance of quality and cost
            
    elif quality_level == QUALITY_DRAFT:
        # For draft quality, prioritize cost while maintaining reasonable quality
        if japanese_involved:
            return MODEL_GPT_4O_MINI  # Acceptable for Japanese at lower cost
        else:
            return MODEL_GEMINI_15_FLASH  # Low cost option
            
    elif quality_level == QUALITY_ECONOMY:
        # For economy, prioritize lowest cost
        return MODEL_GEMINI_15_FLASH  # Lowest cost option
        
    # Default to Claude 3.5 Sonnet for safety
    return MODEL_CLAUDE_35_SONNET

def get_model_specific_prompt(model, source_language, target_language, content_to_translate, context_info):
    """
    Generate model-specific prompts optimized for each model's strengths.
    
    Args:
        model: Model identifier
        source_language: Source language code
        target_language: Target language code
        content_to_translate: Dictionary of content to translate
        context_info: Dictionary of context information
        
    Returns:
        tuple: (system_prompt, user_prompt) for the specified model
    """
    # Base system prompt template
    base_system_prompt = f"""You are a professional translator specializing in PowerPoint presentations. 
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

    # Base user prompt template
    base_user_prompt = f"""Please translate the following presentation content from {source_language} to {target_language}.

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

    # Model-specific optimizations
    if model == MODEL_CLAUDE_35_SONNET or model == MODEL_CLAUDE_35_HAIKU:
        # Claude models excel with detailed instructions and context
        system_prompt = base_system_prompt + """
ADDITIONAL GUIDELINES FOR CLAUDE:
- Pay special attention to cultural nuances in the translation.
- Maintain the formality level of the original text.
- For ambiguous terms, prefer the most contextually appropriate translation.
- Preserve technical terms in their original form when appropriate.
"""
        user_prompt = base_user_prompt
        
    elif model.startswith("gpt"):
        # GPT models work well with structured, concise instructions
        system_prompt = base_system_prompt + """
ADDITIONAL GUIDELINES FOR GPT:
- Focus on accuracy and natural-sounding translations.
- Maintain consistent terminology throughout the document.
- Ensure proper handling of technical terms.
- Preserve the original formatting exactly.
"""
        user_prompt = base_user_prompt + """
IMPORTANT: Your response must be a valid JSON object with no additional text.
The JSON structure must exactly match the input structure.
"""
        
    elif model.startswith("gemini"):
        # Gemini models benefit from clear, direct instructions
        system_prompt = base_system_prompt
        user_prompt = base_user_prompt + """
IMPORTANT REMINDER:
1. Return ONLY a valid JSON object.
2. The JSON must have the exact same keys as the input.
3. Do not add any explanatory text before or after the JSON.
4. Ensure all translations maintain the original formatting.
5. Keep technical terms in their original form when appropriate.
"""
    
    # Add language-specific instructions
    if target_language == "ja":
        system_prompt += """
JAPANESE TRANSLATION GUIDELINES:
- Use appropriate keigo (honorific language) based on the context.
- Pay attention to nuances in Japanese expressions.
- Ensure proper use of particles and sentence structure.
- Consider cultural context when translating idiomatic expressions.
- Preserve technical terms in their original form when appropriate.
"""
    elif source_language == "ja":
        system_prompt += """
JAPANESE SOURCE GUIDELINES:
- Pay attention to implicit subjects that may be omitted in Japanese.
- Carefully translate keigo (honorific language) to appropriate formality levels.
- Expand contextual information that may be implicit in Japanese.
- Preserve technical terms in their original form when appropriate.
"""
        
    return system_prompt, user_prompt

def create_cache_key(content, source_language, target_language, model):
    """
    Create a unique cache key for a translation request.
    
    Args:
        content: Text content to translate
        source_language: Source language code
        target_language: Target language code
        model: Model identifier
        
    Returns:
        str: Cache key
    """
    # Create a string representation of the request
    request_str = f"{content}|{source_language}|{target_language}|{model}"
    
    # Generate a hash of the request string
    return hashlib.md5(request_str.encode('utf-8')).hexdigest()

def get_cached_translation(content, source_language, target_language, model):
    """
    Check if a translation is available in the cache.
    
    Args:
        content: Text content to translate
        source_language: Source language code
        target_language: Target language code
        model: Model identifier
        
    Returns:
        str or None: Cached translation if available, None otherwise
    """
    cache_key = create_cache_key(content, source_language, target_language, model)
    cache_file = os.path.join(CACHE_DIR, cache_key)
    
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading from cache: {e}")
    
    return None

def save_to_cache(content, translation, source_language, target_language, model):
    """
    Save a translation to the cache.
    
    Args:
        content: Original text content
        translation: Translated text
        source_language: Source language code
        target_language: Target language code
        model: Model identifier
    """
    cache_key = create_cache_key(content, source_language, target_language, model)
    cache_file = os.path.join(CACHE_DIR, cache_key)
    
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            f.write(translation)
    except Exception as e:
        logger.error(f"Error writing to cache: {e}")

def translate_with_anthropic(content_to_translate, context_info, source_language, target_language, model, api_key=None, max_retries=3):
    """
    Translate content using Anthropic Claude models.
    
    Args:
        content_to_translate: Dictionary of content to translate
        context_info: Dictionary of context information
        source_language: Source language code
        target_language: Target language code
        model: Model identifier (must be a Claude model)
        api_key: Anthropic API key (optional)
        max_retries: Maximum number of retries for API calls
        
    Returns:
        tuple: (translated_content, usage_info)
    """
    # Use provided API key or get from environment
    client = anthropic.Anthropic(api_key=api_key or os.environ.get("CLAUDE_API_KEY"))
    
    # Get model-specific prompts
    system_prompt, user_prompt = get_model_specific_prompt(
        model, source_language, target_language, content_to_translate, context_info
    )
    
    # Initialize variables for retry logic
    retry_count = 0
    translated_batch = None
    usage_info = {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0}
    
    # Try to translate with retries
    while retry_count <= max_retries:
        try:
            # Call the Anthropic API
            response = client.messages.create(
                model=model,
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
            
            # Track usage
            usage_info["prompt_tokens"] = response.usage.input_tokens
            usage_info["completion_tokens"] = response.usage.output_tokens
            usage_info["cost"] = estimate_cost(
                response.usage.input_tokens, 
                response.usage.output_tokens,
                model
            )
            
            # Extract the JSON from the response
            json_content = extract_json_blocks(response.content[0].text)
            
            if json_content:
                try:
                    translated_batch = json.loads(json_content)
                    break  # Success, exit the retry loop
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing JSON: {e}")
                    retry_count += 1
            else:
                logger.error(f"No valid JSON found in response")
                retry_count += 1
                
        except Exception as e:
            logger.error(f"Error in API call: {e}")
            retry_count += 1
            time.sleep(2)  # Wait before retrying
    
    # If we couldn't translate after all retries, return an empty dict
    if translated_batch is None:
        logger.error(f"Failed to translate after {max_retries} retries")
        return {}, usage_info
    
    return translated_batch, usage_info

def translate_with_openai(content_to_translate, context_info, source_language, target_language, model, api_key=None, max_retries=3):
    """
    Translate content using OpenAI GPT models.
    
    Args:
        content_to_translate: Dictionary of content to translate
        context_info: Dictionary of context information
        source_language: Source language code
        target_language: Target language code
        model: Model identifier (must be a GPT model)
        api_key: OpenAI API key (optional)
        max_retries: Maximum number of retries for API calls
        
    Returns:
        tuple: (translated_content, usage_info)
    """
    # Use provided API key or get from environment
    client = openai.OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
    
    # Get model-specific prompts
    system_prompt, user_prompt = get_model_specific_prompt(
        model, source_language, target_language, content_to_translate, context_info
    )
    
    # Initialize variables for retry logic
    retry_count = 0
    translated_batch = None
    usage_info = {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0}
    
    # Try to translate with retries
    while retry_count <= max_retries:
        try:
            # Call the OpenAI API
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            
            # Track usage
            usage_info["prompt_tokens"] = response.usage.prompt_tokens
            usage_info["completion_tokens"] = response.usage.completion_tokens
            usage_info["cost"] = estimate_cost(
                response.usage.prompt_tokens, 
                response.usage.completion_tokens,
                model
            )
            
            # Extract the JSON from the response
            json_content = response.choices[0].message.content
            
            if json_content:
                try:
                    translated_batch = json.loads(json_content)
                    break  # Success, exit the retry loop
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing JSON: {e}")
                    retry_count += 1
            else:
                logger.error(f"No valid JSON found in response")
                retry_count += 1
                
        except Exception as e:
            logger.error(f"Error in API call: {e}")
            retry_count += 1
            time.sleep(2)  # Wait before retrying
    
    # If we couldn't translate after all retries, return an empty dict
    if translated_batch is None:
        logger.error(f"Failed to translate after {max_retries} retries")
        return {}, usage_info
    
    return translated_batch, usage_info

def translate_with_gemini(content_to_translate, context_info, source_language, target_language, model, api_key=None, max_retries=3):
    """
    Translate content using Google Gemini models.
    
    Args:
        content_to_translate: Dictionary of content to translate
        context_info: Dictionary of context information
        source_language: Source language code
        target_language: Target language code
        model: Model identifier (must be a Gemini model)
        api_key: Google API key (optional)
        max_retries: Maximum number of retries for API calls
        
    Returns:
        tuple: (translated_content, usage_info)
    """
    # Configure the Gemini API
    genai.configure(api_key=api_key or os.environ.get("GOOGLE_API_KEY"))
    
    # Map model names to Gemini model names
    model_mapping = {
        MODEL_GEMINI_15_PRO: "gemini-1.5-pro",
        MODEL_GEMINI_15_FLASH: "gemini-1.5-flash"
    }
    gemini_model = model_mapping.get(model, "gemini-1.5-pro")
    
    # Get model-specific prompts
    system_prompt, user_prompt = get_model_specific_prompt(
        model, source_language, target_language, content_to_translate, context_info
    )
    
    # Combine prompts for Gemini
    combined_prompt = f"{system_prompt}\n\n{user_prompt}"
    
    # Initialize variables for retry logic
    retry_count = 0
    translated_batch = None
    usage_info = {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0}
    
    # Try to translate with retries
    while retry_count <= max_retries:
        try:
            # Create a client for the specified model
            model = genai.GenerativeModel(gemini_model)
            
            # Call the Gemini API
            response = model.generate_content(combined_prompt)
            
            # Extract the text from the response
            response_text = response.text
            
            # Estimate token usage (Gemini doesn't provide token counts)
            # Rough estimate: 4 characters per token
            prompt_tokens = len(combined_prompt) // 4
            completion_tokens = len(response_text) // 4
            
            # Track usage
            usage_info["prompt_tokens"] = prompt_tokens
            usage_info["completion_tokens"] = completion_tokens
            usage_info["cost"] = estimate_cost(
                prompt_tokens, 
                completion_tokens,
                model
            )
            
            # Extract the JSON from the response
            json_content = extract_json_blocks(response_text)
            
            if json_content:
                try:
                    translated_batch = json.loads(json_content)
                    break  # Success, exit the retry loop
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing JSON: {e}")
                    retry_count += 1
            else:
                logger.error(f"No valid JSON found in response")
                retry_count += 1
                
        except Exception as e:
            logger.error(f"Error in API call: {e}")
            retry_count += 1
            time.sleep(2)  # Wait before retrying
    
    # If we couldn't translate after all retries, return an empty dict
    if translated_batch is None:
        logger.error(f"Failed to translate after {max_retries} retries")
        return {}, usage_info
    
    return translated_batch, usage_info

def perform_quality_check(original_text, translated_text, source_language, target_language):
    """
    Perform quality checks on a translation.
    
    Args:
        original_text: Original text
        translated_text: Translated text
        source_language: Source language code
        target_language: Target language code
        
    Returns:
        tuple: (is_valid, issues)
    """
    issues = []
    
    # Check 1: Length ratio
    # Translation should not be too short or too long compared to original
    original_length = len(original_text)
    translated_length = len(translated_text)
    
    if original_length > 0:
        length_ratio = translated_length / original_length
        
        if length_ratio < QA_LENGTH_RATIO_THRESHOLD:
            issues.append(f"Translation is too short (ratio: {length_ratio:.2f})")
        elif length_ratio > QA_MAX_LENGTH_RATIO_THRESHOLD:
            issues.append(f"Translation is too long (ratio: {length_ratio:.2f})")
    
    # Check 2: Formatting preservation
    # Check if bullet points, numbering, and paragraph breaks are preserved
    original_bullets = len(re.findall(r'^\s*[•\-\*]\s+', original_text, re.MULTILINE))
    translated_bullets = len(re.findall(r'^\s*[•\-\*]\s+', translated_text, re.MULTILINE))
    
    if original_bullets != translated_bullets:
        issues.append(f"Bullet point count mismatch: {original_bullets} vs {translated_bullets}")
    
    original_numbering = len(re.findall(r'^\s*\d+\.\s+', original_text, re.MULTILINE))
    translated_numbering = len(re.findall(r'^\s*\d+\.\s+', translated_text, re.MULTILINE))
    
    if original_numbering != translated_numbering:
        issues.append(f"Numbered list count mismatch: {original_numbering} vs {translated_numbering}")
    
    original_paragraphs = len(re.split(r'\n\s*\n', original_text))
    translated_paragraphs = len(re.split(r'\n\s*\n', translated_text))
    
    if original_paragraphs != translated_paragraphs:
        issues.append(f"Paragraph count mismatch: {original_paragraphs} vs {translated_paragraphs}")
    
    # Check 3: Technical term preservation
    # Technical terms should be preserved in the translation
    for term in COMMON_TECHNICAL_TERMS:
        if term in original_text and term not in translated_text:
            # Check if there's a similar term in the translation
            similar_terms = [word for word in translated_text.split() if difflib.SequenceMatcher(None, term, word).ratio() > QA_SIMILARITY_THRESHOLD]
            if not similar_terms:
                issues.append(f"Technical term '{term}' not preserved in translation")
    
    # Check 4: Placeholder preservation
    # Placeholders like {variable} should be preserved
    original_placeholders = re.findall(r'\{[^}]+\}', original_text)
    for placeholder in original_placeholders:
        if placeholder not in translated_text:
            issues.append(f"Placeholder '{placeholder}' not preserved in translation")
    
    # Check 5: URL preservation
    # URLs should be preserved in the translation
    original_urls = re.findall(r'https?://[^\s]+', original_text)
    for url in original_urls:
        if url not in translated_text:
            issues.append(f"URL '{url}' not preserved in translation")
    
    return len(issues) == 0, issues

def fix_translation_issues(original_text, translated_text, issues, source_language, target_language, model, api_key=None):
    """
    Fix issues in a translation using a specialized prompt.
    
    Args:
        original_text: Original text
        translated_text: Translation with issues
        issues: List of identified issues
        source_language: Source language code
        target_language: Target language code
        model: Model identifier
        api_key: API key (optional)
        
    Returns:
        str: Fixed translation
    """
    # Create a specialized prompt for fixing issues
    system_prompt = f"""You are a professional translation editor. Your task is to fix issues in a translation from {source_language} to {target_language}.

IMPORTANT GUIDELINES:
1. Preserve the meaning of the original text.
2. Fix the specific issues identified in the translation.
3. Do not add or remove content beyond what's needed to fix the issues.
4. Preserve all formatting, technical terms, placeholders, and URLs.
5. Return only the fixed translation, without any explanations or notes.
"""

    user_prompt = f"""Please fix the following issues in this translation:

Original text ({source_language}):
```
{original_text}
```

Current translation ({target_language}) with issues:
```
{translated_text}
```

Issues to fix:
{chr(10).join(f"- {issue}" for issue in issues)}

Please provide the corrected translation, preserving all formatting, technical terms, placeholders, and URLs.
"""

    # Use the appropriate API based on the model
    if model.startswith("claude"):
        client = anthropic.Anthropic(api_key=api_key or os.environ.get("CLAUDE_API_KEY"))
        response = client.messages.create(
            model=model,
            max_tokens=150000,
            temperature=0.0,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        fixed_translation = response.content[0].text
        
    elif model.startswith("gpt"):
        client = openai.OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0
        )
        fixed_translation = response.choices[0].message.content
        
    elif model.startswith("gemini"):
        genai.configure(api_key=api_key or os.environ.get("GOOGLE_API_KEY"))
        model_mapping = {
            MODEL_GEMINI_15_PRO: "gemini-1.5-pro",
            MODEL_GEMINI_15_FLASH: "gemini-1.5-flash"
        }
        gemini_model = model_mapping.get(model, "gemini-1.5-pro")
        model = genai.GenerativeModel(gemini_model)
        response = model.generate_content(f"{system_prompt}\n\n{user_prompt}")
        fixed_translation = response.text
    
    # Clean up the response
    fixed_translation = fixed_translation.strip()
    
    # Remove any markdown code block markers
    fixed_translation = re.sub(r'```.*?\n', '', fixed_translation)
    fixed_translation = re.sub(r'\n```', '', fixed_translation)
    
    return fixed_translation

def translate_batch_worker(args):
    """
    Worker function for parallel batch translation.
    
    Args:
        args: Tuple containing (batch, batch_index, slide_metadata, source_language, 
              target_language, quality_level, api_key, max_retries, use_cache, qa_enabled)
        
    Returns:
        tuple: (batch_index, translated_batch, usage_info)
    """
    (batch, batch_index, slide_metadata, source_language, target_language, 
     quality_level, api_key, max_retries, use_cache, qa_enabled) = args
    
    try:
        def clean_text(text):
            """Clean text for better translation results"""
            return re.sub(r'\s+', ' ', text).strip()
        
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
        
        # Select the appropriate model based on content and quality requirements
        selected_model = select_model_for_content(
            content_to_translate, 
            quality_level, 
            source_language, 
            target_language,
            content_length=len(json.dumps(content_to_translate, ensure_ascii=False))
        )
        
        logger.info(f"Batch {batch_index}: Selected model {selected_model} for quality level {quality_level}")
        
        # Check cache for each item if enabled
        if use_cache:
            cached_translations = {}
            for key, value in content_to_translate.items():
                cached = get_cached_translation(value, source_language, target_language, selected_model)
                if cached:
                    cached_translations[key] = cached
                    logger.info(f"Batch {batch_index}: Cache hit for item {key}")
            
            # If all items were found in cache, return them
            if len(cached_translations) == len(content_to_translate):
                logger.info(f"Batch {batch_index}: All items found in cache")
                return batch_index, cached_translations, {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0, "model": selected_model}
            
            # Remove cached items from content to translate
            for key in cached_translations:
                if key in content_to_translate:
                    del content_to_translate[key]
            
            # If all items were cached, return the cached translations
            if not content_to_translate:
                return batch_index, cached_translations, {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0, "model": selected_model}
        
        # Translate using the appropriate API based on the selected model
        translated_batch = {}
        usage_info = {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0, "model": selected_model}
        
        if selected_model.startswith("claude"):
            translated_batch, usage_info = translate_with_anthropic(
                content_to_translate, 
                context_info, 
                source_language, 
                target_language, 
                selected_model, 
                api_key=api_key, 
                max_retries=max_retries
            )
        elif selected_model.startswith("gpt"):
            translated_batch, usage_info = translate_with_openai(
                content_to_translate, 
                context_info, 
                source_language, 
                target_language, 
                selected_model, 
                api_key=api_key, 
                max_retries=max_retries
            )
        elif selected_model.startswith("gemini"):
            translated_batch, usage_info = translate_with_gemini(
                content_to_translate, 
                context_info, 
                source_language, 
                target_language, 
                selected_model, 
                api_key=api_key, 
                max_retries=max_retries
            )
        
        usage_info["model"] = selected_model
        
        # Perform quality checks if enabled
        if qa_enabled:
            qa_issues = {}
            fixed_translations = {}
            
            for key, translated_text in translated_batch.items():
                original_text = content_to_translate.get(key, "")
                is_valid, issues = perform_quality_check(original_text, translated_text, source_language, target_language)
                
                if not is_valid:
                    qa_issues[key] = issues
                    logger.info(f"Batch {batch_index}: Quality issues detected for item {key}: {issues}")
                    
                    # Fix the issues
                    fixed_translation = fix_translation_issues(
                        original_text, 
                        translated_text, 
                        issues, 
                        source_language, 
                        target_language, 
                        selected_model, 
                        api_key=api_key
                    )
                    
                    fixed_translations[key] = fixed_translation
                    logger.info(f"Batch {batch_index}: Fixed translation for item {key}")
            
            # Update translations with fixed versions
            translated_batch.update(fixed_translations)
        
        # Cache translations if enabled
        if use_cache:
            for key, value in translated_batch.items():
                original_text = content_to_translate.get(key)
                if original_text:
                    save_to_cache(original_text, value, source_language, target_language, selected_model)
            
            # Merge with cached translations
            translated_batch.update(cached_translations)
        
        return batch_index, translated_batch, usage_info
        
    except Exception as e:
        logger.error(f"Error in batch {batch_index}: {e}")
        return batch_index, {}, {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0, "model": "error"}

def translate_text(text_dict, slide_metadata, source_language, target_language, quality_level=QUALITY_PROFESSIONAL, resume_file=None, api_key=None, use_cache=True, qa_enabled=True, max_workers=4):
    """
    Translate text from a PowerPoint presentation with hybrid model selection and parallel processing.
    
    Args:
        text_dict: Dictionary of text elements to translate
        slide_metadata: Metadata about slides and text elements
        source_language: Source language code
        target_language: Target language code
        quality_level: Required quality level (professional, standard, draft, economy)
        resume_file: Path to a recovery file to resume from (optional)
        api_key: API key (optional)
        use_cache: Whether to use the translation cache
        qa_enabled: Whether to enable quality assurance checks
        max_workers: Maximum number of parallel workers
        
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
        "total_cost": 0,
        "models_used": {}
    }
    
    # Process batches in parallel
    if total_batches > 0:
        # Prepare arguments for worker function
        worker_args = []
        for batch_index, batch in remaining_batches:
            worker_args.append((
                batch, batch_index, slide_metadata, source_language, target_language,
                quality_level, api_key, 3, use_cache, qa_enabled
            ))
        
        # Create a thread-safe queue for results
        result_queue = queue.Queue()
        
        # Create a thread-safe set to track completed batches
        completed_batches = set()
        
        # Process batches in parallel with a thread pool
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(max_workers, total_batches)) as executor:
            # Submit all tasks
            future_to_batch_index = {
                executor.submit(translate_batch_worker, args): args[1]  # batch_index
                for args in worker_args
            }
            
            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_batch_index):
                batch_index = future_to_batch_index[future]
                try:
                    result_batch_index, batch_translations, usage_info = future.result()
                    
                    # Update translated texts
                    with threading.Lock():
                        translated_texts.update(batch_translations)
                        
                        # Update cost tracker
                        with cost_tracker_lock:
                            cost_tracker["total_prompt_tokens"] += usage_info["prompt_tokens"]
                            cost_tracker["total_completion_tokens"] += usage_info["completion_tokens"]
                            cost_tracker["total_cost"] += usage_info["cost"]
                            
                            model = usage_info.get("model", "unknown")
                            if model in cost_tracker["models_used"]:
                                cost_tracker["models_used"][model] += 1
                            else:
                                cost_tracker["models_used"][model] = 1
                        
                        # Mark batch as completed
                        completed_batches.add(batch_index)
                        
                        # Save recovery state
                        recovery_system["translated_texts"] = translated_texts
                        recovery_system["remaining_batches"] = [
                            (idx, batch) for idx, batch in remaining_batches 
                            if idx not in completed_batches
                        ]
                        recovery_system["save_recovery_state"]()
                    
                    # Update progress
                    with progress_lock:
                        progress_bar.update(1)
                        
                except Exception as e:
                    logger.error(f"Error processing batch {batch_index}: {e}")
    
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
    
    # Log cost summary
    logger.info(f"Translation completed. Total cost: ${cost_tracker['total_cost']:.4f}")
    logger.info(f"Total input tokens: {cost_tracker['total_prompt_tokens']}")
    logger.info(f"Total output tokens: {cost_tracker['total_completion_tokens']}")
    logger.info(f"Models used: {cost_tracker['models_used']}")
    
    return translated_texts

def translate_presentation(input_file, output_file, source_language, target_language, quality_level=QUALITY_PROFESSIONAL, resume_file=None, api_key=None, use_cache=True, qa_enabled=True, max_workers=4):
    """
    Translate a PowerPoint presentation with hybrid model selection and parallel processing.
    
    Args:
        input_file: Path to the input PPTX file
        output_file: Path to save the translated PPTX file
        source_language: Source language code
        target_language: Target language code
        quality_level: Required quality level (professional, standard, draft, economy)
        resume_file: Path to a recovery file to resume from (optional)
        api_key: API key (optional)
        use_cache: Whether to use the translation cache
        qa_enabled: Whether to enable quality assurance checks
        max_workers: Maximum number of parallel workers
        
    Returns:
        dict: Dictionary with translation statistics
    """
    start_time = time.time()
    
    # Extract text from the presentation
    logger.info(f"Extracting text from {input_file}...")
    extraction_result = extract_text(input_file)
    text_dict = extraction_result["text_dict"]
    slide_metadata = extraction_result["slide_metadata"]
    
    # Translate the text
    logger.info(f"Translating from {source_language} to {target_language} with quality level: {quality_level}...")
    translated_texts = translate_text(
        text_dict, 
        slide_metadata, 
        source_language, 
        target_language,
        quality_level=quality_level,
        resume_file=resume_file,
        api_key=api_key,
        use_cache=use_cache,
        qa_enabled=qa_enabled,
        max_workers=max_workers
    )
    
    # Update the presentation with translated text
    logger.info(f"Updating presentation with translations...")
    update_slides(input_file, output_file, translated_texts)
    
    end_time = time.time()
    duration = end_time - start_time
    
    logger.info(f"Translation completed in {duration:.2f} seconds")
    logger.info(f"Translated presentation saved to {output_file}")
    
    return {
        "input_file": input_file,
        "output_file": output_file,
        "source_language": source_language,
        "target_language": target_language,
        "quality_level": quality_level,
        "text_elements": len(text_dict),
        "duration_seconds": duration,
        "qa_enabled": qa_enabled,
        "parallel_processing": True,
        "max_workers": max_workers
    }

def clear_translation_cache():
    """
    Clear the translation cache.
    
    Returns:
        int: Number of cache entries removed
    """
    count = 0
    for filename in os.listdir(CACHE_DIR):
        file_path = os.path.join(CACHE_DIR, filename)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
                count += 1
        except Exception as e:
            logger.error(f"Error deleting cache file {file_path}: {e}")
    
    logger.info(f"Cleared {count} entries from translation cache")
    return count

def get_cache_stats():
    """
    Get statistics about the translation cache.
    
    Returns:
        dict: Cache statistics
    """
    total_size = 0
    entry_count = 0
    
    for filename in os.listdir(CACHE_DIR):
        file_path = os.path.join(CACHE_DIR, filename)
        try:
            if os.path.isfile(file_path):
                total_size += os.path.getsize(file_path)
                entry_count += 1
        except Exception as e:
            logger.error(f"Error accessing cache file {file_path}: {e}")
    
    return {
        "entry_count": entry_count,
        "total_size_bytes": total_size,
        "total_size_mb": total_size / (1024 * 1024)
    }
