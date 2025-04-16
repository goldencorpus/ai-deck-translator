"""
Command-line interface for AI Deck Translator.

This module provides a command-line interface for translating Google Slides and PowerPoint
presentations using AI-powered translation services.

Usage:
    python -m ai_deck_translator.cli.main [options]
"""

import argparse
import os
import sys
from ..core.extractor import extract_text as extract_text_gslides
from ..core.translator import translate_text
from ..core.updater import update_slides as update_slides_gslides
from ..pptx.extractor import extract_text as extract_text_pptx
from ..pptx.updater import update_slides as update_slides_pptx
from ..pptx.enhanced import (
    translate_presentation,
    QUALITY_PROFESSIONAL,
    QUALITY_STANDARD,
    QUALITY_DRAFT,
    QUALITY_ECONOMY,
)
from ..services.google_translate import translate_batch as google_translate_batch
from ..services.anthropic import translate_batch as anthropic_translate_batch
from ..utils.logging import get_logger, setup_logging
from ..utils.exceptions import (
    ValidationError,
    TranslationError,
    NetworkError,
    RateLimitError,
)

# Set up logging
logger = get_logger(__name__)


def parse_args():
    """
    Parse command-line arguments.

    Returns:
        argparse.Namespace: Parsed command-line arguments
    """
    parser = argparse.ArgumentParser(
        description="AI Deck Translator - Translate presentations with AI"
    )

    # Input/output options
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Input presentation file (PPTX) or Google Slides ID",
    )
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help="Output presentation file (PPTX) or Google Slides ID",
    )

    # Translation options
    parser.add_argument(
        "--target-language",
        "-t",
        required=True,
        help="Target language code (e.g., 'ja' for Japanese)",
    )
    parser.add_argument(
        "--source-language",
        "-s",
        default="en",
        help="Source language code (default: en)",
    )

    # Service options
    parser.add_argument(
        "--service",
        choices=["google", "anthropic", "enhanced"],
        default="google",
        help="Translation service to use (default: google)",
    )
    parser.add_argument("--api-key", help="API key for the translation service")

    # Recovery options
    parser.add_argument("--recovery-file", help="Path to save/load recovery data")

    # Logging options
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument("--log-file", help="Path to save log file")

    # Additional options
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Maximum number of elements per batch",
    )
    parser.add_argument(
        "--delay", type=float, default=0.5, help="Delay between batches in seconds"
    )
    parser.add_argument(
        "--translate-notes",
        action="store_true",
        help="Translate slide notes in addition to slide content",
    )

    # Enhanced translator options
    parser.add_argument(
        "--quality",
        choices=[
            QUALITY_PROFESSIONAL,
            QUALITY_STANDARD,
            QUALITY_DRAFT,
            QUALITY_ECONOMY,
        ],
        default=QUALITY_STANDARD,
        help="Translation quality level (for enhanced service)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable translation cache (for enhanced service)",
    )
    parser.add_argument(
        "--no-qa",
        action="store_true",
        help="Disable quality assurance (for enhanced service)",
    )
    parser.add_argument(
        "--workers", type=int, help="Number of parallel workers (for enhanced service)"
    )

    return parser.parse_args()


def main():
    """
    Main entry point for the CLI.

    This function parses command-line arguments, extracts text from the presentation,
    translates it, and updates the presentation with the translated text.

    Returns:
        int: Exit code (0 for success, non-zero for error)
    """
    # Parse command-line arguments
    args = parse_args()

    # Set up logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(log_level, args.log_file)

    try:
        # Determine if input is a Google Slides ID or a PPTX file
        is_google_slides = not os.path.exists(args.input) and len(args.input) == 44

        # If using enhanced translator, ensure we're working with PPTX files
        if args.service == "enhanced" and is_google_slides:
            logger.error(
                "Enhanced translation service only works with PPTX files, not Google Slides"
            )
            return 1

        # Use enhanced translator directly if selected
        if args.service == "enhanced" and not is_google_slides:
            logger.info("Using enhanced translator service for PPTX file")

            result = translate_presentation(
                args.input,
                args.output,
                source_language=args.source_language,
                target_language=args.target_language,
                quality_level=args.quality,
                resume_file=args.recovery_file,
                api_key=args.api_key,
                use_cache=not args.no_cache,
                qa_enabled=not args.no_qa,
                max_workers=args.workers,
            )

            if result["success"]:
                logger.info(f"Successfully translated presentation: {args.output}")
                logger.info(
                    f"Translated {result['translated_elements']} of {result['text_elements']} text elements"
                )
                logger.info(
                    f"Translation completed in {result['duration_seconds']:.2f} seconds"
                )
                return 0
            else:
                logger.error(
                    f"Failed to translate presentation: {result.get('error', 'Unknown error')}"
                )
                return 1

        # Extract text from the presentation
        logger.info(
            f"Extracting text from {'Google Slides' if is_google_slides else 'PowerPoint'} presentation"
        )

        if is_google_slides:
            # Extract text from Google Slides
            text_elements, slide_metadata = extract_text_gslides(args.input)
        else:
            # Extract text from PPTX
            text_elements, slide_metadata = extract_text_pptx(args.input)

        logger.info(
            f"Extracted {len(text_elements)} text elements from {len(slide_metadata)} slides"
        )

        # Select translation function based on service
        if args.service == "google":
            translate_func = google_translate_batch
            logger.info("Using Google Translate service")
        elif args.service == "anthropic":
            if not args.api_key:
                logger.error("API key is required for Anthropic service")
                return 1

            # Create a wrapper function that includes the API key
            def anthropic_translate_with_key(texts, target_language):
                return anthropic_translate_batch(texts, target_language, args.api_key)

            translate_func = anthropic_translate_with_key
            logger.info("Using Anthropic service")

        # Translate text
        logger.info(f"Translating text to {args.target_language}")

        translated_elements = translate_text(
            text_elements=text_elements,
            slide_metadata=slide_metadata,
            target_language=args.target_language,
            translate_func=translate_func,
            batch_size=args.batch_size,
            delay=args.delay,
            recovery_file=args.recovery_file,
        )

        logger.info(f"Translated {len(translated_elements)} text elements")

        # Update the presentation with translated text
        logger.info(f"Updating presentation with translated text")

        if is_google_slides:
            # Update Google Slides
            success = update_slides_gslides(
                args.input, args.output, translated_elements
            )
        else:
            # Update PPTX
            success = update_slides_pptx(args.input, args.output, translated_elements)

        if success:
            logger.info(f"Successfully updated presentation: {args.output}")
            return 0
        else:
            logger.error("Failed to update presentation")
            return 1

    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        return 1
    except TranslationError as e:
        logger.error(f"Translation error: {e}")
        return 1
    except NetworkError as e:
        logger.error(f"Network error: {e}")
        return 1
    except RateLimitError as e:
        logger.error(f"Rate limit error: {e}")
        return 1
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
