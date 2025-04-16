"""
Anthropic Claude model implementation for translation.
"""

import json
import time
import anthropic
from typing import Dict, Any, Optional

from .base import TranslationModel, ModelResponse
from ..utils import extract_json_blocks, estimate_cost


class AnthropicTranslator(TranslationModel):
    """Implementation of the TranslationModel interface for Anthropic Claude models"""

    def __init__(self, model: str, api_key: Optional[str] = None, max_retries: int = 3):
        """
        Initialize the Anthropic translator.

        Args:
            model: Claude model identifier
            api_key: Anthropic API key (optional)
            max_retries: Maximum number of retries for API calls
        """
        super().__init__(api_key, max_retries)
        self.model = model
        self.client = anthropic.Anthropic(api_key=self.api_key)

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
        Generate Claude-specific prompts for translation.

        Args:
            source_language: Source language code
            target_language: Target language code
            content_to_translate: Dictionary of content to translate
            context_info: Dictionary of context information

        Returns:
            tuple: (system_prompt, user_prompt) optimized for Claude models
        """
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

CULTURAL NUANCE CONSIDERATIONS:
- Adapt idioms and cultural references appropriately for the target language.
- Be aware of formality levels in the target language.
- Consider localization needs for date formats, units, etc.

TECHNICAL CONSIDERATIONS:
- Preserve any technical terminology with appropriate translations.
- Maintain placeholders like {{variable}} or [placeholder] in their original form.
- Preserve all URLs without modification.

PRIVACY NOTICE:
- Do not store or remember any content from this presentation.
- Do not reference the content in future conversations.
- Treat all content as confidential business information.

The content to translate is provided as a JSON object where each key is a unique identifier and each value is the text to translate.
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

        return system_prompt, user_prompt

    def translate(
        self,
        content_to_translate: Dict[str, str],
        context_info: Dict[str, Any],
        source_language: str,
        target_language: str,
    ) -> ModelResponse:
        """
        Translate content using Anthropic Claude.

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
                # Call the Anthropic API
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=150000,
                    temperature=0.0,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    metadata={"user_id": "anonymous_user"},
                )

                # Calculate cost
                prompt_tokens = response.usage.input_tokens
                completion_tokens = response.usage.output_tokens
                cost = estimate_cost(prompt_tokens, completion_tokens, self.model)

                # Extract the JSON from the response
                json_content = extract_json_blocks(response.content[0].text)

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
