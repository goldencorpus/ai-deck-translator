"""
Google authentication module for the AI Deck Translator application.

This module handles authentication with Google APIs and provides functions for
interacting with Google Slides and Google Drive. It manages OAuth 2.0 authentication
flow, token storage, and API service creation.

Public Functions:
    authenticate_google: Authenticate with Google and get service objects
    get_presentation: Get a presentation by ID
    create_presentation_copy: Create a copy of a presentation
    batch_update_presentation: Apply a batch update to a presentation
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple, cast

import google.auth.transport.requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ai_deck_translator import config
from ai_deck_translator.utils.exceptions import AuthenticationError, NetworkError
from ai_deck_translator.utils.logging import get_logger

# Set up logging
logger = get_logger(__name__)


def authenticate_google() -> Tuple[Any, Any]:
    """
    Authenticate with Google API and return the service objects.

    This function handles the OAuth 2.0 authentication flow with Google. It attempts
    to load existing credentials from the token file, refreshes them if expired, or
    initiates a new authentication flow if needed. It then creates and returns the
    Google Slides and Google Drive service objects.

    Returns:
        tuple: A tuple containing two elements:
            - slides_service (googleapiclient.discovery.Resource): Google Slides API service
            - drive_service (googleapiclient.discovery.Resource): Google Drive API service

    Raises:
        AuthenticationError: If authentication fails due to invalid credentials,
            missing files, or user cancellation
        NetworkError: If there are network issues during API calls

    Example:
        >>> slides_service, drive_service = authenticate_google()
        >>> # Now you can use these services to interact with Google Slides and Drive
    """
    creds = None
    # Use the absolute ~/.gslides_translator/ paths (config.*_PATH) rather than the
    # bare "credentials.json"/"token.json" names, which would resolve against the CWD.
    token_file = getattr(config, "TOKEN_PATH", config.GOOGLE_TOKEN_FILE)
    credentials_file = getattr(
        config, "CREDENTIALS_PATH", config.GOOGLE_CREDENTIALS_FILE
    )
    scopes = config.GOOGLE_SCOPES

    logger.info(f"Authenticating with Google using token file: {token_file}")

    # Check if token file exists
    if os.path.exists(token_file):
        try:
            creds = Credentials.from_authorized_user_info(
                json.loads(open(token_file).read()), scopes
            )
            logger.info("Loaded existing credentials from token file")
        except Exception as e:
            logger.error(f"Error loading credentials: {str(e)}")
            raise AuthenticationError(f"Error loading credentials: {str(e)}")

    # If no valid credentials, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                logger.info("Refreshing expired credentials")
                creds.refresh(google.auth.transport.requests.Request())
            except Exception as e:
                logger.error(f"Error refreshing credentials: {str(e)}")
                raise AuthenticationError(f"Error refreshing credentials: {str(e)}")
        else:
            try:
                logger.info(
                    f"Starting OAuth flow with credentials from {credentials_file}"
                )
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_file, scopes
                )
                creds = flow.run_local_server(port=0)
                logger.info("Successfully completed OAuth flow")
            except Exception as e:
                logger.error(f"Error during OAuth flow: {str(e)}")
                raise AuthenticationError(f"Error during OAuth flow: {str(e)}")

        # Save the credentials for the next run
        try:
            logger.info(f"Saving credentials to {token_file}")
            os.makedirs(os.path.dirname(token_file) or ".", exist_ok=True)
            with open(token_file, "w") as token:
                token.write(creds.to_json())
            try:
                os.chmod(token_file, 0o600)  # OAuth token is a secret
            except OSError:
                pass
        except Exception as e:
            logger.error(f"Error saving credentials: {str(e)}")
            raise AuthenticationError(f"Error saving credentials: {str(e)}")

    # Build the services
    try:
        logger.info("Building Google Slides and Drive services")
        slides_service = build("slides", "v1", credentials=creds)
        drive_service = build("drive", "v3", credentials=creds)
        return slides_service, drive_service
    except HttpError as e:
        logger.error(f"Error connecting to Google API: {str(e)}")
        raise NetworkError(f"Error connecting to Google API: {str(e)}")
    except Exception as e:
        logger.error(f"Error building service: {str(e)}")
        raise AuthenticationError(f"Error building service: {str(e)}")


def build_services_from_refresh_token(
    refresh_token: str,
    client_id: str,
    client_secret: str,
    token_uri: str = "https://oauth2.googleapis.com/token",
    scopes: Optional[List[str]] = None,
) -> Tuple[Any, Any]:
    """
    Build Slides + Drive services from a per-user OAuth refresh token.

    This is the multi-tenant (SaaS) counterpart to authenticate_google(): instead of the
    single desktop-OAuth token in ~/.gslides_translator/, it acts on behalf of an individual
    customer who granted access via the web "Sign in with Google" + Picker flow (scope
    drive.file). The worker stores the customer's refresh token, calls this to mint a fresh
    access token, and runs the native translation as that customer — so the translated copy
    lands in the customer's own Drive.

    Args:
        refresh_token: The customer's long-lived OAuth refresh token.
        client_id: The web OAuth client id.
        client_secret: The web OAuth client secret.
        token_uri: Google's token endpoint (override only for testing).
        scopes: Optional scope list. Default None — the access token inherits whatever the
            refresh token was granted (drive.file for the SaaS flow).

    Returns:
        tuple: (slides_service, drive_service).

    Raises:
        AuthenticationError: If the refresh token is missing/revoked or the token refresh fails.
        NetworkError: If building the API services fails.
    """
    if not refresh_token:
        raise AuthenticationError("No refresh token provided")
    try:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri=token_uri,
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes,
        )
        creds.refresh(google.auth.transport.requests.Request())
    except Exception as e:
        logger.error(f"Error refreshing user credentials: {str(e)}")
        raise AuthenticationError(f"Error refreshing user credentials: {str(e)}")

    try:
        slides_service = build("slides", "v1", credentials=creds)
        drive_service = build("drive", "v3", credentials=creds)
        return slides_service, drive_service
    except HttpError as e:
        logger.error(f"Error connecting to Google API: {str(e)}")
        raise NetworkError(f"Error connecting to Google API: {str(e)}")
    except Exception as e:
        logger.error(f"Error building service: {str(e)}")
        raise AuthenticationError(f"Error building service: {str(e)}")


def get_presentation(slides_service: Any, presentation_id: str) -> Dict[str, Any]:
    """
    Get a presentation by ID.

    This function retrieves a Google Slides presentation by its ID.

    Args:
        slides_service (googleapiclient.discovery.Resource): Google Slides API service object
            obtained from authenticate_google()
        presentation_id (str): ID of the presentation to retrieve
            This can be found in the URL: docs.google.com/presentation/d/{PRESENTATION_ID}/edit

    Returns:
        dict: Presentation data containing all slides and elements

    Raises:
        NetworkError: If the API request fails or the presentation is not found

    Example:
        >>> slides_service, _ = authenticate_google()
        >>> presentation = get_presentation(slides_service, "1rppKpwoUKmf65wAg7J9gSVpL279IBX4EmbWM7yGiS6s")
        >>> print(f"Presentation title: {presentation.get('title')}")
    """
    try:
        logger.info(f"Getting presentation with ID: {presentation_id}")
        return cast(
            Dict[str, Any],
            slides_service.presentations()
            .get(presentationId=presentation_id)
            .execute(),
        )
    except HttpError as e:
        if e.resp.status == 404:
            logger.error(f"Presentation not found: {presentation_id}")
            raise NetworkError(f"Presentation not found: {presentation_id}")
        else:
            logger.error(f"Error getting presentation: {str(e)}")
            raise NetworkError(f"Error getting presentation: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting presentation: {str(e)}")
        raise NetworkError(f"Error getting presentation: {str(e)}")


def create_presentation_copy(
    drive_service: Any, presentation_id: str, title: str
) -> str:
    """
    Create a copy of a presentation.

    This function creates a copy of an existing Google Slides presentation with a new title.
    The copy is created in the same Google Drive folder as the original.

    Args:
        drive_service (googleapiclient.discovery.Resource): Google Drive API service object
            obtained from authenticate_google()
        presentation_id (str): ID of the presentation to copy
            This can be found in the URL: docs.google.com/presentation/d/{PRESENTATION_ID}/edit
        title (str): Title for the new presentation

    Returns:
        str: ID of the new presentation

    Raises:
        NetworkError: If the API request fails

    Example:
        >>> _, drive_service = authenticate_google()
        >>> new_id = create_presentation_copy(drive_service,
        ...                                  "1rppKpwoUKmf65wAg7J9gSVpL279IBX4EmbWM7yGiS6s",
        ...                                  "My Presentation - Japanese")
        >>> print(f"New presentation: https://docs.google.com/presentation/d/{new_id}/edit")
    """
    try:
        logger.info(
            f"Creating copy of presentation {presentation_id} with title: {title}"
        )
        # Create a copy of the presentation
        copy = (
            drive_service.files()
            .copy(fileId=presentation_id, body={"name": title})
            .execute()
        )

        logger.info(f"Created new presentation with ID: {copy['id']}")
        return cast(str, copy["id"])
    except HttpError as e:
        logger.error(f"Error copying presentation: {str(e)}")
        raise NetworkError(f"Error copying presentation: {str(e)}")
    except Exception as e:
        logger.error(f"Error copying presentation: {str(e)}")
        raise NetworkError(f"Error copying presentation: {str(e)}")


def batch_update_presentation(
    slides_service: Any, presentation_id: str, requests: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Apply a batch update to a presentation.

    This function applies a batch of update requests to a Google Slides presentation.
    It can be used to update text, formatting, and other properties of slides and elements.

    Args:
        slides_service (googleapiclient.discovery.Resource): Google Slides API service object
            obtained from authenticate_google()
        presentation_id (str): ID of the presentation to update
            This can be found in the URL: docs.google.com/presentation/d/{PRESENTATION_ID}/edit
        requests (list): List of update request dictionaries
            Each request should follow the Google Slides API batch update format

    Returns:
        dict: Response from the API containing the result of the batch update

    Raises:
        NetworkError: If the API request fails

    Example:
        >>> slides_service, _ = authenticate_google()
        >>> requests = [
        ...     {
        ...         'replaceAllText': {
        ...             'containsText': {'text': 'Hello'},
        ...             'replaceText': 'Bonjour'
        ...         }
        ...     }
        ... ]
        >>> result = batch_update_presentation(slides_service,
        ...                                   "1rppKpwoUKmf65wAg7J9gSVpL279IBX4EmbWM7yGiS6s",
        ...                                   requests)
    """
    try:
        logger.info(
            f"Applying batch update to presentation {presentation_id} with {len(requests)} requests"
        )
        return cast(
            Dict[str, Any],
            slides_service.presentations()
            .batchUpdate(presentationId=presentation_id, body={"requests": requests})
            .execute(),
        )
    except HttpError as e:
        logger.error(f"Error updating presentation: {str(e)}")
        raise NetworkError(f"Error updating presentation: {str(e)}")
    except Exception as e:
        logger.error(f"Error updating presentation: {str(e)}")
        raise NetworkError(f"Error updating presentation: {str(e)}")
