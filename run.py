#!/usr/bin/env python3
"""
Main entry point for the AI Deck Translator application.
Supports both command-line and web interfaces for Google Slides and PowerPoint presentations.
"""
import argparse
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

def main():
    """Main entry point function for the application"""
    parser = argparse.ArgumentParser(description="AI Deck Translator")
    parser.add_argument("--web", action="store_true", help="Launch the web UI")
    parser.add_argument("--port", type=int, default=5000, help="Port for web UI (default: 5000)")
    parser.add_argument("--host", default="127.0.0.1", help="Host for web UI (default: 127.0.0.1)")
    
    # Common arguments for both Google Slides and PPTX
    parser.add_argument("--source-lang", default="en", help="Source language code (default: en)")
    parser.add_argument("--target-lang", default="ja", help="Target language code (default: ja)")
    parser.add_argument("--api-key", help="Anthropic API key (optional, can use CLAUDE_API_KEY env var)")
    parser.add_argument("--resume-file", help="Recovery file to resume from (optional)")
    
    # Google Slides specific arguments
    parser.add_argument("--presentation-id", help="Google Slides presentation ID")
    
    # PPTX specific arguments
    parser.add_argument("--input-file", help="Input PowerPoint file (.pptx)")
    parser.add_argument("--output-file", help="Output PowerPoint file (.pptx)")
    
    args = parser.parse_args()
    
    # If API key is provided, set it as environment variable
    if args.api_key:
        os.environ["CLAUDE_API_KEY"] = args.api_key
    
    if args.web:
        # Import web interface module
        from ai_deck_translator.web.app import create_app
        
        app = create_app()
        print(f"Starting Web UI on http://{args.host}:{args.port}")
        print("Press Ctrl+C to stop")
        app.run(host=args.host, port=args.port, debug=False)
    else:
        # Determine if we're translating Google Slides or PPTX
        if args.presentation_id:
            # Google Slides translation
            from ai_deck_translator.core.translator import translate_slides
            
            print(f"Translating Google Slides presentation {args.presentation_id} from {args.source_lang} to {args.target_lang}")
            
            # Run the translation process
            translate_slides(
                presentation_id=args.presentation_id,
                source_language=args.source_lang,
                target_language=args.target_lang,
                resume_file=args.resume_file
            )
        elif args.input_file:
            # PPTX translation
            from ai_deck_translator.pptx.translator import translate_pptx
            
            # If output file is not provided, generate one
            output_file = args.output_file
            if not output_file:
                base_name = os.path.splitext(args.input_file)[0]
                output_file = f"{base_name}_{args.target_lang}.pptx"
            
            print(f"Translating PowerPoint file {args.input_file} from {args.source_lang} to {args.target_lang}")
            print(f"Output will be saved to {output_file}")
            
            # Run the translation process
            translate_pptx(
                input_file=args.input_file,
                output_file=output_file,
                source_language=args.source_lang,
                target_language=args.target_lang,
                resume_file=args.resume_file
            )
        else:
            # Interactive mode - ask what to translate
            print("AI Deck Translator")
            print("=================")
            print("1. Translate Google Slides presentation")
            print("2. Translate PowerPoint (.pptx) file")
            choice = input("Enter your choice (1 or 2): ")
            
            if choice == "1":
                # Google Slides translation
                from ai_deck_translator.core.translator import translate_slides
                
                presentation_id = input("Enter Google Slides Presentation ID: ")
                
                translate_slides(
                    presentation_id=presentation_id,
                    source_language=args.source_lang,
                    target_language=args.target_lang,
                    resume_file=args.resume_file
                )
            elif choice == "2":
                # PPTX translation
                from ai_deck_translator.pptx.translator import translate_pptx
                
                input_file = input("Enter path to PowerPoint file (.pptx): ")
                
                # Generate output file name
                base_name = os.path.splitext(input_file)[0]
                output_file = f"{base_name}_{args.target_lang}.pptx"
                
                translate_pptx(
                    input_file=input_file,
                    output_file=output_file,
                    source_language=args.source_lang,
                    target_language=args.target_lang,
                    resume_file=args.resume_file
                )
            else:
                print("Invalid choice. Exiting.")
                sys.exit(1)

if __name__ == "__main__":
    main() 