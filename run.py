#!/usr/bin/env python3
"""
AI Deck Translator - Main entry point

This script serves as the entry point for both CLI and web interfaces
of the AI Deck Translator application.
"""

import argparse
import sys
import os

from ai_deck_translator.web.app import create_app, run_web_app
from ai_deck_translator.core.translator import translate_presentation
from ai_deck_translator.utils.logging import logger
from ai_deck_translator.config import config


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="AI Deck Translator - Translate presentations between languages"
    )
    parser.add_argument(
        "--web", 
        action="store_true", 
        help="Launch web interface"
    )
    parser.add_argument(
        "--host", 
        type=str, 
        default=config["web"]["host"],
        help="Host for the web server (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=config["web"]["port"],
        help="Port for the web server (default: 5000)"
    )
    parser.add_argument(
        "--debug", 
        action="store_true", 
        help="Enable debug mode"
    )
    return parser.parse_args()


def cli_interface():
    """Run the command line interface."""
    try:
        # Get presentation ID
        presentation_id = input("Enter presentation ID: ")
        
        # Get source and target languages
        source_lang = input("Enter source language (e.g., en): ")
        target_lang = input("Enter target language (e.g., ja): ")
        
        # Start translation
        translate_presentation(presentation_id, source_lang, target_lang)
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error in CLI interface: {str(e)}")
        sys.exit(1)


def main():
    """Entry point for the application."""
    args = parse_args()
    
    try:
        if args.web:
            # Run web interface
            app = create_app()
            run_web_app(app, host=args.host, port=args.port, debug=args.debug)
        else:
            # Run CLI interface
            cli_interface()
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main() 