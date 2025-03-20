"""
Shared utilities for AI Deck Translator.

This module provides common utility functions shared between Google Slides and 
PowerPoint (PPTX) translation systems to ensure consistent behavior and reduce
code duplication.

Key functions:
- repair_json: Fix malformed JSON returned by translation APIs
- extract_json_blocks: Extract JSON blocks from API responses
- glossary_functions: Apply glossary terms to translations
- quality_checks: Common quality assurance checks
"""
import re
import json
import os
from typing import Dict, List, Any, Tuple, Optional

def repair_json(json_content: str) -> str:
    """
    Repair malformed JSON returned by translation APIs.
    
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

def extract_json_blocks(text: str) -> Dict[str, Any]:
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

def perform_quality_check(
    original_text: str, 
    translated_text: str, 
    source_language: str, 
    target_language: str
) -> Tuple[float, List[str]]:
    """
    Perform quality checks on a translation.
    
    Args:
        original_text: Original text
        translated_text: Translated text
        source_language: Source language code
        target_language: Target language code
        
    Returns:
        Tuple[float, List[str]]: Quality score (0-100) and list of issues
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
    if actual_ratio < expected_ratio * (1 - ratio_tolerance) or actual_ratio > expected_ratio * (1 + ratio_tolerance):
        issues.append(f"Length ratio issue: Expected around {expected_ratio:.1f}, got {actual_ratio:.1f}")
    
    # Check 2: Formatting preservation (bullet points, numbering, etc.)
    format_markers = ["•", "-", "*", "1.", "2.", "3.", "I.", "II.", "III.", "A.", "B.", "C."]
    
    for marker in format_markers:
        orig_count = original_text.count(marker)
        trans_count = translated_text.count(marker)
        
        if orig_count > 0 and trans_count != orig_count:
            issues.append(f"Format marker '{marker}' count mismatch: {orig_count} in original, {trans_count} in translation")
    
    # Check 3: Technical term preservation
    # This is a simplified approach; a more robust solution would use a terminology database
    import re
    
    # Find acronyms (all caps words)
    acronyms = re.findall(r'\b[A-Z]{2,}\b', original_text)
    
    # Find proper nouns (capitalized words not at sentence start)
    proper_nouns = re.findall(r'(?<=[.!?]\s|\s)[A-Z][a-zA-Z]*\b', " " + original_text)
    
    # Combine technical terms
    technical_terms = acronyms + proper_nouns
    
    # Check if these terms are preserved in the translation
    missing_terms = []
    for term in technical_terms:
        # Skip very short terms as they might be common words
        if len(term) <= 1:
            continue
            
        # For non-Latin target languages like Japanese, Chinese, etc.,
        # we can't directly check for the term
        if target_language in ['ja', 'zh', 'ko', 'th', 'ar']:
            continue
            
        if term.lower() not in translated_text.lower():
            missing_terms.append(term)
    
    if missing_terms:
        issues.append(f"Missing technical terms: {', '.join(missing_terms)}")
    
    # Check 4: Placeholder preservation (e.g., {0}, {name}, etc.)
    placeholders_original = re.findall(r'\{[^}]+\}', original_text)
    placeholders_translated = re.findall(r'\{[^}]+\}', translated_text)
    
    if len(placeholders_original) != len(placeholders_translated):
        issues.append(f"Placeholder count mismatch: {len(placeholders_original)} in original, {len(placeholders_translated)} in translation")
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

class GlossaryManager:
    """
    Manager for terminology glossaries to ensure consistent translations.
    
    This class provides methods to register glossaries, find terms in text,
    and apply glossary translations to ensure consistent terminology.
    """
    
    def __init__(self, glossary_dir: Optional[str] = None):
        """
        Initialize the glossary manager.
        
        Args:
            glossary_dir: Directory containing glossary files
        """
        self.glossaries = {}
        self.glossary_dir = glossary_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "glossaries"
        )
        
        # Create directory if it doesn't exist
        if not os.path.exists(self.glossary_dir):
            os.makedirs(self.glossary_dir)
            
        # Load all glossaries
        self._load_glossaries()
    
    def _load_glossaries(self):
        """Load all glossary files from the glossary directory."""
        if not os.path.exists(self.glossary_dir):
            return
            
        for filename in os.listdir(self.glossary_dir):
            if filename.endswith(".json"):
                try:
                    filepath = os.path.join(self.glossary_dir, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        glossary_data = json.load(f)
                        
                    # Extract language pair from filename
                    name_parts = filename.replace(".json", "").split("_")
                    if len(name_parts) >= 3:
                        source_lang = name_parts[1]
                        target_lang = name_parts[2]
                        
                        # Register glossary
                        self.glossaries[(source_lang, target_lang)] = glossary_data
                except Exception as e:
                    print(f"Error loading glossary {filename}: {e}")
    
    def find_terms(self, text: str, source_language: str, target_language: str) -> List[str]:
        """
        Find glossary terms in the source text.
        
        Args:
            text: Source text
            source_language: Source language code
            target_language: Target language code
            
        Returns:
            List[str]: List of terms found in the text
        """
        terms = []
        
        # Check if we have a glossary for this language pair
        glossary = self.glossaries.get((source_language, target_language), {})
        
        if not glossary:
            return terms
            
        # Find all terms in the text
        for term in glossary:
            if term.lower() in text.lower():
                terms.append(term)
                
        return terms
    
    def apply_glossary(self, original_text: str, source_language: str, 
                     target_language: str, translated_text: str) -> str:
        """
        Apply glossary translations to ensure consistent terminology.
        
        Args:
            original_text: Original source text
            source_language: Source language code
            target_language: Target language code
            translated_text: The translated text to update
            
        Returns:
            str: Updated translation with correct terminology
        """
        # Check if we have a glossary for this language pair
        glossary = self.glossaries.get((source_language, target_language), {})
        
        if not glossary:
            return translated_text
            
        # Find terms in the original text
        terms = self.find_terms(original_text, source_language, target_language)
        
        # Replace incorrect translations with glossary terms
        updated_text = translated_text
        
        for term in terms:
            if term in glossary:
                preferred_translation = glossary[term]
                
                # Use regex to replace the term with case insensitivity
                # but preserving the case of the replacement
                updated_text = re.sub(
                    fr'\b{re.escape(preferred_translation)}\b', 
                    preferred_translation, 
                    updated_text, 
                    flags=re.IGNORECASE
                )
                
        return updated_text
    
    def register_term(self, source_language: str, target_language: str,
                   source_term: str, target_term: str):
        """
        Register a new term in the glossary.
        
        Args:
            source_language: Source language code
            target_language: Target language code
            source_term: Term in source language
            target_term: Preferred translation in target language
        """
        # Create or get the glossary for this language pair
        if (source_language, target_language) not in self.glossaries:
            self.glossaries[(source_language, target_language)] = {}
            
        # Add the term
        self.glossaries[(source_language, target_language)][source_term] = target_term
        
        # Save the glossary
        self._save_glossary(source_language, target_language)
    
    def _save_glossary(self, source_language: str, target_language: str):
        """
        Save a glossary to disk.
        
        Args:
            source_language: Source language code
            target_language: Target language code
        """
        if (source_language, target_language) not in self.glossaries:
            return
            
        filename = f"glossary_{source_language}_{target_language}.json"
        filepath = os.path.join(self.glossary_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.glossaries[(source_language, target_language)], f, 
                    ensure_ascii=False, indent=2)

# Initialize a global glossary manager
glossary_manager = GlossaryManager()

def find_terms_in_text(text: str, source_language: str, target_language: str) -> List[str]:
    """
    Find glossary terms in the source text.
    
    Args:
        text: Source text
        source_language: Source language code
        target_language: Target language code
        
    Returns:
        List[str]: List of terms found in the text
    """
    return glossary_manager.find_terms(text, source_language, target_language)

def apply_glossary_to_text(original_text: str, source_language: str, 
                        target_language: str, translated_text: str) -> str:
    """
    Apply glossary translations to ensure consistent terminology.
    
    Args:
        original_text: Original source text
        source_language: Source language code
        target_language: Target language code
        translated_text: The translated text to update
        
    Returns:
        str: Updated translation with correct terminology
    """
    return glossary_manager.apply_glossary(
        original_text, source_language, target_language, translated_text
    ) 