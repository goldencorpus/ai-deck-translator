"""
PPTX Updater module for updating PowerPoint presentations with translated text.

This module provides functionality for creating a copy of a PowerPoint presentation
and updating it with translated text. It handles various types of text elements including
shapes, tables, SmartArt, and notes, ensuring that formatting and layout are preserved.

Public Functions:
    update_slides: Update a PowerPoint presentation with translated text
    update_xml_elements: Update XML elements in a PowerPoint presentation
"""

import os
import zipfile
import xml.etree.ElementTree as ET
from pptx import Presentation
import re
import shutil
from ..utils.logging import get_logger
from ..utils.exceptions import ValidationError, PresentationError

# Set up logging
logger = get_logger(__name__)

# XML namespaces used in PPTX files
namespaces = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "dgm": "http://schemas.openxmlformats.org/drawingml/2006/diagram",
}


def update_slides(pptx_file, output_file, translated_texts):
    """
    Update PowerPoint presentation with translated text.

    This function creates a copy of the original PowerPoint file and updates all text
    elements with their translated versions. It preserves formatting, layout, and non-text
    elements. The new presentation is saved to the specified output file.

    Args:
        pptx_file (str): Path to the original PPTX file
        output_file (str): Path to save the updated PPTX file
        translated_texts (dict): Dictionary mapping element IDs to translated text
            Keys should match the element IDs from extract_text()
            Values should be the translated text for each element

    Returns:
        bool: True if successful, False otherwise

    Raises:
        ValidationError: If the input file cannot be accessed or is invalid
        PresentationError: If there are issues updating the presentation

    Example:
        >>> success = update_slides("presentation.pptx", "presentation_ja.pptx",
        ...                        {"slide1_shape1": "Translated text 1"})
        >>> if success:
        ...     print(f"Translation saved to presentation_ja.pptx")
    """
    if not os.path.exists(pptx_file):
        logger.error(f"PPTX file not found: {pptx_file}")
        raise ValidationError(f"PPTX file not found: {pptx_file}")

    try:
        logger.info(f"Updating PPTX file: {pptx_file} -> {output_file}")

        # Create a copy of the presentation
        prs = Presentation(pptx_file)

        # Update presentation title if available
        if "presentation_title" in translated_texts and hasattr(
            prs.core_properties, "title"
        ):
            prs.core_properties.title = translated_texts["presentation_title"]
            logger.debug(
                f"Updated presentation title: {translated_texts['presentation_title']}"
            )

        # Process each slide
        for slide_idx, slide in enumerate(prs.slides):
            slide_number = slide_idx + 1
            logger.debug(f"Updating slide {slide_number}")

            # Update text in shapes
            for shape_idx, shape in enumerate(slide.shapes):
                shape_id = f"slide{slide_number}_shape{shape_idx}"

                # Update text in text frames
                if (
                    hasattr(shape, "text")
                    and shape.text.strip()
                    and shape_id in translated_texts
                ):
                    # Replace text while preserving paragraph formatting
                    if (
                        hasattr(shape, "text_frame")
                        and shape.text != translated_texts[shape_id]
                    ):
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
                            translated_lines = translated_texts[shape_id].split("\n")

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
                                for i in range(
                                    len(existing_paragraphs), len(translated_lines)
                                ):
                                    p = shape.text_frame.add_paragraph()
                                    p.text = translated_lines[i]

                        logger.debug(f"Updated text in shape {shape_id}")

                # Update text in tables
                if shape.has_table:
                    for row_idx, row in enumerate(shape.table.rows):
                        for col_idx, cell in enumerate(row.cells):
                            cell_id = f"{shape_id}_table_r{row_idx}c{col_idx}"
                            if cell_id in translated_texts:
                                # Update cell text
                                cell.text = translated_texts[cell_id]
                                logger.debug(f"Updated text in table cell {cell_id}")

            # Update slide notes
            notes_id = f"slide{slide_number}_notes"
            if (
                notes_id in translated_texts
                and slide.has_notes_slide
                and slide.notes_slide
            ):
                # Find the notes text shape
                for notes_shape in slide.notes_slide.shapes:
                    if hasattr(notes_shape, "text") and notes_shape.text.strip():
                        # Replace the notes text. The TextFrame.text setter safely
                        # replaces all paragraphs in one step; the previous manual
                        # paragraph-removal loop spun forever because python-pptx always
                        # keeps a paragraph element present, so the count never hit 0.
                        if hasattr(notes_shape, "text_frame"):
                            notes_shape.text_frame.text = translated_texts[notes_id]
                            logger.debug(f"Updated notes for slide {slide_number}")
                            break

        # Save the updated presentation
        try:
            logger.info(f"Saving updated presentation to {output_file}")
            prs.save(output_file)

            # Now handle XML-level updates for elements that python-pptx can't update directly
            update_xml_elements(pptx_file, output_file, translated_texts)

            logger.info("Successfully updated presentation")
            return True
        except Exception as e:
            logger.error(f"Error saving presentation: {e}")
            raise PresentationError(f"Failed to save presentation: {str(e)}")
    except Exception as e:
        logger.error(f"Error updating presentation: {e}")
        if isinstance(e, (ValidationError, PresentationError)):
            raise
        else:
            raise PresentationError(f"Error updating presentation: {str(e)}")


def update_xml_elements(original_file, updated_file, translated_texts):
    """
    Update XML elements in the PPTX file that python-pptx can't handle directly.

    This function extracts the PPTX file (which is a ZIP archive), modifies the XML
    content directly, and then repackages it. This is necessary for elements that
    the python-pptx library doesn't provide direct access to, such as SmartArt.

    Args:
        original_file (str): Path to the original PPTX file
        updated_file (str): Path to the updated PPTX file
        translated_texts (dict): Dictionary mapping element IDs to translated text

    Raises:
        PresentationError: If there are issues updating the XML elements
    """
    # Create temporary directory for extraction
    temp_dir = os.path.join(os.path.dirname(updated_file), "_temp_pptx_update")
    os.makedirs(temp_dir, exist_ok=True)

    try:
        logger.info("Performing XML-level updates")

        # Extract the updated file
        with zipfile.ZipFile(updated_file, "r") as zip_ref:
            zip_ref.extractall(temp_dir)

        # Process each slide
        slide_files = [
            f
            for f in os.listdir(os.path.join(temp_dir, "ppt", "slides"))
            if f.startswith("slide") and f.endswith(".xml")
        ]

        for slide_file in slide_files:
            slide_number = int(re.search(r"slide(\d+)\.xml", slide_file).group(1))
            slide_path = os.path.join(temp_dir, "ppt", "slides", slide_file)

            logger.debug(f"Processing XML for slide {slide_number}")

            # Parse the slide XML
            tree = ET.parse(slide_path)
            root = tree.getroot()

            # Update SmartArt text
            smartart_ids = [
                key
                for key in translated_texts.keys()
                if key.startswith(f"slide{slide_number}_smartart_")
            ]
            if smartart_ids:
                logger.debug(
                    f"Found {len(smartart_ids)} SmartArt elements to update in slide {slide_number}"
                )

                # Get slide relationships
                slide_rels_path = os.path.join(
                    temp_dir, "ppt", "slides", "_rels", f"{slide_file}.rels"
                )

                if os.path.exists(slide_rels_path):
                    for smartart_id in smartart_ids:
                        rel_id = smartart_id.split("_")[-1]

                        # Find the target diagram in relationships
                        rels_tree = ET.parse(slide_rels_path)
                        rels_root = rels_tree.getroot()

                        target_path = None
                        for rel in rels_root.findall(
                            './/Relationship[@Id="' + rel_id + '"]',
                            {
                                "": "http://schemas.openxmlformats.org/package/2006/relationships"
                            },
                        ):
                            target_path = rel.get("Target")
                            break

                        if target_path:
                            # Convert target path to full path
                            if target_path.startswith("/"):
                                diagram_path = os.path.join(temp_dir, target_path[1:])
                            else:
                                base_path = os.path.dirname(slide_rels_path)
                                diagram_path = os.path.normpath(
                                    os.path.join(base_path, "..", target_path)
                                )

                            # Update the diagram if it exists
                            if os.path.exists(diagram_path):
                                try:
                                    # Parse the diagram XML
                                    diagram_tree = ET.parse(diagram_path)
                                    diagram_root = diagram_tree.getroot()

                                    # Split the translated text into lines
                                    translated_lines = translated_texts[
                                        smartart_id
                                    ].split("\n")

                                    # Update text elements in the diagram
                                    text_elements = diagram_root.findall(
                                        ".//dgm:t", namespaces
                                    )
                                    for i, text_elem in enumerate(text_elements):
                                        if i < len(translated_lines):
                                            text_elem.text = translated_lines[i]

                                    # Save the updated diagram
                                    diagram_tree.write(
                                        diagram_path,
                                        encoding="utf-8",
                                        xml_declaration=True,
                                    )
                                    logger.debug(
                                        f"Updated SmartArt diagram for {smartart_id}"
                                    )
                                except Exception as e:
                                    logger.warning(
                                        f"Error updating SmartArt diagram: {e}"
                                    )

            # Update XML text elements
            xml_text_ids = [
                key
                for key in translated_texts.keys()
                if key.startswith(f"slide{slide_number}_xml_")
            ]
            if xml_text_ids:
                logger.debug(
                    f"Found {len(xml_text_ids)} XML text elements to update in slide {slide_number}"
                )

                for xml_text_id in xml_text_ids:
                    parent_id = xml_text_id.split("_")[-1]

                    # Find elements with this ID
                    for elem in root.findall(f'.//*[@id="{parent_id}"]'):
                        # Find all text elements within this parent
                        text_elements = elem.findall(".//a:t", namespaces)

                        # If there's only one text element, update it directly
                        if len(text_elements) == 1:
                            text_elements[0].text = translated_texts[xml_text_id]
                        elif len(text_elements) > 1:
                            # For multiple text elements, try to split the translation
                            translated_parts = translated_texts[xml_text_id].split("\n")

                            # Update as many elements as we have parts
                            for i, text_elem in enumerate(text_elements):
                                if i < len(translated_parts):
                                    text_elem.text = translated_parts[i]

            # Update slide notes in XML if needed
            notes_id = f"slide{slide_number}_notes"
            if notes_id in translated_texts:
                # Check if there's a notes slide XML file
                notes_slide_path = os.path.join(
                    temp_dir, "ppt", "notesSlides", f"notesSlide{slide_number}.xml"
                )
                if os.path.exists(notes_slide_path):
                    try:
                        # Parse the notes slide XML
                        notes_tree = ET.parse(notes_slide_path)
                        notes_root = notes_tree.getroot()

                        # Find all text elements in the notes slide
                        text_elements = notes_root.findall(".//a:t", namespaces)

                        # Split the translated notes into lines
                        translated_lines = translated_texts[notes_id].split("\n")

                        # Update the text elements
                        if len(text_elements) == 1:
                            text_elements[0].text = translated_texts[notes_id]
                        elif len(text_elements) > 1:
                            # For multiple text elements, try to match the structure
                            for i, text_elem in enumerate(text_elements):
                                if i < len(translated_lines):
                                    text_elem.text = translated_lines[i]
                                else:
                                    text_elem.text = ""

                        # Save the updated notes slide
                        notes_tree.write(
                            notes_slide_path, encoding="utf-8", xml_declaration=True
                        )
                        logger.debug(
                            f"Updated notes slide XML for slide {slide_number}"
                        )
                    except Exception as e:
                        logger.warning(f"Error updating notes slide XML: {e}")

            # Save the updated slide
            tree.write(slide_path, encoding="utf-8", xml_declaration=True)

        # Recreate the PPTX file
        with zipfile.ZipFile(updated_file, "w") as zip_ref:
            for root_dir, _, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root_dir, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    zip_ref.write(file_path, arcname)

        logger.info("XML-level updates completed successfully")
    except Exception as e:
        logger.error(f"Error updating XML elements: {e}")
        raise PresentationError(f"Failed to update XML elements: {str(e)}")
    finally:
        # Clean up temporary directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logger.debug("Cleaned up temporary directory")
