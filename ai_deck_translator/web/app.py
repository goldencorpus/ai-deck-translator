"""
Web interface for the AI Deck Translator application.
"""
import os
import io
import sys
import threading
from contextlib import redirect_stdout
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from .. import config
from ..core.translator import translate_slides
from ..pptx.translator import translate_pptx, list_recovery_files as list_pptx_recovery_files

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY
    
    # Global state for tracking translation progress
    translation_state = {
        'running': False,
        'progress': 0,
        'console_output': '',
        'result_url': None,
        'result_file': None,
        'translation_type': None  # 'slides' or 'pptx'
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
    
    def translate_slides_with_progress(presentation_id, source_language, target_language, api_key=None, resume_file=None):
        """Run the Google Slides translation process and update progress."""
        nonlocal translation_state
        
        # Reset state
        translation_state['running'] = True
        translation_state['progress'] = 0
        translation_state['console_output'] = 'Starting Google Slides translation...\n'
        translation_state['result_url'] = None
        translation_state['result_file'] = None
        translation_state['translation_type'] = 'slides'
        
        # Capture stdout to show in the web UI
        capture = CaptureStdout()
        
        try:
            with capture:
                # Set API key if provided
                if api_key:
                    os.environ["CLAUDE_API_KEY"] = api_key
                
                # Run the translation
                result = translate_slides(
                    presentation_id=presentation_id,
                    source_language=source_language,
                    target_language=target_language,
                    resume_file=resume_file
                )
                
                # Update state with result
                if result and 'presentation_url' in result:
                    translation_state['result_url'] = result['presentation_url']
        except Exception as e:
            translation_state['console_output'] += f"Error: {str(e)}\n"
        finally:
            # Update state
            translation_state['running'] = False
            translation_state['progress'] = 100
            translation_state['console_output'] += capture.get_output()
    
    def translate_pptx_with_progress(input_file, output_file, source_language, target_language, api_key=None, resume_file=None):
        """Run the PPTX translation process and update progress."""
        nonlocal translation_state
        
        # Reset state
        translation_state['running'] = True
        translation_state['progress'] = 0
        translation_state['console_output'] = 'Starting PowerPoint translation...\n'
        translation_state['result_url'] = None
        translation_state['result_file'] = None
        translation_state['translation_type'] = 'pptx'
        
        # Capture stdout to show in the web UI
        capture = CaptureStdout()
        
        try:
            with capture:
                # Set API key if provided
                if api_key:
                    os.environ["CLAUDE_API_KEY"] = api_key
                
                # Run the translation
                success = translate_pptx(
                    input_file=input_file,
                    output_file=output_file,
                    source_language=source_language,
                    target_language=target_language,
                    resume_file=resume_file
                )
                
                # Update state with result
                if success:
                    translation_state['result_file'] = output_file
        except Exception as e:
            translation_state['console_output'] += f"Error: {str(e)}\n"
        finally:
            # Update state
            translation_state['running'] = False
            translation_state['progress'] = 100
            translation_state['console_output'] += capture.get_output()
    
    @app.route('/')
    def index():
        """Render the main page."""
        return render_template('index.html')
    
    @app.route('/translate', methods=['POST'])
    def start_translation():
        """Start the translation process."""
        if translation_state['running']:
            flash('A translation is already in progress', 'warning')
            return redirect(url_for('index'))
        
        # Get common parameters
        source_language = request.form.get('source_language', 'en')
        target_language = request.form.get('target_language', 'ja')
        api_key = request.form.get('api_key', '')
        resume_file = request.form.get('resume_file', '')
        translation_type = request.form.get('translation_type', 'slides')
        
        if translation_type == 'slides':
            # Google Slides translation
            presentation_id = request.form.get('presentation_id', '')
            
            if not presentation_id:
                flash('Please enter a Google Slides Presentation ID', 'danger')
                return redirect(url_for('index'))
            
            # Start translation in a background thread
            thread = threading.Thread(
                target=translate_slides_with_progress,
                args=(presentation_id, source_language, target_language, api_key, resume_file)
            )
            thread.daemon = True
            thread.start()
            
            flash('Translation started', 'success')
            return redirect(url_for('index'))
        
        elif translation_type == 'pptx':
            # PPTX translation
            # Handle file upload
            if 'pptx_file' not in request.files:
                flash('No file selected', 'danger')
                return redirect(url_for('index'))
            
            file = request.files['pptx_file']
            
            if file.filename == '':
                flash('No file selected', 'danger')
                return redirect(url_for('index'))
            
            if not file.filename.endswith('.pptx'):
                flash('Please select a PowerPoint (.pptx) file', 'danger')
                return redirect(url_for('index'))
            
            # Save the uploaded file
            upload_folder = os.path.join(os.getcwd(), 'uploads')
            os.makedirs(upload_folder, exist_ok=True)
            
            input_file = os.path.join(upload_folder, file.filename)
            file.save(input_file)
            
            # Generate output file name
            base_name = os.path.splitext(input_file)[0]
            output_file = f"{base_name}_{target_language}.pptx"
            
            # Start translation in a background thread
            thread = threading.Thread(
                target=translate_pptx_with_progress,
                args=(input_file, output_file, source_language, target_language, api_key, resume_file)
            )
            thread.daemon = True
            thread.start()
            
            flash('Translation started', 'success')
            return redirect(url_for('index'))
        
        else:
            flash('Invalid translation type', 'danger')
            return redirect(url_for('index'))
    
    @app.route('/progress')
    def get_progress():
        """Return the current translation progress."""
        return jsonify({
            'running': translation_state['running'],
            'progress': translation_state['progress'],
            'console_output': translation_state['console_output'],
            'result_url': translation_state['result_url'],
            'result_file': translation_state['result_file'],
            'translation_type': translation_state['translation_type']
        })
    
    @app.route('/recovery-files')
    def list_recovery_files():
        """List available recovery files."""
        translation_type = request.args.get('type', 'slides')
        
        if translation_type == 'slides':
            from ..core.translator import list_recovery_files as list_slides_recovery_files
            recovery_files = list_slides_recovery_files()
        else:
            recovery_files = list_pptx_recovery_files()
        
        return jsonify(recovery_files)
    
    return app 