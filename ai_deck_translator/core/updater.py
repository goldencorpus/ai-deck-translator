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

# Set up logging
logger = get_logger(__name__)

def update_slides(slides_service, drive_service, presentation_id, translated_texts, target_language):
    """
    Update a Google Slides presentation with translated text.
    
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
    
    Returns:
        str: ID of the new translated presentation
        
    Raises:
        NetworkError: If there are network issues during API calls
        
    Example:
        >>> from ai_deck_translator.auth.google_auth import authenticate_google
        >>> slides_service, drive_service = authenticate_google()
        >>> new_id = update_slides(slides_service, drive_service, 
        ...                        "1rppKpwoUKmf65wAg7J9gSVpL279IBX4EmbWM7yGiS6s",
        ...                        {"objectId1": "Translated text 1"}, "ja")
        >>> print(f"New presentation: https://docs.google.com/presentation/d/{new_id}/edit")
    """
    # First, get the original presentation 
    presentation = slides_service.presentations().get(presentationId=presentation_id).execute()
    original_title = presentation.get('title', 'Presentation')
    new_title = f"{original_title} - {target_language}"
    
    # Get file metadata to copy the presentation
    file_metadata = {
        'name': new_title,
        'mimeType': 'application/vnd.google-apps.presentation'
    }
    
    # Copy the file using Drive API
    copied_file = drive_service.files().copy(
        fileId=presentation_id, 
        body=file_metadata
    ).execute()
    
    new_presentation_id = copied_file['id']
    
    # Now update the new presentation with translated texts
    requests = []
    for object_id, new_text in translated_texts.items():
        # Check if it's a table cell (has the format objectId_r{row}_c{col})
        if '_r' in object_id and '_c' in object_id:
            # Parse the table cell coordinates
            base_id, row_col = object_id.split('_r', 1)
            row_idx, col_idx = row_col.split('_c')
            
            # For table cells, we need to use different update format
            requests.append({
                "deleteText": {
                    "objectId": base_id,
                    "cellLocation": {
                        "rowIndex": int(row_idx),
                        "columnIndex": int(col_idx)
                    },
                    "textRange": {"type": "ALL"}
                }
            })
            requests.append({
                "insertText": {
                    "objectId": base_id,
                    "cellLocation": {
                        "rowIndex": int(row_idx),
                        "columnIndex": int(col_idx)
                    },
                    "insertionIndex": 0,
                    "text": new_text
                }
            })
        else:
            # Regular text elements
            requests.append({"deleteText": {"objectId": object_id, "textRange": {"type": "ALL"}}})
            requests.append({"insertText": {"objectId": object_id, "insertionIndex": 0, "text": new_text}})
    
    # Process requests in batches since there might be a limit on request size
    batch_size = 100  # Adjust batch size as needed
    for i in range(0, len(requests), batch_size):
        batch_requests = requests[i:i + batch_size]
        try:
            slides_service.presentations().batchUpdate(
                presentationId=new_presentation_id, 
                body={"requests": batch_requests}
            ).execute()
        except Exception as e:
            print(f"Error in update batch {i//batch_size + 1}: {e}")
            # Print the first few problematic requests for debugging
            problem_batch = requests[i:i+min(5, batch_size)]
            print(f"Problem might be in these requests: {problem_batch}")
    
    # Open the new presentation in browser
    presentation_url = f"https://docs.google.com/presentation/d/{new_presentation_id}/edit"
    print(f"Opening translated presentation: {presentation_url}")
    webbrowser.open(presentation_url)
    
    return new_presentation_id 