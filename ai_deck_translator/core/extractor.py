"""
Text extraction module for Google Slides presentations.

This module provides functionality for extracting text content from Google Slides
presentations while preserving the structure and context of the content. It handles
various types of text elements including shapes, tables, and notes.

Public Functions:
    extract_text: Extract all text elements from a Google Slides presentation
"""
from ..utils.logging import get_logger
from ..utils.exceptions import NetworkError

# Set up logging
logger = get_logger(__name__)

def extract_text(service, presentation_id):  
    """
    Extract all text elements from a Google Slides presentation.
    
    This function retrieves a Google Slides presentation and extracts all text content
    from it, including text in shapes, tables, and notes. It preserves the structure
    and context of the content to ensure accurate translation.
    
    Args:
        service (googleapiclient.discovery.Resource): Google Slides API service object
            obtained from authenticate_google()
        presentation_id (str): ID of the presentation to extract text from
            This can be found in the URL: docs.google.com/presentation/d/{PRESENTATION_ID}/edit
    
    Returns:
        tuple: A tuple containing two elements:
            - text_dict (dict): Dictionary mapping element IDs to text content
                Keys are unique identifiers for text elements
                Values are the text content of those elements
            - slide_metadata (list): List of dictionaries with slide information
                Each dictionary contains metadata about a slide, including:
                    - slide_number (int): The slide number (1-indexed)
                    - title (str): The slide title, if available
                    - content (list): List of text content in the slide
                    - notes (str): Speaker notes for the slide, if available
    
    Raises:
        NetworkError: If there are network issues during API calls
        
    Example:
        >>> from ai_deck_translator.auth.google_auth import authenticate_google
        >>> slides_service, _ = authenticate_google()
        >>> text_dict, slide_metadata = extract_text(slides_service, "1rppKpwoUKmf65wAg7J9gSVpL279IBX4EmbWM7yGiS6s")
        >>> print(f"Extracted {len(text_dict)} text elements from {len(slide_metadata)} slides")
    """
    try:
        logger.info(f"Extracting text from presentation: {presentation_id}")
        presentation = service.presentations().get(presentationId=presentation_id).execute()  
        slides = presentation.get('slides', [])  
        text_dict = {}  
        slide_metadata = []  # Store structured context  
        
        logger.info(f"Found {len(slides)} slides in presentation")
        
        for index, slide in enumerate(slides):  
            slide_number = index + 1
            logger.debug(f"Processing slide {slide_number}")
            
            slide_info = {  
                "slide_number": slide_number,  
                "title": "",  
                "content": [],
                "notes": ""
            }  
              
            # Process regular shape elements (text boxes, etc.)
            for element in slide.get('pageElements', []):  
                # Handle shapes (text boxes, etc.)
                shape = element.get('shape')  
                if shape and 'text' in shape:  
                    text_elements = shape.get('text', {}).get('textElements', [])  
                    full_text = ""
                    
                    try:
                        full_text = "".join(te.get('textRun', {}).get('content', '') 
                                           for te in text_elements if 'textRun' in te).strip()
                    except Exception as e:
                        logger.error(f"Error processing text element: {e}")
                        continue
                        
                    if full_text:  
                        text_dict[element['objectId']] = full_text  
                        slide_info["content"].append(full_text)
                        
                        # Check if this might be the slide title (typically first text box)
                        if not slide_info["title"] and element.get('transform', {}).get('scaleX', 0) > 0:
                            slide_info["title"] = full_text
                
                # Handle tables
                table = element.get('table')
                if table:
                    for row_idx, row in enumerate(table.get('tableRows', [])):
                        for col_idx, cell in enumerate(row.get('tableCells', [])):
                            if 'text' in cell:
                                text_elements = cell.get('text', {}).get('textElements', [])
                                cell_text = ""
                                
                                try:
                                    cell_text = "".join(te.get('textRun', {}).get('content', '') 
                                                      for te in text_elements if 'textRun' in te).strip()
                                except Exception as e:
                                    logger.error(f"Error processing table cell: {e}")
                                    continue
                                    
                                if cell_text:
                                    # Create a unique ID for the table cell
                                    cell_id = f"{element['objectId']}_r{row_idx}_c{col_idx}"
                                    text_dict[cell_id] = cell_text
                                    slide_info["content"].append(cell_text)
            
            # Extract speaker notes
            if 'slideProperties' in slide and 'notesPage' in slide['slideProperties']:
                notes_page = slide['slideProperties']['notesPage']
                if 'pageElements' in notes_page:
                    for notes_element in notes_page['pageElements']:
                        if 'shape' in notes_element and 'text' in notes_element['shape']:
                            notes_text_elements = notes_element['shape']['text'].get('textElements', [])
                            notes_text = ""
                            
                            try:
                                notes_text = "".join(te.get('textRun', {}).get('content', '') 
                                                   for te in notes_text_elements if 'textRun' in te).strip()
                            except Exception as e:
                                logger.error(f"Error processing notes text: {e}")
                                continue
                                
                            if notes_text:
                                notes_id = f"slide{slide_number}_notes"
                                text_dict[notes_id] = notes_text
                                slide_info["notes"] = notes_text
                                logger.debug(f"Extracted notes for slide {slide_number}")
              
            slide_metadata.append(slide_info)  
        
        logger.info(f"Extracted {len(text_dict)} text elements from {len(slide_metadata)} slides")
        return text_dict, slide_metadata
    except Exception as e:
        logger.error(f"Error extracting text from presentation: {e}")
        raise NetworkError(f"Failed to extract text from presentation: {str(e)}") 