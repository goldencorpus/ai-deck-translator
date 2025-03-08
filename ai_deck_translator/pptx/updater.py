"""
PPTX Updater module for updating PowerPoint presentations with translated text.
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

def update_slides(pptx_file, output_file, translated_texts):
    """
    Update PowerPoint presentation with translated text.
    
    Args:
        pptx_file: Path to the original PPTX file
        output_file: Path to save the updated PPTX file
        translated_texts: Dictionary of translated text elements with IDs
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Create a copy of the presentation
    prs = Presentation(pptx_file)
    
    # Update presentation title if available
    if "presentation_title" in translated_texts and hasattr(prs.core_properties, 'title'):
        prs.core_properties.title = translated_texts["presentation_title"]
    
    # Process each slide
    for slide_idx, slide in enumerate(prs.slides):
        slide_number = slide_idx + 1
        
        # Update text in shapes
        for shape_idx, shape in enumerate(slide.shapes):
            shape_id = f"slide{slide_number}_shape{shape_idx}"
            
            # Update text in text frames
            if hasattr(shape, "text") and shape.text.strip() and shape_id in translated_texts:
                # Replace text while preserving paragraph formatting
                if hasattr(shape, "text_frame") and shape.text != translated_texts[shape_id]:
                    # Clear existing paragraphs
                    existing_paragraphs = list(shape.text_frame.paragraphs)
                    
                    # If there's only one paragraph, simply update the text
                    if len(existing_paragraphs) == 1:
                        p = existing_paragraphs[0]
                        if p.runs:
                            p.runs[0].text = translated_texts[shape_id]
                        else:
                            p.text = translated_texts[shape_id]
                    else:
                        # For multiple paragraphs, try to match the structure
                        translated_lines = translated_texts[shape_id].split('\n')
                        
                        # Update existing paragraphs
                        for i, p in enumerate(existing_paragraphs):
                            if i < len(translated_lines):
                                if p.runs:
                                    p.runs[0].text = translated_lines[i]
                                else:
                                    p.text = translated_lines[i]
                            else:
                                # Clear extra paragraphs
                                if p.runs:
                                    p.runs[0].text = ""
                                else:
                                    p.text = ""
                        
                        # Add any additional paragraphs if needed
                        if len(translated_lines) > len(existing_paragraphs):
                            for i in range(len(existing_paragraphs), len(translated_lines)):
                                p = shape.text_frame.add_paragraph()
                                p.text = translated_lines[i]
            
            # Update text in tables
            if shape.has_table:
                for row_idx, row in enumerate(shape.table.rows):
                    for col_idx, cell in enumerate(row.cells):
                        cell_id = f"{shape_id}_table_r{row_idx}c{col_idx}"
                        if cell_id in translated_texts:
                            # Update cell text
                            cell.text = translated_texts[cell_id]
    
    # Save the updated presentation
    try:
        prs.save(output_file)
        
        # Now handle XML-level updates for elements that python-pptx can't update directly
        update_xml_elements(pptx_file, output_file, translated_texts)
        
        return True
    except Exception as e:
        print(f"Error saving presentation: {e}")
        return False

def update_xml_elements(original_file, updated_file, translated_texts):
    """
    Update XML elements in the PPTX file that python-pptx can't handle directly.
    
    Args:
        original_file: Path to the original PPTX file
        updated_file: Path to the updated PPTX file
        translated_texts: Dictionary of translated text elements with IDs
    """
    # Create temporary directory for extraction
    temp_dir = os.path.join(os.path.dirname(updated_file), "_temp_pptx_update")
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Extract the updated file
        with zipfile.ZipFile(updated_file, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Process each slide
        slide_files = [f for f in os.listdir(os.path.join(temp_dir, "ppt", "slides")) if f.startswith("slide") and f.endswith(".xml")]
        
        for slide_file in slide_files:
            slide_number = int(re.search(r'slide(\d+)\.xml', slide_file).group(1))
            slide_path = os.path.join(temp_dir, "ppt", "slides", slide_file)
            
            # Parse the slide XML
            tree = ET.parse(slide_path)
            root = tree.getroot()
            
            # Update SmartArt text
            smartart_ids = [key for key in translated_texts.keys() if key.startswith(f"slide{slide_number}_smartart_")]
            if smartart_ids:
                # Get slide relationships
                slide_rels_path = os.path.join(temp_dir, "ppt", "slides", "_rels", f"{slide_file}.rels")
                
                if os.path.exists(slide_rels_path):
                    for smartart_id in smartart_ids:
                        rel_id = smartart_id.split("_")[-1]
                        
                        # Find the target diagram in relationships
                        rels_tree = ET.parse(slide_rels_path)
                        rels_root = rels_tree.getroot()
                        
                        target_path = None
                        for rel in rels_root.findall('.//Relationship[@Id="' + rel_id + '"]', {'': 'http://schemas.openxmlformats.org/package/2006/relationships'}):
                            target_path = rel.get('Target')
                            break
                        
                        if target_path:
                            # Convert target path to full path
                            if target_path.startswith('/'):
                                diagram_path = os.path.join(temp_dir, target_path[1:])
                            else:
                                base_path = os.path.dirname(slide_rels_path)
                                diagram_path = os.path.normpath(os.path.join(base_path, '..', target_path))
                            
                            # Update the diagram if it exists
                            if os.path.exists(diagram_path):
                                try:
                                    # Parse the diagram XML
                                    diagram_tree = ET.parse(diagram_path)
                                    diagram_root = diagram_tree.getroot()
                                    
                                    # Split the translated text into lines
                                    translated_lines = translated_texts[smartart_id].split('\n')
                                    
                                    # Update text elements in the diagram
                                    text_elements = diagram_root.findall('.//dgm:t', namespaces)
                                    for i, text_elem in enumerate(text_elements):
                                        if i < len(translated_lines):
                                            text_elem.text = translated_lines[i]
                                    
                                    # Save the updated diagram
                                    diagram_tree.write(diagram_path, encoding='utf-8', xml_declaration=True)
                                except:
                                    pass  # Skip if there's an error updating the diagram
            
            # Update XML text elements
            xml_text_ids = [key for key in translated_texts.keys() if key.startswith(f"slide{slide_number}_xml_")]
            if xml_text_ids:
                for xml_text_id in xml_text_ids:
                    parent_id = xml_text_id.split("_")[-1]
                    
                    # Find elements with this ID
                    for elem in root.findall(f'.//*[@id="{parent_id}"]'):
                        # Find all text elements within this parent
                        text_elements = elem.findall('.//a:t', namespaces)
                        
                        # If there's only one text element, update it directly
                        if len(text_elements) == 1:
                            text_elements[0].text = translated_texts[xml_text_id]
                        elif len(text_elements) > 1:
                            # For multiple text elements, try to split the translation
                            translated_parts = translated_texts[xml_text_id].split('\n')
                            
                            # Update as many elements as we have parts
                            for i, text_elem in enumerate(text_elements):
                                if i < len(translated_parts):
                                    text_elem.text = translated_parts[i]
            
            # Save the updated slide
            tree.write(slide_path, encoding='utf-8', xml_declaration=True)
        
        # Recreate the PPTX file
        with zipfile.ZipFile(updated_file, 'w') as zip_ref:
            for root_dir, _, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root_dir, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    zip_ref.write(file_path, arcname)
    
    except Exception as e:
        print(f"Error updating XML elements: {e}")
    
    finally:
        # Clean up temporary directory
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
