"""
PPTX adapter for AI Deck Translator.

This module provides an implementation of the DocumentAdapter interface
for PowerPoint (PPTX) files, handling text extraction and document updating.
"""

import os
import time
import shutil
from typing import Dict, List, Any, Tuple, Optional
from pptx import Presentation

from ..core.translation_interface import DocumentAdapter, TextElements, MetadataType


class PPTXAdapter(DocumentAdapter):
    """
    PowerPoint (PPTX) document adapter for the AI Deck Translator.

    This adapter handles extracting text from PPTX files and updating
    presentations with translated text.
    """

    def extract_text(self, document_id: str) -> Tuple[TextElements, MetadataType]:
        """
        Extract text elements and metadata from a PowerPoint presentation.

        Args:
            document_id: Path to the PPTX file

        Returns:
            tuple: (text_elements, metadata)
        """
        if not os.path.exists(document_id):
            raise FileNotFoundError(f"PPTX file not found: {document_id}")

        # Load the presentation
        prs = Presentation(document_id)

        # Extract text from slides
        text_elements = {}
        slide_metadata = []

        for slide_index, slide in enumerate(prs.slides):
            slide_number = slide_index + 1
            slide_content = []
            slide_notes = ""

            # Get slide notes if available
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame.text:
                slide_notes = slide.notes_slide.notes_text_frame.text.strip()
                text_elements[f"slide_{slide_number}_notes"] = slide_notes

            # Get slide title if available
            slide_title = ""
            for shape in slide.shapes:
                if (
                    shape.has_text_frame
                    and shape.text.strip()
                    and hasattr(shape, "is_title")
                    and shape.is_title
                ):
                    slide_title = shape.text.strip()
                    break

            # Process each shape in the slide
            for shape_index, shape in enumerate(slide.shapes):
                if not hasattr(shape, "text"):
                    continue

                text = shape.text.strip()
                if not text:
                    continue

                # Add text to our elements
                text_id = f"slide_{slide_number}_element_{shape_index}"
                text_elements[text_id] = text
                slide_content.append(text_id)

                # Handle tables separately
                if hasattr(shape, "has_table") and shape.has_table:
                    table = shape.table
                    for row_idx in range(len(table.rows)):
                        for col_idx in range(len(table.columns)):
                            cell = table.cell(row_idx, col_idx)
                            if cell.text.strip():
                                cell_id = f"{text_id}_r{row_idx}_c{col_idx}"
                                text_elements[cell_id] = cell.text.strip()
                                slide_content.append(cell_id)

            # Add slide metadata
            slide_metadata.append(
                {
                    "slide_number": slide_number,
                    "title": slide_title,
                    "content": slide_content,
                    "notes": slide_notes,
                    "layout": (
                        slide.slide_layout.name
                        if hasattr(slide, "slide_layout")
                        and hasattr(slide.slide_layout, "name")
                        else "Unknown"
                    ),
                }
            )

        return text_elements, slide_metadata

    def update_document(
        self, document_id: str, translated_elements: TextElements, target_language: str
    ) -> str:
        """
        Update a PowerPoint presentation with translated text.

        Args:
            document_id: Path to the PPTX file
            translated_elements: Dictionary of translated text elements
            target_language: Target language code

        Returns:
            str: Path to the updated PPTX file
        """
        if not os.path.exists(document_id):
            raise FileNotFoundError(f"PPTX file not found: {document_id}")

        # Create output file path with target language suffix
        file_dir = os.path.dirname(document_id)
        file_name = os.path.basename(document_id)
        name_parts = os.path.splitext(file_name)
        output_file = os.path.join(
            file_dir, f"{name_parts[0]}_{target_language}{name_parts[1]}"
        )

        # Make a copy of the original file
        shutil.copy2(document_id, output_file)

        # Load the presentation
        prs = Presentation(output_file)

        # Update slides with translated text
        for slide_index, slide in enumerate(prs.slides):
            slide_number = slide_index + 1

            # Update notes if available
            notes_id = f"slide_{slide_number}_notes"
            if notes_id in translated_elements and slide.has_notes_slide:
                slide.notes_slide.notes_text_frame.text = translated_elements[notes_id]

            # Update shapes
            for shape_index, shape in enumerate(slide.shapes):
                if not hasattr(shape, "text"):
                    continue

                text_id = f"slide_{slide_number}_element_{shape_index}"

                if text_id in translated_elements:
                    shape.text = translated_elements[text_id]

                # Update table cells if present
                if hasattr(shape, "has_table") and shape.has_table:
                    table = shape.table
                    for row_idx in range(len(table.rows)):
                        for col_idx in range(len(table.columns)):
                            cell = table.cell(row_idx, col_idx)
                            cell_id = f"{text_id}_r{row_idx}_c{col_idx}"

                            if cell_id in translated_elements:
                                cell.text = translated_elements[cell_id]

        # Save the presentation
        prs.save(output_file)

        return output_file
