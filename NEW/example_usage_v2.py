"""
Example usage script for the enhanced translator V2 implementation.
This script demonstrates how to use the enhanced translator with quality assurance and parallel processing.
"""

import os
import sys
import argparse
from datetime import datetime

# Add the parent directory to the path to import the enhanced_translator module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the enhanced translator module
import enhanced_translator_v2 as et


def main():
    """Main function to demonstrate the enhanced translator V2 usage"""
    parser = argparse.ArgumentParser(
        description="Translate a PowerPoint presentation with enhanced translator V2"
    )
    parser.add_argument("input_file", help="Path to the input PPTX file")
    parser.add_argument("output_file", help="Path to save the translated PPTX file")
    parser.add_argument("source_language", help="Source language code (e.g., en, ja)")
    parser.add_argument("target_language", help="Target language code (e.g., en, ja)")
    parser.add_argument(
        "--quality",
        choices=["professional", "standard", "draft", "economy"],
        default="professional",
        help="Translation quality level",
    )
    parser.add_argument(
        "--no-cache", action="store_true", help="Disable translation caching"
    )
    parser.add_argument(
        "--no-qa", action="store_true", help="Disable quality assurance"
    )
    parser.add_argument(
        "--workers", type=int, default=4, help="Number of parallel workers"
    )
    parser.add_argument("--resume", help="Path to a recovery file to resume from")
    parser.add_argument("--api-key", help="API key (optional)")
    parser.add_argument(
        "--cache-stats", action="store_true", help="Show cache statistics"
    )
    parser.add_argument(
        "--clear-cache", action="store_true", help="Clear the translation cache"
    )

    args = parser.parse_args()

    # Show cache statistics if requested
    if args.cache_stats:
        stats = et.get_cache_stats()
        print(f"Cache statistics:")
        print(f"  Entries: {stats['entry_count']}")
        print(
            f"  Total size: {stats['total_size_bytes']} bytes ({stats['total_size_mb']:.2f} MB)"
        )

    # Clear cache if requested
    if args.clear_cache:
        count = et.clear_translation_cache()
        print(f"Cleared {count} entries from translation cache")

    # Map quality level string to constant
    quality_map = {
        "professional": et.QUALITY_PROFESSIONAL,
        "standard": et.QUALITY_STANDARD,
        "draft": et.QUALITY_DRAFT,
        "economy": et.QUALITY_ECONOMY,
    }
    quality_level = quality_map[args.quality]

    # Translate the presentation
    print(f"Starting translation with quality level: {args.quality}")
    print(f"  Source language: {args.source_language}")
    print(f"  Target language: {args.target_language}")
    print(f"  Input file: {args.input_file}")
    print(f"  Output file: {args.output_file}")
    print(f"  Caching: {'Disabled' if args.no_cache else 'Enabled'}")
    print(f"  Quality Assurance: {'Disabled' if args.no_qa else 'Enabled'}")
    print(f"  Parallel Workers: {args.workers}")

    start_time = datetime.now()

    result = et.translate_presentation(
        args.input_file,
        args.output_file,
        args.source_language,
        args.target_language,
        quality_level=quality_level,
        resume_file=args.resume,
        api_key=args.api_key,
        use_cache=not args.no_cache,
        qa_enabled=not args.no_qa,
        max_workers=args.workers,
    )

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print(f"\nTranslation completed in {duration:.2f} seconds")
    print(f"Translated {result['text_elements']} text elements")
    print(f"Output saved to: {result['output_file']}")


if __name__ == "__main__":
    main()
