"""
Web interface for the Google Slides Translator application.
"""
import os
import io
import sys
import threading
from contextlib import redirect_stdout
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from .. import config
from ..core.translator import translate_slides

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY
    
    # Global state for tracking translation progress
    translation_state = {
        'running': False,
        'progress': 0,
        'console_output': '',
        'result_url': None
    }
    
    # Create a custom stdout capture
    class CaptureStdout:
        def __init__(self):
            self.buffer = io.StringIO()
        
        def __enter__(self):
            self.old_stdout = sys.stdout
            sys.stdout = self.buffer
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            sys.stdout = self.old_stdout
        
        def get_output(self):
            return self.buffer.getvalue()
    
    def translate_with_progress(presentation_id, source_language, target_language, api_key=None, resume_file=None):
        """Run the translation process and update progress."""
        nonlocal translation_state
        
        # Reset state
        translation_state['running'] = True
        translation_state['progress'] = 0
        translation_state['console_output'] = 'Starting translation...\n'
        translation_state['result_url'] = None
        
        # Set API key if provided
        if api_key:
            os.environ["CLAUDE_API_KEY"] = api_key
        
        # Capture stdout
        with CaptureStdout() as capture:
            try:
                # Run the translation process
                new_presentation_id = translate_slides(
                    presentation_id=presentation_id,
                    source_language=source_language,
                    target_language=target_language,
                    resume_file=resume_file,
                    web_state=translation_state
                )
                
                # Create the presentation URL
                presentation_url = f"https://docs.google.com/presentation/d/{new_presentation_id}/edit"
                translation_state['result_url'] = presentation_url
                
            except Exception as e:
                translation_state['console_output'] += f"\nError: {str(e)}\n"
                print(f"Error in translation process: {e}")
            finally:
                # Mark as complete
                translation_state['running'] = False
                
                # Capture any final output
                output = capture.get_output()
                if output:
                    translation_state['console_output'] += output
    
    @app.route('/')
    def index():
        """Render the main page."""
        # Update session with current translation state
        session['translation_running'] = translation_state['running']
        session['progress'] = translation_state['progress']
        session['console_output'] = translation_state['console_output']
        session['result_url'] = translation_state['result_url']
        return render_template('index.html')
    
    @app.route('/translate', methods=['POST'])
    def start_translation():
        """Start the translation process."""
        presentation_id = request.form.get('presentation_id')
        source_language = request.form.get('source_language')
        target_language = request.form.get('target_language')
        api_key = request.form.get('api_key')
        resume_file = request.form.get('resume_file')
        
        if not presentation_id:
            flash('Please enter a valid presentation ID', 'danger')
            return redirect(url_for('index'))
        
        if translation_state['running']:
            flash('A translation is already in progress', 'warning')
            return redirect(url_for('index'))
        
        # Start translation in a background thread
        thread = threading.Thread(
            target=translate_with_progress,
            args=(presentation_id, source_language, target_language, api_key, resume_file)
        )
        thread.daemon = True
        thread.start()
        
        flash('Translation started!', 'success')
        return redirect(url_for('index'))
    
    @app.route('/progress')
    def get_progress():
        """Get the current translation progress as JSON."""
        return jsonify({
            'running': translation_state['running'],
            'progress': translation_state['progress'],
            'console_output': translation_state['console_output'],
            'result_url': translation_state['result_url']
        })
    
    @app.route('/recovery-files')
    def list_recovery_files():
        """List available recovery files."""
        from ..utils.recovery import list_recovery_files
        recovery_files = list_recovery_files()
        return jsonify(recovery_files)
    
    return app 