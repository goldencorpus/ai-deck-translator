"""
Google API authentication module for the Google Slides Translator.
"""
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from .. import config

def authenticate_google():
    """
    Authenticate with Google API using OAuth 2.0.
    
    Returns:
        tuple: (slides_service, drive_service) - authenticated API service objects
    """
    creds = None
    token_path = config.TOKEN_FILE
    regenerate_token = False

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, config.GOOGLE_API_SCOPES)
        if not creds or not creds.valid:
            regenerate_token = True
        else:
            current_scopes = set(creds.scopes)
            required_scopes = set(config.GOOGLE_API_SCOPES)
            if not required_scopes.issubset(current_scopes):
                print("Token has insufficient permissions. Regenerating...")
                regenerate_token = True
    else:
        regenerate_token = True

    if regenerate_token:
        if os.path.exists(token_path):
            os.remove(token_path)
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', config.GOOGLE_API_SCOPES)
        creds = flow.run_local_server(port=0)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
            
    slides_service = build('slides', 'v1', credentials=creds)
    drive_service = build('drive', 'v3', credentials=creds)
    return slides_service, drive_service 