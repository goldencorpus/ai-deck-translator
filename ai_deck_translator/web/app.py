"""
Web interface for AI Deck Translator.

This module provides a web interface for translating Google Slides and PowerPoint
presentations using AI-powered translation services.

Usage:
    python -m ai_deck_translator.web.app
"""
import os
import uuid
import threading
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session
from werkzeug.utils import secure_filename
from ..core.extractor import extract_text as extract_text_gslides
from ..core.translator import translate_text
from ..core.updater import update_slides as update_slides_gslides
from ..pptx.extractor import extract_text as extract_text_pptx
from ..pptx.updater import update_slides as update_slides_pptx
from ..services.google_translate import translate_batch as google_translate_batch
from ..services.anthropic import translate_batch as anthropic_translate_batch
from ..utils.logging import get_logger, setup_logging
from ..utils.exceptions import ValidationError, TranslationError, NetworkError, RateLimitError

# Set up logging
logger = get_logger(__name__)

# Create Flask app
app = Flask(__name__, template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))

# Configure upload folder
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Configure allowed extensions
ALLOWED_EXTENSIONS = {"pptx"}

# Global state for translation progress
translation_state = {}

def allowed_file(filename):
    """
    Check if a file has an allowed extension.
    
    Args:
        filename (str): Name of the file to check
        
    Returns:
        bool: True if the file has an allowed extension, False otherwise
    """
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def update_progress(current, total):
    """
    Update the translation progress in the global state.
    
    Args:
        current (int): Current progress
        total (int): Total items to process
    """
    session_id = session.get("session_id")
    if session_id in translation_state:
        translation_state[session_id]["progress"] = current
        translation_state[session_id]["total"] = total
        translation_state[session_id]["percent"] = int(100 * current / total) if total > 0 else 0

def translate_presentation(input_file, output_file, target_language, service, api_key, translate_notes):
    """
    Translate a presentation in a background thread.
    
    Args:
        input_file (str): Path to the input presentation file
        output_file (str): Path to save the output presentation file
        target_language (str): Target language code
        service (str): Translation service to use
        api_key (str): API key for the translation service
        translate_notes (bool): Whether to translate slide notes
    """
    session_id = session.get("session_id")
    
    try:
        # Update state to indicate translation has started
        translation_state[session_id]["status"] = "running"
        
        # Determine if input is a Google Slides ID or a PPTX file
        is_google_slides = not os.path.exists(input_file) and len(input_file) == 44
        
        # Extract text from the presentation
        logger.info(f"Extracting text from {'Google Slides' if is_google_slides else 'PowerPoint'} presentation")
        
        if is_google_slides:
            # Extract text from Google Slides
            text_elements, slide_metadata = extract_text_gslides(input_file)
        else:
            # Extract text from PPTX
            text_elements, slide_metadata = extract_text_pptx(input_file)
        
        logger.info(f"Extracted {len(text_elements)} text elements from {len(slide_metadata)} slides")
        
        # Select translation function based on service
        if service == "google":
            translate_func = google_translate_batch
            logger.info("Using Google Translate service")
        elif service == "anthropic":
            if not api_key:
                raise ValidationError("API key is required for Anthropic service")
            
            # Create a wrapper function that includes the API key
            def anthropic_translate_with_key(texts, target_language):
                return anthropic_translate_batch(texts, target_language, api_key)
            
            translate_func = anthropic_translate_with_key
            logger.info("Using Anthropic service")
        
        # Translate text
        logger.info(f"Translating text to {target_language}")
        
        # If translate_notes is False, filter out notes from slide_metadata
        if not translate_notes:
            for metadata in slide_metadata:
                if "notes" in metadata:
                    metadata["notes"] = ""
        
        translated_elements = translate_text(
            text_elements=text_elements,
            slide_metadata=slide_metadata,
            target_language=target_language,
            translate_func=translate_func,
            progress_callback=update_progress
        )
        
        logger.info(f"Translated {len(translated_elements)} text elements")
        
        # Update the presentation with translated text
        logger.info(f"Updating presentation with translated text")
        
        if is_google_slides:
            # Update Google Slides
            success = update_slides_gslides(input_file, output_file, translated_elements)
        else:
            # Update PPTX
            success = update_slides_pptx(input_file, output_file, translated_elements)
        
        if success:
            logger.info(f"Successfully updated presentation: {output_file}")
            translation_state[session_id]["status"] = "completed"
            translation_state[session_id]["output_file"] = output_file
        else:
            logger.error("Failed to update presentation")
            translation_state[session_id]["status"] = "failed"
            translation_state[session_id]["error"] = "Failed to update presentation"
            
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        translation_state[session_id]["status"] = "failed"
        translation_state[session_id]["error"] = f"Validation error: {str(e)}"
    except TranslationError as e:
        logger.error(f"Translation error: {e}")
        translation_state[session_id]["status"] = "failed"
        translation_state[session_id]["error"] = f"Translation error: {str(e)}"
    except NetworkError as e:
        logger.error(f"Network error: {e}")
        translation_state[session_id]["status"] = "failed"
        translation_state[session_id]["error"] = f"Network error: {str(e)}"
    except RateLimitError as e:
        logger.error(f"Rate limit error: {e}")
        translation_state[session_id]["status"] = "failed"
        translation_state[session_id]["error"] = f"Rate limit error: {str(e)}"
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        translation_state[session_id]["status"] = "failed"
        translation_state[session_id]["error"] = f"Unexpected error: {str(e)}"

@app.route("/")
def index():
    """
    Render the index page.
    
    Returns:
        str: Rendered HTML template
    """
    # Generate a unique session ID if not already set
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
        translation_state[session["session_id"]] = {
            "status": "idle",
            "progress": 0,
            "total": 0,
            "percent": 0
        }
    
    return render_template("index.html")

@app.route("/translate", methods=["POST"])
def translate():
    """
    Handle translation form submission.
    
    Returns:
        Response: Redirect to the progress page
    """
    # Check if session ID is set
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    
    session_id = session["session_id"]
    
    # Initialize translation state
    translation_state[session_id] = {
        "status": "preparing",
        "progress": 0,
        "total": 0,
        "percent": 0
    }
    
    # Get form data
    target_language = request.form.get("target_language")
    service = request.form.get("service", "google")
    api_key = request.form.get("api_key", "")
    translate_notes = request.form.get("translate_notes") == "on"
    
    # Check if target language is provided
    if not target_language:
        flash("Target language is required", "error")
        return redirect(url_for("index"))
    
    # Check if API key is provided for Anthropic
    if service == "anthropic" and not api_key:
        flash("API key is required for Anthropic service", "error")
        return redirect(url_for("index"))
    
    # Handle Google Slides ID
    slides_id = request.form.get("slides_id")
    if slides_id:
        # Validate Google Slides ID
        if len(slides_id) != 44:
            flash("Invalid Google Slides ID", "error")
            return redirect(url_for("index"))
        
        # Generate output file name
        output_file = f"{slides_id}_{target_language}"
        
        # Start translation in a background thread
        thread = threading.Thread(
            target=translate_presentation,
            args=(slides_id, output_file, target_language, service, api_key, translate_notes)
        )
        thread.daemon = True
        thread.start()
        
        return redirect(url_for("progress"))
    
    # Handle file upload
    if "file" not in request.files:
        flash("No file part", "error")
        return redirect(url_for("index"))
    
    file = request.files["file"]
    
    if file.filename == "":
        flash("No selected file", "error")
        return redirect(url_for("index"))
    
    if file and allowed_file(file.filename):
        # Save the uploaded file
        filename = secure_filename(file.filename)
        input_file = os.path.join(app.config["UPLOAD_FOLDER"], f"{session_id}_{filename}")
        file.save(input_file)
        
        # Generate output file name
        output_name = f"{os.path.splitext(filename)[0]}_{target_language}.pptx"
        output_file = os.path.join(app.config["UPLOAD_FOLDER"], f"{session_id}_{output_name}")
        
        # Start translation in a background thread
        thread = threading.Thread(
            target=translate_presentation,
            args=(input_file, output_file, target_language, service, api_key, translate_notes)
        )
        thread.daemon = True
        thread.start()
        
        return redirect(url_for("progress"))
    
    flash("Invalid file type", "error")
    return redirect(url_for("index"))

@app.route("/progress")
def progress():
    """
    Render the progress page.
    
    Returns:
        str: Rendered HTML template
    """
    # Check if session ID is set
    if "session_id" not in session:
        return redirect(url_for("index"))
    
    session_id = session["session_id"]
    
    # Check if translation state exists
    if session_id not in translation_state:
        translation_state[session_id] = {
            "status": "idle",
            "progress": 0,
            "total": 0,
            "percent": 0
        }
    
    return render_template("progress.html", state=translation_state[session_id])

@app.route("/status")
def status():
    """
    Get the current translation status.
    
    Returns:
        dict: Current translation status
    """
    # Check if session ID is set
    if "session_id" not in session:
        return {"status": "idle", "progress": 0, "total": 0, "percent": 0}
    
    session_id = session["session_id"]
    
    # Check if translation state exists
    if session_id not in translation_state:
        return {"status": "idle", "progress": 0, "total": 0, "percent": 0}
    
    return translation_state[session_id]

@app.route("/download")
def download():
    """
    Download the translated presentation.
    
    Returns:
        Response: File download response
    """
    # Check if session ID is set
    if "session_id" not in session:
        return redirect(url_for("index"))
    
    session_id = session["session_id"]
    
    # Check if translation state exists and has an output file
    if session_id not in translation_state or "output_file" not in translation_state[session_id]:
        flash("No translated file available", "error")
        return redirect(url_for("index"))
    
    output_file = translation_state[session_id]["output_file"]
    
    # Check if the output file exists
    if not os.path.exists(output_file):
        flash("Translated file not found", "error")
        return redirect(url_for("index"))
    
    # Get the filename from the output file path
    filename = os.path.basename(output_file)
    if session_id in filename:
        filename = filename.replace(f"{session_id}_", "")
    
    # Send the file for download
    return send_file(output_file, as_attachment=True, download_name=filename)

def main():
    """
    Main entry point for the web interface.
    
    This function sets up logging and starts the Flask development server.
    """
    # Set up logging
    setup_logging("INFO")
    
    # Start the Flask development server
    app.run(debug=True, host="0.0.0.0", port=5000)

if __name__ == "__main__":
    main() 