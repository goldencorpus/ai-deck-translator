"""
Module for updating Google Slides presentations with translated text.

This module provides functionality for creating a copy of a Google Slides presentation
and updating it with translated text. It handles various types of text elements including
shapes, tables, and notes, ensuring that formatting and layout are preserved.

Public Functions:
    update_slides: Create a copy of a presentation and update it with translated text
"""

import webbrowser
from ..utils.logging import get_logger
from ..utils.exceptions import NetworkError, PresentationError

# Set up logging
logger = get_logger(__name__)


def update_slides(
    slides_service, drive_service, presentation_id, translated_texts, target_language=None, web_state=None, **kwargs
):
    """
    Update a Google Slides presentation with translated text.
    (web_state and **kwargs are accepted for test compatibility.)

    This function creates a new copy of the original presentation and updates all text
    elements with their translated versions. It preserves formatting, layout, and non-text
    elements. The new presentation is created in the same Google Drive folder as the original.

    Args:
        slides_service (googleapiclient.discovery.Resource): Google Slides API service object
            obtained from authenticate_google()
        drive_service (googleapiclient.discovery.Resource): Google Drive API service object
            obtained from authenticate_google()
        presentation_id (str): ID of the original presentation to copy and update
            This can be found in the URL: docs.google.com/presentation/d/{PRESENTATION_ID}/edit
        translated_texts (dict): Dictionary mapping element IDs to translated text
            Keys should match the element IDs from extract_text()
            Values should be the translated text for each element
        target_language (str): Target language code (e.g., 'ja' for Japanese)
            Used to append to the presentation title
        web_state (str): Web state for test compatibility
        **kwargs: Additional keyword arguments for test compatibility

    Returns:
        str: ID of the new translated presentation

    Raises:
        NetworkError: If there are network issues during API calls
        PresentationError: If there are issues with the presentation structure

    Example:
        >>> from ai_deck_translator.auth.google_auth import authenticate_google
        >>> slides_service, drive_service = authenticate_google()
        >>> new_id = update_slides(slides_service, drive_service,
        ...                        "1rppKpwoUKmf65wAg7J9gSVpL279IBX4EmbWM7yGiS6s",
        ...                        {"objectId1": "Translated text 1"}, "ja")
        >>> print(f"New presentation: https://docs.google.com/presentation/d/{new_id}/edit")
    """
    try:
        # First, get the original presentation
        logger.info(f"Getting original presentation: {presentation_id}")
        presentation = (
            slides_service.presentations().get(presentationId=presentation_id).execute()
        )
        original_title = presentation.get("title", "Presentation")
        new_title = f"{original_title} - {target_language}"

        # Get file metadata to copy the presentation
        file_metadata = {
            "name": new_title,
            "mimeType": "application/vnd.google-apps.presentation",
        }

        # Copy the file using Drive API
        logger.info(f"Creating copy of presentation with title: {new_title}")
        copied_file = (
            drive_service.files()
            .copy(fileId=presentation_id, body=file_metadata)
            .execute()
        )

        new_presentation_id = copied_file["id"]
        logger.info(f"Created new presentation with ID: {new_presentation_id}")

        # Now update the new presentation with translated texts
        requests = []
        notes_requests = []

        # Process regular text elements
        for object_id, new_text in translated_texts.items():
            # Skip notes for now, we'll handle them separately
            if "_notes" in object_id:
                continue

            # Check if it's a table cell (has the format objectId_r{row}_c{col})
            if "_r" in object_id and "_c" in object_id:
                # Parse the table cell coordinates
                base_id, row_col = object_id.split("_r", 1)
                row_idx, col_idx = row_col.split("_c")

                # For table cells, we need to use different update format
                requests.append(
                    {
                        "tableText": {
                            "tableObjectId": base_id,
                            "tableRowIndex": int(row_idx),
                            "tableColumnIndex": int(col_idx),
                            "text": new_text,
                        }
                    }
                )
            else:
                # For regular shapes, use replaceAllText
                requests.append(
                    {
                        "replaceAllShapesWithText": {
                            "containsText": {"text": "*", "matchCase": False},
                            "pageObjectIds": [],
                            "replaceText": new_text,
                            "objectIds": [object_id],
                        }
                    }
                )

        # Process slide notes
        for object_id, new_text in translated_texts.items():
            if "_notes" in object_id and "slide" in object_id:
                # Extract slide number from the object ID
                slide_number = int(object_id.split("slide")[1].split("_")[0])

                # Get the slide ID
                slide_id = presentation.get("slides", [])[slide_number - 1].get(
                    "objectId"
                )

                if slide_id:
                    notes_requests.append(
                        {
                            "replaceAllText": {
                                "replaceText": new_text,
                                "pageObjectIds": [slide_id],
                                "containsText": {"text": "*", "matchCase": False},
                            }
                        }
                    )

        # Apply the updates in batches to avoid exceeding API limits
        batch_size = 100  # Google Slides API has a limit of 100 requests per batch

        # Update regular text elements
        for i in range(0, len(requests), batch_size):
            batch = requests[i : i + batch_size]
            logger.info(
                f"Applying batch update {i//batch_size + 1}/{(len(requests) + batch_size - 1)//batch_size}"
            )

            try:
                slides_service.presentations().batchUpdate(
                    presentationId=new_presentation_id, body={"requests": batch}
                ).execute()
            except Exception as e:
                logger.error(f"Error applying batch update: {e}")
                raise NetworkError(f"Failed to update presentation: {str(e)}")

        # Update slide notes
        if notes_requests:
            logger.info(f"Updating {len(notes_requests)} slide notes")

            for i in range(0, len(notes_requests), batch_size):
                batch = notes_requests[i : i + batch_size]

                try:
                    slides_service.presentations().batchUpdate(
                        presentationId=new_presentation_id, body={"requests": batch}
                    ).execute()
                except Exception as e:
                    logger.warning(f"Error updating slide notes: {e}")
                    # Continue even if notes update fails

        # Open the presentation in the browser
        presentation_url = (
            f"https://docs.google.com/presentation/d/{new_presentation_id}/edit"
        )
        logger.info(f"Opening translated presentation: {presentation_url}")
        webbrowser.open(presentation_url)

        return new_presentation_id
    except Exception as e:
        logger.error(f"Error updating presentation: {e}")
        if "Network" in str(e):
            raise NetworkError(f"Network error updating presentation: {str(e)}")
        else:
            raise PresentationError(f"Error updating presentation: {str(e)}")
