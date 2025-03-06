"""
Google API authentication module.

This module handles authentication with Google's API services for
accessing Google Slides and Google Drive.
"""

import os
import pickle
from typing import List, Optional, Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from gslides_translator.utils.exceptions import AuthenticationError, NetworkError
from gslides_translator.utils.logging import logger
from gslides_translator.config import CREDENTIALS_PATH, TOKEN_PATH

# Define the scopes needed for API access
SCOPES = [
    'https://www.googleapis.com/auth/presentations',
    'https://www.googleapis.com/auth/drive'
]


def get_credentials(
    credentials_path: str = CREDENTIALS_PATH,
    token_path: str = TOKEN_PATH,
    scopes: List[str] = SCOPES
) -> Credentials:
    """
    Get or create user credentials for Google API access.

    This function attempts to load existing credentials from the token file.
    If the token doesn't exist or is invalid, it initiates the OAuth flow
    to get new credentials.

    Args:
        credentials_path (str): Path to the credentials.json file
        token_path (str): Path to save/load the token file
        scopes (List[str]): OAuth scopes to request

    Returns:
        google.oauth2.credentials.Credentials: Valid credentials object

    Raises:
        AuthenticationError: If authentication fails
        NetworkError: If there's a network error during authentication
    """
    credentials = None

    # Ensure the directory for token_path exists
    token_dir = os.path.dirname(token_path)
    if token_dir:
        os.makedirs(token_dir, exist_ok=True)

    # Check if token file exists
    if os.path.exists(token_path):
        logger.info(f"Loading credentials from {token_path}")
        try:
            with open(token_path, 'rb') as token:
                credentials = pickle.load(token)
        except Exception as e:
            logger.warning(f"Failed to load credentials: {e}")

    # If no valid credentials, get new ones
    if not credentials or not credentials.valid:
        logger.info("Credentials not found or invalid, starting authentication flow")
        
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                logger.info("Refreshing expired credentials")
                credentials.refresh(Request())
            except Exception as e:
                logger.error(f"Failed to refresh credentials: {e}")
                credentials = None
        
        # If still no valid credentials, start OAuth flow
        if not credentials:
            if not os.path.exists(credentials_path):
                logger.error(f"Credentials file not found at {credentials_path}")
                raise AuthenticationError(
                    f"Credentials file not found at {credentials_path}. "
                    f"Please download credentials.json from Google Cloud Console "
                    f"and place it at this location."
                )
            
            try:
                logger.info(f"Starting OAuth flow with credentials from {credentials_path}")
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_path, scopes
                )
                credentials = flow.run_local_server(port=0)
                
                # Save the credentials for future use
                logger.info(f"Saving new credentials to {token_path}")
                with open(token_path, 'wb') as token:
                    pickle.dump(credentials, token)
            except Exception as e:
                logger.error(f"Authentication flow failed: {e}")
                if "Connection" in str(e) or "Network" in str(e):
                    raise NetworkError(f"Network error during authentication: {str(e)}")
                else:
                    raise AuthenticationError(f"Failed to authenticate: {str(e)}")

    return credentials


def get_slides_service(credentials: Optional[Credentials] = None) -> Any:
    """
    Get the Google Slides API service.

    Args:
        credentials (Credentials, optional): Google API credentials.
            If None, will be obtained using get_credentials().

    Returns:
        Resource: Google Slides API service

    Raises:
        AuthenticationError: If authentication fails
        NetworkError: If there's a network error
    """
    if not credentials:
        credentials = get_credentials()
    
    try:
        service = build('slides', 'v1', credentials=credentials)
        logger.info("Successfully created Google Slides service")
        return service
    except HttpError as e:
        logger.error(f"Failed to build Slides service: {e}")
        if e.resp.status in (403, 401):
            raise AuthenticationError(f"Authentication error with Google Slides API: {str(e)}")
        else:
            raise NetworkError(f"Network error with Google Slides API: {str(e)}")
    except Exception as e:
        logger.error(f"Unknown error building Slides service: {e}")
        raise AuthenticationError(f"Failed to connect to Google Slides API: {str(e)}")


def get_drive_service(credentials: Optional[Credentials] = None) -> Any:
    """
    Get the Google Drive API service.

    Args:
        credentials (Credentials, optional): Google API credentials.
            If None, will be obtained using get_credentials().

    Returns:
        Resource: Google Drive API service

    Raises:
        AuthenticationError: If authentication fails
        NetworkError: If there's a network error
    """
    if not credentials:
        credentials = get_credentials()
    
    try:
        service = build('drive', 'v3', credentials=credentials)
        logger.info("Successfully created Google Drive service")
        return service
    except HttpError as e:
        logger.error(f"Failed to build Drive service: {e}")
        if e.resp.status in (403, 401):
            raise AuthenticationError(f"Authentication error with Google Drive API: {str(e)}")
        else:
            raise NetworkError(f"Network error with Google Drive API: {str(e)}")
    except Exception as e:
        logger.error(f"Unknown error building Drive service: {e}")
        raise AuthenticationError(f"Failed to connect to Google Drive API: {str(e)}")


def revoke_credentials(token_path: str = TOKEN_PATH) -> None:
    """
    Revoke the current credentials and delete the token file.

    Args:
        token_path (str): Path to the token file

    Raises:
        AuthenticationError: If revocation fails
    """
    if os.path.exists(token_path):
        try:
            credentials = None
            with open(token_path, 'rb') as token:
                credentials = pickle.load(token)
            
            if credentials:
                credentials.revoke(Request())
                logger.info("Successfully revoked credentials")
            
            os.remove(token_path)
            logger.info(f"Deleted token file at {token_path}")
        except Exception as e:
            logger.error(f"Failed to revoke credentials: {e}")
            raise AuthenticationError(f"Failed to revoke credentials: {str(e)}")
    else:
        logger.warning(f"No token file found at {token_path}")


def validate_presentation_permissions(presentation_id: str, credentials: Optional[Credentials] = None) -> bool:
    """
    Validate that the user has permissions to access the presentation.

    Args:
        presentation_id (str): ID of the Google Slides presentation
        credentials (Credentials, optional): Google API credentials
            If None, will be obtained using get_credentials()

    Returns:
        bool: True if user has access, False otherwise

    Raises:
        AuthenticationError: If authentication fails
        NetworkError: If there's a network error
    """
    if not credentials:
        credentials = get_credentials()
    
    service = get_slides_service(credentials)
    
    try:
        # Try to get presentation metadata (minimal request)
        service.presentations().get(
            presentationId=presentation_id,
            fields="presentationId"
        ).execute()
        logger.info(f"Successfully validated access to presentation {presentation_id}")
        return True
    except HttpError as e:
        if e.resp.status == 404:
            logger.warning(f"Presentation {presentation_id} not found")
            return False
        elif e.resp.status in (403, 401):
            logger.warning(f"No permission to access presentation {presentation_id}")
            return False
        else:
            logger.error(f"Network error checking presentation access: {e}")
            raise NetworkError(f"Network error checking presentation access: {str(e)}")
    except Exception as e:
        logger.error(f"Error validating presentation permissions: {e}")
        raise AuthenticationError(f"Failed to validate presentation permissions: {str(e)}") 