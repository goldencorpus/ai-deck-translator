"""
PPTX Extractor module for extracting text from PowerPoint presentations.

This module provides functionality for extracting text content from PowerPoint
presentations while preserving the structure and context of the content. It handles
various types of text elements including shapes, tables, SmartArt, and notes.

Public Functions:
    extract_text: Extract all text elements from a PowerPoint presentation
    extract_from_smartart: Extract text from SmartArt diagrams
"""

import os
import zipfile
import xml.etree.ElementTree as ET
from pptx import Presentation
import re
from ..utils.logging import get_logger
from ..utils.exceptions import ValidationError

# Set up logging
logger = get_logger(__name__)

# XML namespaces used in PPTX files
namespaces = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "dgm": "http://schemas.openxmlformats.org/drawingml/2006/diagram",
}


def extract_from_smartart(pptx_file, rels_path, rel_id):
    """
    Extract text from SmartArt diagrams that python-pptx cannot access directly.

    Args:
        pptx_file (str): Path to the PPTX file
        rels_path (str): Path to the relationships file within the PPTX
        rel_id (str): Relationship ID for the SmartArt

    Returns:
        list: List of text strings from the SmartArt

    Raises:
        ValidationError: If the file cannot be accessed or is invalid
    """
    texts = []

    try:
        with zipfile.ZipFile(pptx_file, "r") as zip_ref:
            # Find the target path from the relationship
            rels_content = zip_ref.read(rels_path).decode("utf-8")
            rels_root = ET.fromstring(rels_content)

            target_path = None
            for rel in rels_root.findall(
                './/Relationship[@Id="' + rel_id + '"]',
                {"": "http://schemas.openxmlformats.org/package/2006/relationships"},
            ):
                target_path = rel.get("Target")
                break

            if not target_path:
                return texts

            # Convert target path to full path within the PPTX
            if target_path.startswith("/"):
                diagram_path = target_path[1:]  # Remove leading slash
            else:
                # Handle relative paths
                base_path = os.path.dirname(rels_path)
                diagram_path = os.path.normpath(
                    os.path.join(base_path, "..", target_path)
                )

            # Extract text from the diagram
            try:
                diagram_content = zip_ref.read(diagram_path).decode("utf-8")
                diagram_root = ET.fromstring(diagram_content)

                # Extract text from various diagram elements
                for text_elem in diagram_root.findall(".//dgm:t", namespaces):
                    if text_elem.text and text_elem.text.strip():
                        texts.append(text_elem.text.strip())
            except Exception as e:
                logger.warning(f"Error extracting text from SmartArt: {e}")
                pass  # Skip if there's an error reading the diagram
    except Exception as e:
        logger.error(f"Error accessing PPTX file for SmartArt extraction: {e}")
        raise ValidationError(f"Failed to access PPTX file: {str(e)}")

    return texts


def extract_text(pptx_file):
    """
    Extract text from PowerPoint presentation with enhanced support for various text content types.

    This function extracts text from a PowerPoint presentation, including text in shapes,
    tables, SmartArt diagrams, and slide notes. It preserves the structure and context
    of the content to ensure accurate translation.

    Args:
        pptx_file (str): Path to the PPTX file

    Returns:
        tuple: A tuple containing two elements:
            - text_dict (dict): Dictionary mapping element IDs to text content
                Keys are unique identifiers for text elements
                Values are the text content of those elements
            - slide_metadata (list): List of dictionaries with slide information
                Each dictionary contains metadata about a slide, including:
                    - slide_number (int): The slide number (1-indexed)
                    - layout (str): The slide layout name
                    - elements (list): List of element metadata
                    - notes (str): Speaker notes for the slide, if available

    Raises:
        ValidationError: If the file cannot be accessed or is invalid

    Example:
        >>> text_dict, slide_metadata = extract_text("presentation.pptx")
        >>> print(f"Extracted {len(text_dict)} text elements from {len(slide_metadata)} slides")
    """
    if not os.path.exists(pptx_file):
        logger.error(f"PPTX file not found: {pptx_file}")
        raise ValidationError(f"PPTX file not found: {pptx_file}")

    text_dict = {}
    slide_metadata = []

    try:
        logger.info(f"Extracting text from PPTX file: {pptx_file}")

        # Standard python-pptx extraction
        prs = Presentation(pptx_file)

        # Extract presentation title if available
        if prs.core_properties.title:
            text_dict["presentation_title"] = prs.core_properties.title
            slide_metadata.append(
                {
                    "id": "presentation_title",
                    "type": "presentation_title",
                    "slide_number": 0,
                    "context": "Presentation Title",
                }
            )
            logger.debug(f"Extracted presentation title: {prs.core_properties.title}")

        # Process each slide
        for slide_idx, slide in enumerate(prs.slides):
            slide_number = slide_idx + 1
            slide_layout = (
                slide.slide_layout.name
                if hasattr(slide, "slide_layout")
                and hasattr(slide.slide_layout, "name")
                else "Unknown Layout"
            )

            logger.debug(f"Processing slide {slide_number} with layout: {slide_layout}")

            # Add slide metadata
            slide_meta = {
                "slide_number": slide_number,
                "layout": slide_layout,
                "elements": [],
                "notes": "",
            }

            # Extract text from shapes
            for shape_idx, shape in enumerate(slide.shapes):
                shape_id = f"slide{slide_number}_shape{shape_idx}"

                # Extract text from text frames
                if hasattr(shape, "text") and shape.text.strip():
                    shape_name = (
                        shape.name if hasattr(shape, "name") else "Unknown Shape"
                    )

                    # Multi-paragraph shapes (e.g. bullet lists) are extracted one
                    # paragraph per ID so each line is translated and written back
                    # independently. Translating the whole block as one string lets the
                    # model drop the line breaks, collapsing several bullets into one.
                    paragraphs = (
                        list(shape.text_frame.paragraphs)
                        if shape.has_text_frame
                        else []
                    )
                    nonempty = [
                        (idx, para)
                        for idx, para in enumerate(paragraphs)
                        if para.text.strip()
                    ]

                    if len(nonempty) > 1:
                        for para_idx, para in nonempty:
                            para_id = f"{shape_id}_p{para_idx}"
                            text_dict[para_id] = para.text
                            slide_meta["elements"].append(
                                {
                                    "id": para_id,
                                    "type": "shape_paragraph",
                                    "shape_type": shape_name,
                                    "parent_shape": shape_id,
                                    "paragraph_index": para_idx,
                                }
                            )
                    else:
                        text_dict[shape_id] = shape.text
                        slide_meta["elements"].append(
                            {
                                "id": shape_id,
                                "type": "shape",
                                "shape_type": shape_name,
                            }
                        )

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
                                    "parent_shape": shape_id,
                                }
                                slide_meta["elements"].append(element_meta)

            # Extract slide notes
            if slide.has_notes_slide and slide.notes_slide:
                notes_text = ""
                for notes_shape in slide.notes_slide.shapes:
                    if hasattr(notes_shape, "text") and notes_shape.text.strip():
                        notes_text += notes_shape.text.strip() + "\n"

                if notes_text:
                    notes_id = f"slide{slide_number}_notes"
                    text_dict[notes_id] = notes_text.strip()
                    slide_meta["notes"] = notes_text.strip()
                    logger.debug(f"Extracted notes for slide {slide_number}")

            # Deep XML extraction for elements that python-pptx might miss
            try:
                with zipfile.ZipFile(pptx_file, "r") as zip_ref:
                    # Get slide XML content
                    slide_path = f"ppt/slides/slide{slide_number}.xml"
                    slide_content = zip_ref.read(slide_path).decode("utf-8")
                    slide_root = ET.fromstring(slide_content)

                    # Get slide relationships
                    slide_rels_path = f"ppt/slides/_rels/slide{slide_number}.xml.rels"

                    # Extract SmartArt text
                    for rel_elem in slide_root.findall(
                        './/p:graphicFrame//a:graphicData[@uri="http://schemas.openxmlformats.org/drawingml/2006/diagram"]/../../../..',
                        namespaces,
                    ):
                        # Find the relationship ID for this SmartArt
                        rel_id = None
                        for elem in rel_elem.findall(".//a:blip", namespaces):
                            rel_id = elem.get(
                                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
                            )
                            break

                        if rel_id:
                            smartart_text = extract_from_smartart(
                                pptx_file, slide_rels_path, rel_id
                            )
                            if smartart_text:
                                smartart_id = f"slide{slide_number}_smartart_{rel_id}"
                                text_dict[smartart_id] = "\n".join(smartart_text)

                                # Add metadata for this SmartArt
                                element_meta = {
                                    "id": smartart_id,
                                    "type": "smartart",
                                    "rel_id": rel_id,
                                }
                                slide_meta["elements"].append(element_meta)

                    # Find all text in the slide, including those that might be missed by python-pptx
                    for text_elem in slide_root.findall(".//a:t", namespaces):
                        if text_elem.text and text_elem.text.strip():
                            # Try to find a parent element with an id
                            parent_elem = text_elem
                            parent_id = None

                            # Look up the tree for an element with an id
                            for _ in range(10):  # Limit the depth of search
                                parent_elem = (
                                    parent_elem.getparent()
                                    if hasattr(parent_elem, "getparent")
                                    else None
                                )
                                if parent_elem is None:
                                    break

                                if parent_elem.get("id"):
                                    parent_id = parent_elem.get("id")
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
                                        "parent_id": parent_id,
                                    }
                                    slide_meta["elements"].append(element_meta)

                    # Check for notes in the XML if not found by python-pptx
                    if not slide_meta["notes"]:
                        try:
                            notes_slide_path = (
                                f"ppt/notesSlides/notesSlide{slide_number}.xml"
                            )
                            if notes_slide_path in [
                                name for name in zip_ref.namelist()
                            ]:
                                notes_content = zip_ref.read(notes_slide_path).decode(
                                    "utf-8"
                                )
                                notes_root = ET.fromstring(notes_content)

                                notes_text = []
                                for text_elem in notes_root.findall(
                                    ".//a:t", namespaces
                                ):
                                    if text_elem.text and text_elem.text.strip():
                                        notes_text.append(text_elem.text.strip())

                                if notes_text:
                                    notes_id = f"slide{slide_number}_notes"
                                    text_dict[notes_id] = "\n".join(notes_text)
                                    slide_meta["notes"] = "\n".join(notes_text)
                                    logger.debug(
                                        f"Extracted notes from XML for slide {slide_number}"
                                    )
                        except Exception as e:
                            logger.warning(
                                f"Error extracting notes from XML for slide {slide_number}: {e}"
                            )
            except Exception as e:
                logger.warning(
                    f"Error during deep XML extraction for slide {slide_number}: {e}"
                )

            # Add this slide's metadata to the overall metadata
            slide_metadata.append(slide_meta)

        logger.info(
            f"Extracted {len(text_dict)} text elements from {len(slide_metadata)} slides"
        )
        return text_dict, slide_metadata
    except Exception as e:
        logger.error(f"Error extracting text from PPTX file: {e}")
        raise ValidationError(f"Failed to extract text from PPTX file: {str(e)}")
