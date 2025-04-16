"""
OpenAI GPT model implementation for translation.
"""

import json
import time

try:
    import openai
except ImportError:
    openai = None
from typing import Dict, Any, Optional

from .base import TranslationModel, ModelResponse
from ..utils import extract_json_blocks, estimate_cost


class OpenAITranslator(TranslationModel):
    """Implementation of the TranslationModel interface for OpenAI GPT models"""

    def __init__(self, model: str, api_key: Optional[str] = None, max_retries: int = 3):
        """
        Initialize the OpenAI translator.

        Args:
            model: GPT model identifier
            api_key: OpenAI API key (optional)
            max_retries: Maximum number of retries for API calls
        """
        if openai is None:
            raise ImportError(
                "The 'openai' package is required to use OpenAITranslator. "
                "Install it with 'pip install openai'."
            )
        super().__init__(api_key, max_retries)
        self.model = model
        self.client = openai.OpenAI(api_key=self.api_key)

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
        Generate GPT-specific prompts for translation.

        Args:
            source_language: Source language code
            target_language: Target language code
            content_to_translate: Dictionary of content to translate
            context_info: Dictionary of context information

        Returns:
            tuple: (system_prompt, user_prompt) optimized for GPT models
        """
        system_prompt = f"""You are translating PowerPoint presentation content from {source_language} to {target_language}. 
Follow these guidelines precisely:

- Translate all text accurately while maintaining the original meaning and tone.
- Preserve formatting elements like bullet points, numbering, and paragraph breaks.
- Maintain any technical terminology appropriately.
- For tables, preserve the tabular structure in your translation.
- Respect the context of each text element (slide title, body text, etc.).
- Do not add or remove content; translate only what is provided.
- Return your response as a JSON object with the same structure as the input.

Privacy: Do not store or remember any content from this presentation. Do not reference the content in future conversations. Treat all content as confidential business information.

Return ONLY valid JSON with the exact same structure as the input, with no extra text.
"""

        # Add language-specific instructions if needed
        if target_language == "ja" or source_language == "ja":
            system_prompt += """
When working with Japanese content:
- Pay attention to appropriate formality levels
- Preserve technical terms in their original form when appropriate
- Ensure proper grammar and particle usage
- Translate idioms and cultural references appropriately
"""

        user_prompt = f"""Translate this presentation content from {source_language} to {target_language}.

Content (JSON):
```json
{json.dumps(content_to_translate, ensure_ascii=False, indent=2)}
```

Context:
```json
{json.dumps(context_info, ensure_ascii=False, indent=2)}
```

Return ONLY the JSON with translations, preserving all keys exactly.
"""

        return system_prompt, user_prompt

    def translate(
        self,
        content_to_translate: Dict[str, str],
        context_info: Dict[str, Any],
        source_language: str,
        target_language: str,
    ) -> ModelResponse:
        """
        Translate content using OpenAI GPT.

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

        # Initialize variables for retry logic
        retry_count = 0
        translated_batch = None

        # Try to translate with retries
        while retry_count <= self.max_retries:
            try:
                # Call the OpenAI API
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"},
                )

                # Track usage
                prompt_tokens = response.usage.prompt_tokens
                completion_tokens = response.usage.completion_tokens
                cost = estimate_cost(prompt_tokens, completion_tokens, self.model)

                # Extract the JSON from the response
                json_content = response.choices[0].message.content

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
