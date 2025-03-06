"""
Text extraction module for Google Slides presentations.
"""

def extract_text(service, presentation_id):  
    """
    Extract all text elements from a Google Slides presentation.
    
    Args:
        service: Google Slides API service
        presentation_id: ID of the presentation to extract text from
    
    Returns:
        tuple: (text_dict, slide_metadata)
            - text_dict: Dictionary mapping element IDs to text content
            - slide_metadata: List of dictionaries with slide information
    """
    presentation = service.presentations().get(presentationId=presentation_id).execute()  
    slides = presentation.get('slides', [])  
    text_dict = {}  
    slide_metadata = []  # Store structured context  
      
    for index, slide in enumerate(slides):  
        slide_info = {  
            "slide_number": index + 1,  
            "title": "",  
            "content": []  
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
                    print(f"Error processing text element: {e}")
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
                                print(f"Error processing table cell: {e}")
                                continue
                                
                            if cell_text:
                                # Create a unique ID for the table cell
                                cell_id = f"{element['objectId']}_r{row_idx}_c{col_idx}"
                                text_dict[cell_id] = cell_text
                                slide_info["content"].append(cell_text)
          
        slide_metadata.append(slide_info)  
      
    return text_dict, slide_metadata 