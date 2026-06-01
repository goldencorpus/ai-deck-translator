"""
Module for updating Google Slides presentations with translated text.
"""

import webbrowser


def update_slides(
    slides_service, drive_service, presentation_id, translated_texts, target_language
):
    """
    Update a Google Slides presentation with translated text.
    Creates a new copy of the presentation and updates it with translations.

    Args:
        slides_service: Google Slides API service
        drive_service: Google Drive API service
        presentation_id: ID of the original presentation
        translated_texts: Dictionary mapping element IDs to translated text
        target_language: Target language code for the presentation title

    Returns:
        str: ID of the new translated presentation
    """
    # First, get the original presentation
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
    copied_file = (
        drive_service.files().copy(fileId=presentation_id, body=file_metadata).execute()
    )

    new_presentation_id = copied_file["id"]

    # Now update the new presentation with translated texts
    requests = []
    for object_id, new_text in translated_texts.items():
        # Check if it's a table cell (has the format objectId_r{row}_c{col})
        if "_r" in object_id and "_c" in object_id:
            # Parse the table cell coordinates
            base_id, row_col = object_id.split("_r", 1)
            row_idx, col_idx = row_col.split("_c")

            # For table cells, we need to use different update format
            requests.append(
                {
                    "deleteText": {
                        "objectId": base_id,
                        "cellLocation": {
                            "rowIndex": int(row_idx),
                            "columnIndex": int(col_idx),
                        },
                        "textRange": {"type": "ALL"},
                    }
                }
            )
            requests.append(
                {
                    "insertText": {
                        "objectId": base_id,
                        "cellLocation": {
                            "rowIndex": int(row_idx),
                            "columnIndex": int(col_idx),
                        },
                        "insertionIndex": 0,
                        "text": new_text,
                    }
                }
            )
        else:
            # Regular text elements
            requests.append(
                {"deleteText": {"objectId": object_id, "textRange": {"type": "ALL"}}}
            )
            requests.append(
                {
                    "insertText": {
                        "objectId": object_id,
                        "insertionIndex": 0,
                        "text": new_text,
                    }
                }
            )

    # Process requests in batches since there might be a limit on request size
    batch_size = 100  # Adjust batch size as needed
    for i in range(0, len(requests), batch_size):
        batch_requests = requests[i : i + batch_size]
        try:
            slides_service.presentations().batchUpdate(
                presentationId=new_presentation_id, body={"requests": batch_requests}
            ).execute()
        except Exception as e:
            print(f"Error in update batch {i//batch_size + 1}: {e}")
            # Print the first few problematic requests for debugging
            problem_batch = requests[i : i + min(5, batch_size)]
            print(f"Problem might be in these requests: {problem_batch}")

    # Open the new presentation in browser
    presentation_url = (
        f"https://docs.google.com/presentation/d/{new_presentation_id}/edit"
    )
    print(f"Opening translated presentation: {presentation_url}")
    webbrowser.open(presentation_url)

    return new_presentation_id
