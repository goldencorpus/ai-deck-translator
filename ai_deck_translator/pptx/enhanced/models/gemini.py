"""
Google Gemini model implementation for translation.
"""

import json
import time
from typing import Any, Dict, Optional

import google.generativeai as genai

from ..utils import estimate_cost, extract_json_blocks
from .base import ModelResponse, TranslationModel


class GeminiTranslator(TranslationModel):
    """Implementation of the TranslationModel interface for Google Gemini models"""

    def __init__(self, model: str, api_key: Optional[str] = None, max_retries: int = 3):
        """
        Initialize the Gemini translator.

        Args:
            model: Gemini model identifier
            api_key: Google AI API key (optional)
            max_retries: Maximum number of retries for API calls
        """
        super().__init__(api_key, max_retries)
        self.model = model
        genai.configure(api_key=self.api_key)

    def get_model_name(self) -> str:
        """Get the name of this model"""
        return self.model

    def generate_prompts(
        self,
        source_language: str,
        target_language: str,
        content_to_translate: Dict[str, str],
        context_info: Dict[str, Any],
    ) -> tuple:
        """
        Generate Gemini-specific prompts for translation.

        Args:
            source_language: Source language code
            target_language: Target language code
            content_to_translate: Dictionary of content to translate
            context_info: Dictionary of context information

        Returns:
            tuple: (system_prompt, user_prompt) optimized for Gemini models
        """
        system_prompt = f"""Translation task: {source_language} to {target_language}. 
PowerPoint presentation content.

Guidelines:
* Translate all text accurately while maintaining the original meaning and tone.
* Preserve formatting elements like bullet points, numbering, and paragraph breaks.
* Maintain any technical terminology appropriately.
* For tables, preserve the tabular structure in your translation.
* Respect the context of each text element (slide title, body text, etc.).
* Do not add or remove content; translate only what is provided.
* Return your response as a JSON object with the same structure as the input.

Privacy requirements: Do not store or remember any content from this presentation. Do not reference the content in future conversations. Treat all content as confidential business information.

FORMAT: Return ONLY JSON with identical structure. No explanations.
"""

        user_prompt = f"""TRANSLATE: {source_language} → {target_language}

CONTENT:
{json.dumps(content_to_translate, ensure_ascii=False, indent=2)}

CONTEXT:
{json.dumps(context_info, ensure_ascii=False, indent=2)}

RESPONSE FORMAT: JSON only, identical structure to input. No wrapper text.
"""

        # For Gemini, we combine the prompts since it has a different interface
        return system_prompt, user_prompt

    def translate(
        self,
        content_to_translate: Dict[str, str],
        context_info: Dict[str, Any],
        source_language: str,
        target_language: str,
    ) -> ModelResponse:
        """
        Translate content using Google Gemini.

        Args:
            content_to_translate: Dictionary of content to translate
            context_info: Dictionary of context information
            source_language: Source language code
            target_language: Target language code

        Returns:
            ModelResponse: Standardized response with translation results
        """
        system_prompt, user_prompt = self.generate_prompts(
            source_language, target_language, content_to_translate, context_info
        )

        # Combine prompts for Gemini
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"

        # Initialize variables for retry logic
        retry_count = 0
        translated_batch = None

        # Try to translate with retries
        while retry_count <= self.max_retries:
            try:
                # Create a client for the specified model
                model = genai.GenerativeModel(self.model)

                # Call the Gemini API
                response = model.generate_content(combined_prompt)

                # Estimate token usage (Gemini doesn't provide token counts)
                # Rough estimate: 4 characters per token
                prompt_tokens = len(combined_prompt) // 4
                completion_tokens = len(response.text) // 4

                # Track usage
                cost = estimate_cost(prompt_tokens, completion_tokens, self.model)

                # Extract the JSON from the response
                json_content = extract_json_blocks(response.text)

                if json_content:
                    try:
                        translated_batch = json.loads(json_content)
                        break  # Success, exit the retry loop
                    except json.JSONDecodeError as e:
                        retry_count += 1
                else:
                    retry_count += 1

            except Exception as e:
                retry_count += 1
                time.sleep(2)  # Wait before retrying

        # If we couldn't translate after all retries, return an empty dict
        if translated_batch is None:
            translated_batch = {}

        return ModelResponse(
            translated_content=translated_batch,
            prompt_tokens=prompt_tokens if "prompt_tokens" in locals() else 0,
            completion_tokens=(
                completion_tokens if "completion_tokens" in locals() else 0
            ),
            model=self.model,
            cost=cost if "cost" in locals() else 0.0,
            raw_response=response if "response" in locals() else None,
        )
