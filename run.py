#!/usr/bin/env python3
"""
Main entry point for the Google Slides Translator application.
Supports both command-line and web interfaces.
"""
import argparse
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

def main():
    """Main entry point function for the application"""
    parser = argparse.ArgumentParser(description="Google Slides Translator")
    parser.add_argument("--web", action="store_true", help="Launch the web UI")
    parser.add_argument("--port", type=int, default=5000, help="Port for web UI (default: 5000)")
    parser.add_argument("--host", default="127.0.0.1", help="Host for web UI (default: 127.0.0.1)")
    parser.add_argument("--presentation-id", help="Google Slides presentation ID")
    parser.add_argument("--source-lang", default="en", help="Source language code (default: en)")
    parser.add_argument("--target-lang", default="ja", help="Target language code (default: ja)")
    parser.add_argument("--api-key", help="Anthropic API key (optional, can use CLAUDE_API_KEY env var)")
    parser.add_argument("--resume-file", help="Recovery file to resume from (optional)")
    
    args = parser.parse_args()
    
    if args.web:
        # Import web interface module
        from gslides_translator.web.app import create_app
        
        app = create_app()
        print(f"Starting Web UI on http://{args.host}:{args.port}")
        print("Press Ctrl+C to stop")
        app.run(host=args.host, port=args.port, debug=False)
    else:
        # Import CLI module
        from gslides_translator.core.translator import translate_slides
        
        # If presentation ID is not provided, prompt for it
        presentation_id = args.presentation_id
        if not presentation_id:
            presentation_id = input("Enter Google Slides Presentation ID: ")
        
        # If API key is provided, set it as environment variable
        if args.api_key:
            os.environ["CLAUDE_API_KEY"] = args.api_key
        
        # Run the translation process
        translate_slides(
            presentation_id=presentation_id,
            source_language=args.source_lang,
            target_language=args.target_lang,
            resume_file=args.resume_file
        )

if __name__ == "__main__":
    main() 