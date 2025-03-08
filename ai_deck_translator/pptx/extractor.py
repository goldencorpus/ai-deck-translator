"""
PPTX Extractor module for extracting text from PowerPoint presentations.
"""
import os
import zipfile
import xml.etree.ElementTree as ET
from pptx import Presentation
import re

# XML namespaces used in PPTX files
namespaces = {
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'dgm': 'http://schemas.openxmlformats.org/drawingml/2006/diagram'
}

def extract_from_smartart(pptx_file, rels_path, rel_id):
    """
    Extract text from SmartArt diagrams that python-pptx cannot access directly.
    
    Args:
        pptx_file: Path to the PPTX file
        rels_path: Path to the relationships file within the PPTX
        rel_id: Relationship ID for the SmartArt
        
    Returns:
        list: List of text strings from the SmartArt
    """
    texts = []
    
    with zipfile.ZipFile(pptx_file, 'r') as zip_ref:
        # Find the target path from the relationship
        rels_content = zip_ref.read(rels_path).decode('utf-8')
        rels_root = ET.fromstring(rels_content)
        
        target_path = None
        for rel in rels_root.findall('.//Relationship[@Id="' + rel_id + '"]', {'': 'http://schemas.openxmlformats.org/package/2006/relationships'}):
            target_path = rel.get('Target')
            break
            
        if not target_path:
            return texts
            
        # Convert target path to full path within the PPTX
        if target_path.startswith('/'):
            diagram_path = target_path[1:]  # Remove leading slash
        else:
            # Handle relative paths
            base_path = os.path.dirname(rels_path)
            diagram_path = os.path.normpath(os.path.join(base_path, '..', target_path))
            
        # Extract text from the diagram
        try:
            diagram_content = zip_ref.read(diagram_path).decode('utf-8')
            diagram_root = ET.fromstring(diagram_content)
            
            # Extract text from various diagram elements
            for text_elem in diagram_root.findall('.//dgm:t', namespaces):
                if text_elem.text and text_elem.text.strip():
                    texts.append(text_elem.text.strip())
        except:
            pass  # Skip if there's an error reading the diagram
            
    return texts

def extract_text(pptx_file):
    """
    Extract text from PowerPoint presentation with enhanced support for various text content types.
    
    Args:
        pptx_file: Path to the PPTX file
        
    Returns:
        dict: Dictionary of text elements with unique IDs
        list: Metadata about slides and text elements
    """
    text_dict = {}
    slide_metadata = []
    
    # Standard python-pptx extraction
    prs = Presentation(pptx_file)
    
    # Extract presentation title if available
    if prs.core_properties.title:
        text_dict["presentation_title"] = prs.core_properties.title
        slide_metadata.append({
            "id": "presentation_title",
            "type": "presentation_title",
            "slide_number": 0,
            "context": "Presentation Title"
        })
    
    # Process each slide
    for slide_idx, slide in enumerate(prs.slides):
        slide_number = slide_idx + 1
        slide_layout = slide.slide_layout.name if hasattr(slide, 'slide_layout') and hasattr(slide.slide_layout, 'name') else "Unknown Layout"
        
        # Add slide metadata
        slide_meta = {
            "slide_number": slide_number,
            "layout": slide_layout,
            "elements": []
        }
        
        # Extract text from shapes
        for shape_idx, shape in enumerate(slide.shapes):
            shape_id = f"slide{slide_number}_shape{shape_idx}"
            
            # Extract text from text frames
            if hasattr(shape, "text") and shape.text.strip():
                text_dict[shape_id] = shape.text
                
                # Add metadata for this shape
                element_meta = {
                    "id": shape_id,
                    "type": "shape",
                    "shape_type": shape.name if hasattr(shape, "name") else "Unknown Shape"
                }
                slide_meta["elements"].append(element_meta)
            
            # Extract text from tables
            if shape.has_table:
                for row_idx, row in enumerate(shape.table.rows):
                    for col_idx, cell in enumerate(row.cells):
                        if cell.text.strip():
                            cell_id = f"{shape_id}_table_r{row_idx}c{col_idx}"
                            text_dict[cell_id] = cell.text
                            
                            # Add metadata for this table cell
                            element_meta = {
                                "id": cell_id,
                                "type": "table_cell",
                                "row": row_idx,
                                "column": col_idx,
                                "parent_shape": shape_id
                            }
                            slide_meta["elements"].append(element_meta)
        
        # Deep XML extraction for elements that python-pptx might miss
        try:
            with zipfile.ZipFile(pptx_file, 'r') as zip_ref:
                # Get slide XML content
                slide_path = f"ppt/slides/slide{slide_number}.xml"
                slide_content = zip_ref.read(slide_path).decode('utf-8')
                slide_root = ET.fromstring(slide_content)
                
                # Get slide relationships
                slide_rels_path = f"ppt/slides/_rels/slide{slide_number}.xml.rels"
                
                # Extract SmartArt text
                for rel_elem in slide_root.findall('.//p:graphicFrame//a:graphicData[@uri="http://schemas.openxmlformats.org/drawingml/2006/diagram"]/../../../..', namespaces):
                    # Find the relationship ID for this SmartArt
                    rel_id = None
                    for elem in rel_elem.findall('.//a:blip', namespaces):
                        rel_id = elem.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                        break
                    
                    if rel_id:
                        smartart_text = extract_from_smartart(pptx_file, slide_rels_path, rel_id)
                        if smartart_text:
                            smartart_id = f"slide{slide_number}_smartart_{rel_id}"
                            text_dict[smartart_id] = "\n".join(smartart_text)
                            
                            # Add metadata for this SmartArt
                            element_meta = {
                                "id": smartart_id,
                                "type": "smartart",
                                "rel_id": rel_id
                            }
                            slide_meta["elements"].append(element_meta)
                
                # Find all text in the slide, including those that might be missed by python-pptx
                for text_elem in slide_root.findall('.//a:t', namespaces):
                    if text_elem.text and text_elem.text.strip():
                        # Try to find a parent element with an id
                        parent_elem = text_elem
                        parent_id = None
                        
                        # Look up the tree for an element with an id
                        for _ in range(10):  # Limit the depth of search
                            parent_elem = parent_elem.getparent() if hasattr(parent_elem, 'getparent') else None
                            if parent_elem is None:
                                break
                                
                            if parent_elem.get('id'):
                                parent_id = parent_elem.get('id')
                                break
                        
                        # If we found a parent with an ID, use it to create a unique ID for this text
                        if parent_id:
                            xml_text_id = f"slide{slide_number}_xml_{parent_id}"
                            
                            # Only add if not already captured by python-pptx
                            if xml_text_id not in text_dict:
                                text_dict[xml_text_id] = text_elem.text.strip()
                                
                                # Add metadata for this XML text
                                element_meta = {
                                    "id": xml_text_id,
                                    "type": "xml_text",
                                    "parent_id": parent_id
                                }
                                slide_meta["elements"].append(element_meta)
        except:
            # If there's an error with the XML extraction, continue with what we have
            pass
        
        # Add this slide's metadata to the overall metadata
        slide_metadata.append(slide_meta)
    
    return text_dict, slide_metadata
