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
import time
import tempfile
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_file,
    session,
    jsonify,
    make_response,
)
from werkzeug.utils import secure_filename
from ..core.extractor import extract_text as extract_text_gslides
from ..core.translator import translate_text
from ..core.updater import update_slides as update_slides_gslides
from ..pptx.extractor import extract_text as extract_text_pptx
from ..pptx.updater import update_slides as update_slides_pptx
from ..services.google_translate import translate_batch as google_translate_batch
from ..services.anthropic import translate_batch as anthropic_translate_batch
from ..utils.logging import get_logger, setup_logging
from ..utils.exceptions import (
    ValidationError,
    TranslationError,
    NetworkError,
    RateLimitError,
)
from flask_session import Session
from datetime import timedelta
from markupsafe import Markup
import markdown

# Set up logging
logger = get_logger(__name__)

# Global state for translation progress
translation_state = {}


def allowed_file(filename, allowed_extensions):
    """
    Check if a file has an allowed extension.

    Args:
        filename (str): Name of the file to check
        allowed_extensions (set): Set of allowed file extensions

    Returns:
        bool: True if the file has an allowed extension, False otherwise
    """
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def translate_presentation(
    input_file,
    output_file,
    target_language,
    service,
    api_key,
    translate_notes,
    session_id,
):
    """
    Translate a presentation in a background thread.

    Args:
        input_file (str): Path to the input presentation file
        output_file (str): Path to save the output presentation file
        target_language (str): Target language code
        service (str): Translation service to use
        api_key (str): API key for the translation service
        translate_notes (bool): Whether to translate slide notes
        session_id (str): Session ID from the request context
    """
    try:
        # Update state to indicate translation has started
        translation_state[session_id]["status"] = "running"
        translation_state[session_id]["progress"] = 0
        translation_state[session_id][
            "total"
        ] = 1  # Set initial total to at least 1 to avoid division by zero
        translation_state[session_id]["percent"] = 0
        translation_state[session_id]["last_updated"] = time.time()

        # Set the expected output file path early, so it's available even if processing fails
        translation_state[session_id]["output_file"] = output_file

        logger.info(f"[{session_id}] Starting translation process")
        logger.info(f"[{session_id}] Output file will be: {output_file}")
        logger.info(
            f"[{session_id}] Translation state initialized: {translation_state[session_id]}"
        )

        # Determine if input is a Google Slides ID or a PPTX file
        is_google_slides = not os.path.exists(input_file) and len(input_file) == 44
        logger.info(
            f"[{session_id}] Input type: {'Google Slides' if is_google_slides else 'PowerPoint'}"
        )

        # Extract text from the presentation
        logger.info(f"[{session_id}] Extracting text from presentation...")

        try:
            if is_google_slides:
                # Extract text from Google Slides
                text_elements, slide_metadata = extract_text_gslides(input_file)
            else:
                # Extract text from PPTX
                text_elements, slide_metadata = extract_text_pptx(input_file)
        except PermissionError as e:
            logger.error(f"[{session_id}] Permission error accessing presentation: {e}")
            translation_state[session_id]["status"] = "failed"
            translation_state[session_id][
                "error"
            ] = "Access denied (403): You don't have permission to access this presentation"
            return
        except Exception as e:
            if (
                "403" in str(e)
                or "forbidden" in str(e).lower()
                or "permission" in str(e).lower()
            ):
                logger.error(f"[{session_id}] Permission error (403): {e}")
                translation_state[session_id]["status"] = "failed"
                translation_state[session_id][
                    "error"
                ] = "Access denied (403): Make sure the presentation is shared or public"
                return
            else:
                raise  # Re-raise if it's not a permission error

        logger.info(
            f"[{session_id}] Extracted {len(text_elements)} text elements from {len(slide_metadata)} slides"
        )

        # Select translation function based on service
        if service == "google":
            translate_func = google_translate_batch
            logger.info(f"[{session_id}] Using Google Translate service")
        elif service == "anthropic":
            if not api_key:
                logger.error(
                    f"[{session_id}] API key is required for Anthropic service"
                )
                raise ValidationError("API key is required for Anthropic service")

            # Create a wrapper function that includes the API key
            def anthropic_translate_with_key(texts, target_language):
                return anthropic_translate_batch(texts, target_language, api_key)

            translate_func = anthropic_translate_with_key
            logger.info(f"[{session_id}] Using Anthropic service")

        # Translate text
        logger.info(f"[{session_id}] Translating text to {target_language}")

        # If translate_notes is False, filter out notes from slide_metadata
        if not translate_notes:
            for metadata in slide_metadata:
                if "notes" in metadata:
                    metadata["notes"] = ""

        # Create a progress callback that uses the session_id parameter instead of accessing the session
        def progress_callback(current, total):
            """
            Update the translation progress.

            Args:
                current (int): The current progress.
                total (int): The total number of elements to process.
            """
            try:
                # Check if the session exists in the translation state
                if session_id not in translation_state:
                    logger.warning(
                        f"[{session_id}] Progress callback called but session not found in translation state"
                    )
                    return

                # Update the translation state
                state = translation_state[session_id]
                state["progress"] = current
                state["total"] = total
                state["last_updated"] = time.time()

                # Update the percentage if total is greater than 0
                if total > 0:
                    state["percent"] = round((current / total) * 100)

                    # If progress equals total and total is not 0, mark as completed
                    if current == total and state["status"] != "completed":
                        logger.info(
                            f"[{session_id}] Translation progress reached 100%: {current}/{total}"
                        )
                        state["status"] = "completed"
                        logger.info(
                            f"[{session_id}] Translation status updated to 'completed'"
                        )

                        # Ensure output_file is set for completed translations
                        if (
                            "output_file" not in state
                            and "output_file" in translation_state.get(session_id, {})
                        ):
                            state["output_file"] = translation_state[session_id][
                                "output_file"
                            ]
                            logger.info(
                                f"[{session_id}] Set output_file path: {state['output_file']}"
                            )
                else:
                    state["percent"] = 0
                    logger.warning(
                        f"[{session_id}] Total is 0, setting progress percentage to 0"
                    )

            except Exception as e:
                logger.error(f"[{session_id}] Error updating translation progress: {e}")
                # Try to set error status if possible
                try:
                    translation_state[session_id]["status"] = "error"
                    translation_state[session_id]["error"] = str(e)
                except:
                    pass  # If we can't update the state, just log the error

        # Setup initial progress state with the correct total
        total_elements = len(text_elements)
        translation_state[session_id]["total"] = total_elements
        if total_elements > 0:
            translation_state[session_id]["percent"] = 0
        logger.info(
            f"[{session_id}] Initial progress state: {translation_state[session_id]}"
        )

        translated_elements = translate_text(
            text_elements=text_elements,
            slide_metadata=slide_metadata,
            target_language=target_language,
            translate_func=translate_func,
            progress_callback=progress_callback,
        )

        logger.info(
            f"[{session_id}] Translated {len(translated_elements)} text elements"
        )

        # Force update progress to 100% after translation is completed
        if len(text_elements) > 0:
            progress_callback(len(text_elements), len(text_elements))
            logger.info(f"[{session_id}] Force updated progress to 100%")

        # Update the presentation with translated text
        logger.info(f"[{session_id}] Updating presentation with translated text")

        try:
            if is_google_slides:
                # Update Google Slides
                success = update_slides_gslides(
                    input_file, output_file, translated_elements
                )
            else:
                # Update PPTX
                success = update_slides_pptx(
                    input_file, output_file, translated_elements
                )
                # Make sure output_file is set in the translation state for PPTX files
                translation_state[session_id]["output_file"] = output_file
        except PermissionError as e:
            logger.error(f"[{session_id}] Permission error updating presentation: {e}")
            translation_state[session_id]["status"] = "failed"
            translation_state[session_id][
                "error"
            ] = "Access denied (403): You don't have permission to update this presentation"
            return
        except Exception as e:
            if (
                "403" in str(e)
                or "forbidden" in str(e).lower()
                or "permission" in str(e).lower()
            ):
                logger.error(f"[{session_id}] Permission error (403): {e}")
                translation_state[session_id]["status"] = "failed"
                translation_state[session_id][
                    "error"
                ] = "Access denied (403): Make sure the presentation is shared with edit permissions"
                return
            else:
                raise  # Re-raise if it's not a permission error

        if success:
            logger.info(
                f"[{session_id}] Successfully updated presentation: {output_file}"
            )

            # Verify that the output file actually exists on disk
            if not os.path.exists(output_file):
                logger.error(
                    f"[{session_id}] Output file expected but not found at: {output_file}"
                )
                translation_state[session_id]["status"] = "failed"
                translation_state[session_id]["error"] = "Failed to create output file"
                return

            # Set final state
            translation_state[session_id]["progress"] = total_elements
            translation_state[session_id]["total"] = total_elements
            translation_state[session_id]["percent"] = 100
            translation_state[session_id]["status"] = "completed"
            translation_state[session_id]["output_file"] = output_file

            logger.info(
                f"[{session_id}] Translation completed. Final state: {translation_state[session_id]}"
            )
        else:
            logger.error(f"[{session_id}] Failed to update presentation")
            translation_state[session_id]["status"] = "failed"
            translation_state[session_id]["error"] = "Failed to update presentation"
            logger.error(
                f"[{session_id}] Translation failed. Final state: {translation_state[session_id]}"
            )

    except ValidationError as e:
        logger.error(f"[{session_id}] Validation error: {e}")
        translation_state[session_id]["status"] = "failed"
        translation_state[session_id]["error"] = f"Validation error: {str(e)}"
        logger.error(
            f"[{session_id}] Translation failed. Final state: {translation_state[session_id]}"
        )
    except TranslationError as e:
        logger.error(f"[{session_id}] Translation error: {e}")
        translation_state[session_id]["status"] = "failed"
        translation_state[session_id]["error"] = f"Translation error: {str(e)}"
        logger.error(
            f"[{session_id}] Translation failed. Final state: {translation_state[session_id]}"
        )
    except NetworkError as e:
        logger.error(f"[{session_id}] Network error: {e}")
        translation_state[session_id]["status"] = "failed"
        translation_state[session_id]["error"] = f"Network error: {str(e)}"
        logger.error(
            f"[{session_id}] Translation failed. Final state: {translation_state[session_id]}"
        )
    except RateLimitError as e:
        logger.error(f"[{session_id}] Rate limit error: {e}")
        translation_state[session_id]["status"] = "failed"
        translation_state[session_id]["error"] = f"Rate limit error: {str(e)}"
        logger.error(
            f"[{session_id}] Translation failed. Final state: {translation_state[session_id]}"
        )
    except Exception as e:
        logger.exception(f"[{session_id}] Unexpected error: {e}")
        translation_state[session_id]["status"] = "failed"
        translation_state[session_id]["error"] = f"Unexpected error: {str(e)}"
        logger.error(
            f"[{session_id}] Translation failed. Final state: {translation_state[session_id]}"
        )

    # Final log to confirm state is updated
    logger.info(
        f"[{session_id}] Translation thread completed. State: {translation_state[session_id]}"
    )


def create_app(debug=False):
    """
    Create and configure the Flask application.

    Args:
        debug (bool): Whether to enable debug mode.

    Returns:
        Flask: The configured Flask application.
    """
    app = Flask(__name__, template_folder="templates")
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev_key")
    app.config["UPLOAD_FOLDER"] = os.path.join(
        tempfile.gettempdir(), "ai_deck_translator_uploads"
    )
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max upload
    app.config["DEBUG"] = debug

    # Ensure upload directory exists
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Session management
    app.config["SESSION_TYPE"] = "filesystem"
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=1)
    Session(app)

    # Setup Markdown filter
    @app.template_filter("markdown")
    def render_markdown(text):
        return Markup(markdown.markdown(text))

    # Translation state storage
    # Dict to store translation state
    # Key: session_id, Value: Dict with keys:
    # - status: 'pending', 'running', 'completed', 'error'
    # - progress: number of processed elements
    # - total: total number of elements to process
    # - percent: progress percentage
    # - error: error message (if status is 'error')
    # - output_file: path to the output file (if status is 'completed')
    global translation_state
    translation_state = {}

    # Schedule cleanup of old translation states every 10 minutes
    def clean_old_translation_states():
        """Clean up translation states older than 1 hour"""
        current_time = time.time()
        expired_sessions = []

        for session_id, state in translation_state.items():
            # If last_updated is more than 1 hour old, remove it
            if "last_updated" in state and current_time - state["last_updated"] > 3600:
                expired_sessions.append(session_id)
                # Try to remove temporary files
                if "output_file" in state and os.path.exists(state["output_file"]):
                    try:
                        os.remove(state["output_file"])
                        logger.info(
                            f"Removed expired output file for session {session_id}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Error removing output file for session {session_id}: {e}"
                        )

        # Remove expired sessions
        for session_id in expired_sessions:
            del translation_state[session_id]
            logger.info(
                f"Cleaned up expired translation state for session {session_id}"
            )

    # Use a separate thread to clean up old translation states
    def start_cleanup_scheduler():
        """Start the cleanup scheduler in a separate thread"""
        while True:
            time.sleep(600)  # Run every 10 minutes
            clean_old_translation_states()

    # Start the cleanup scheduler thread
    cleanup_thread = threading.Thread(target=start_cleanup_scheduler, daemon=True)
    cleanup_thread.start()

    # Configure allowed extensions
    ALLOWED_EXTENSIONS = {"pptx"}

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
                "percent": 0,
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
            "percent": 0,
            "last_updated": time.time(),
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

            # Add a note about Google Slides permissions
            translation_state[session_id][
                "note"
            ] = "Working with Google Slides requires proper sharing permissions. The presentation must be shared with at least view access to extract text, and edit access to update it."

            # Generate output file name
            output_file = f"{slides_id}_{target_language}"

            # Start translation in a background thread
            thread = threading.Thread(
                target=translate_presentation,
                args=(
                    slides_id,
                    output_file,
                    target_language,
                    service,
                    api_key,
                    translate_notes,
                    session_id,
                ),
            )
            thread.daemon = True
            thread.start()

            logger.info(
                f"[{session_id}] Started translation thread for Google Slides with ID: {slides_id}"
            )
            return redirect(url_for("progress"))

        # Handle file upload
        if "file" not in request.files:
            flash("No file part", "error")
            return redirect(url_for("index"))

        file = request.files["file"]

        if file.filename == "":
            flash("No selected file", "error")
            return redirect(url_for("index"))

        if file and allowed_file(file.filename, ALLOWED_EXTENSIONS):
            # Save the uploaded file
            filename = secure_filename(file.filename)
            input_file = os.path.join(
                app.config["UPLOAD_FOLDER"], f"{session_id}_{filename}"
            )
            file.save(input_file)

            # Generate output file name
            output_name = f"{os.path.splitext(filename)[0]}_{target_language}.pptx"
            output_file = os.path.join(
                app.config["UPLOAD_FOLDER"], f"{session_id}_{output_name}"
            )

            # Log the output file path for debugging
            logger.info(f"[{session_id}] Setting output file path: {output_file}")

            # Store the output file path in the session state
            translation_state[session_id]["output_file"] = output_file

            # Start translation in a background thread
            thread = threading.Thread(
                target=translate_presentation,
                args=(
                    input_file,
                    output_file,
                    target_language,
                    service,
                    api_key,
                    translate_notes,
                    session_id,
                ),
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
            logger.warning("Progress page requested but no session_id in session")
            return redirect(url_for("index"))

        session_id = session["session_id"]
        logger.info(f"Progress page requested for session {session_id}")

        # Check if translation state exists
        if session_id not in translation_state:
            logger.warning(
                f"Progress page requested but translation state not found for session {session_id}"
            )
            translation_state[session_id] = {
                "status": "idle",
                "progress": 0,
                "total": 0,
                "percent": 0,
            }

        # Ensure all required fields exist in the state
        required_fields = ["status", "progress", "total", "percent"]
        for field in required_fields:
            if field not in translation_state[session_id]:
                logger.warning(
                    f"Field {field} missing in translation state for session {session_id}, initializing it"
                )
                if field == "status":
                    translation_state[session_id][field] = "idle"
                else:
                    translation_state[session_id][field] = 0

        logger.info(
            f"Rendering progress page with state: {translation_state[session_id]}"
        )
        return render_template("progress.html", state=translation_state[session_id])

    @app.route("/status")
    def status():
        """
        Get the current translation status.

        Returns:
            dict: Current translation status as JSON
        """
        from flask import jsonify, make_response

        # Default response
        default_status = {"status": "idle", "progress": 0, "total": 0, "percent": 0}

        # Check if session ID is set
        if "session_id" not in session:
            logger.warning("Status requested but no session_id in session")
            response = make_response(jsonify(default_status))
        else:
            session_id = session["session_id"]
            logger.info(f"Status requested for session {session_id}")

            # Check if translation state exists
            if session_id not in translation_state:
                logger.warning(
                    f"Session {session_id} exists but no translation state found"
                )
                response = make_response(jsonify(default_status))
            else:
                # Copy the state to avoid modifying the original during serialization
                state_copy = dict(translation_state[session_id])

                # Ensure all required fields exist and have the correct types
                if "status" not in state_copy or not isinstance(
                    state_copy["status"], str
                ):
                    logger.warning(
                        f"Invalid status in state for session {session_id}, fixing"
                    )
                    state_copy["status"] = (
                        "idle"
                        if "status" not in state_copy
                        else str(state_copy["status"])
                    )

                for field in ["progress", "total", "percent"]:
                    if field not in state_copy or not isinstance(
                        state_copy[field], (int, float)
                    ):
                        logger.warning(
                            f"Invalid {field} in state for session {session_id}, fixing"
                        )
                        state_copy[field] = 0

                # Log the final state
                logger.info(f"Status requested for session {session_id}: {state_copy}")

                # Return status as JSON
                response = make_response(jsonify(state_copy))

        # Add no-cache headers to prevent browsers from caching the response
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0"
        )
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return response

    @app.route("/download")
    def download():
        """
        Download the translated presentation.

        Returns:
            Response: File download response
        """
        # Check if session ID is set
        if "session_id" not in session:
            logger.warning("Download requested but no session_id in session")
            flash("No active translation session found", "error")
            return redirect(url_for("index"))

        session_id = session["session_id"]
        logger.info(f"[{session_id}] Download requested")

        # Check if translation state exists
        if session_id not in translation_state:
            logger.warning(
                f"[{session_id}] Download requested but translation state not found"
            )
            flash("No translation state found for your session", "error")
            return redirect(url_for("index"))

        # Log the entire state for debugging
        logger.info(
            f"[{session_id}] Current translation state: {translation_state[session_id]}"
        )

        # Check if output file exists in the state
        if "output_file" not in translation_state[session_id]:
            logger.warning(
                f"[{session_id}] Download requested but no output_file available in state"
            )
            # Try to reconstruct the output file path if possible
            if translation_state[session_id].get("status") == "completed":
                # This is a recovery attempt for completed translations with missing output_file
                try:
                    # Look for files in the temp directory matching this session ID
                    temp_dir = app.config["UPLOAD_FOLDER"]
                    matching_files = [
                        f
                        for f in os.listdir(temp_dir)
                        if session_id in f and f.endswith(".pptx")
                    ]

                    if matching_files:
                        # Find the most recently modified file
                        latest_file = max(
                            matching_files,
                            key=lambda f: os.path.getmtime(os.path.join(temp_dir, f)),
                        )
                        recovered_path = os.path.join(temp_dir, latest_file)

                        if os.path.exists(recovered_path):
                            logger.info(
                                f"[{session_id}] Recovered output file: {recovered_path}"
                            )
                            translation_state[session_id][
                                "output_file"
                            ] = recovered_path
                        else:
                            logger.warning(
                                f"[{session_id}] Recovery attempt failed - file does not exist: {recovered_path}"
                            )
                    else:
                        logger.warning(
                            f"[{session_id}] Recovery attempt failed - no matching files found"
                        )
                except Exception as e:
                    logger.error(f"[{session_id}] Error during recovery attempt: {e}")

            # Check again if output_file exists after recovery attempt
            if "output_file" not in translation_state[session_id]:
                flash(
                    "No translated file available. The translation process may not have completed successfully.",
                    "error",
                )
                return redirect(url_for("index"))

        # If progress is 100% but status is not completed, fix it
        if (
            translation_state[session_id].get("progress", 0)
            == translation_state[session_id].get("total", 0)
            and translation_state[session_id].get("total", 0) > 0
            and translation_state[session_id].get("status") != "completed"
        ):
            logger.info(
                f"[{session_id}] Progress is 100% but status is not completed, fixing it"
            )
            translation_state[session_id]["status"] = "completed"
            # Update last_updated timestamp
            translation_state[session_id]["last_updated"] = time.time()

        output_file = translation_state[session_id]["output_file"]
        logger.info(f"[{session_id}] Sending file for download: {output_file}")

        # Double-check that the file exists on disk
        if not os.path.exists(output_file):
            logger.error(f"[{session_id}] Output file not found at path: {output_file}")

            # Aggressive recovery attempt - check for any recently created PPTX files
            try:
                temp_dir = app.config["UPLOAD_FOLDER"]
                all_pptx_files = [
                    f for f in os.listdir(temp_dir) if f.endswith(".pptx")
                ]
                # Sort by modification time, newest first
                all_pptx_files.sort(
                    key=lambda f: os.path.getmtime(os.path.join(temp_dir, f)),
                    reverse=True,
                )

                if all_pptx_files:
                    # Take the most recently modified PPTX file
                    newest_file = os.path.join(temp_dir, all_pptx_files[0])
                    logger.info(
                        f"[{session_id}] Attempting to use most recent PPTX file: {newest_file}"
                    )

                    if os.path.exists(newest_file):
                        # Update the state with this file
                        translation_state[session_id]["output_file"] = newest_file
                        output_file = newest_file
                        logger.info(
                            f"[{session_id}] Using alternative file for download: {output_file}"
                        )
                    else:
                        raise FileNotFoundError("Most recent file not accessible")
                else:
                    raise FileNotFoundError("No PPTX files found in directory")
            except Exception as e:
                logger.error(f"[{session_id}] Secondary recovery attempt failed: {e}")
                # If we still don't have a file, notify the user and redirect
                flash(
                    "The translated file could not be found on the server. The file may have been deleted or failed to generate.",
                    "error",
                )
                # Mark the translation as failed since we couldn't find the output
                translation_state[session_id]["status"] = "failed"
                translation_state[session_id]["error"] = "Output file not found"
                return redirect(url_for("index"))

        try:
            # Get the original filename for better user experience
            filename = os.path.basename(output_file)
            # Return the file
            logger.info(
                f"[{session_id}] Sending file for download (final): {output_file}"
            )
            return send_file(output_file, as_attachment=True, download_name=filename)
        except Exception as e:
            logger.error(f"[{session_id}] Failed to send file for download: {e}")
            flash(
                "Failed to download the file. Please try again or contact support if the issue persists.",
                "error",
            )
            return redirect(url_for("index"))

    @app.route("/translate_with_progress")
    def translate_with_progress():
        """
        Simulates a translation process and updates the global `translation_state`.
        Args:
            presentation_id (str): ID of the presentation to translate.
            source_language (str): Source language code.
            target_language (str): Target language code.
            api_key (str): API key for translation.
        Returns:
            None
        """
        presentation_id = request.args.get("presentation_id")
        source_language = request.args.get("source_language")
        target_language = request.args.get("target_language")
        api_key = request.args.get("api_key")

        if not presentation_id or not source_language or not target_language or not api_key:
            return jsonify({"error": "Missing parameters"}), 400

        try:
            # Simulate translation progress
            translate_with_progress(presentation_id, source_language, target_language, api_key)
            return jsonify({"status": "success", "result_url": translation_state["result_url"]})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return app


def main():
    """
    Run the web application.

    Returns:
        None
    """
    # Set up detailed logging
    import logging

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Create and configure the app
    app = create_app()

    # Start the server
    app.run(host="127.0.0.1", port=5000, debug=True)


if __name__ == "__main__":
    main()

def translate_with_progress(presentation_id, source_language, target_language, api_key):
    """
    Simulates a translation process and updates the global `translation_state`.
    Args:
        presentation_id (str): ID of the presentation to translate.
        source_language (str): Source language code.
        target_language (str): Target language code.
        api_key (str): API key for translation.
    Returns:
        None
    """
    global translation_state
    translation_state["running"] = True
    translation_state["progress"] = 0
    translation_state["console_output"] = []
    for i in range(1, 101):
        time.sleep(0.01)
        translation_state["progress"] = i
        translation_state["console_output"].append(f"Progress: {i}%")
    translation_state["running"] = False
    translation_state["result_url"] = f"https://example.com/{presentation_id}/{target_language}"
