"""
Configuration settings for the Google Slides Translator application.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Google API scopes
GOOGLE_API_SCOPES = [
    'https://www.googleapis.com/auth/presentations', 
    'https://www.googleapis.com/auth/drive'
]

# Token file for Google API authentication
TOKEN_FILE = 'token.json'

# Claude API settings
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
CLAUDE_MODEL = "claude-3-7-sonnet"  # Default model to use

# Default language settings
DEFAULT_SOURCE_LANGUAGE = "en"  # English
DEFAULT_TARGET_LANGUAGE = "ja"  # Japanese

# Translation batch settings
MAX_INPUT_TOKENS = 150000
PROMPT_TOKENS = 2000
MAX_RETRIES = 3

# Recovery settings
RECOVERY_DIR = "translation_recovery"

# Web UI settings
SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(24))
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000 