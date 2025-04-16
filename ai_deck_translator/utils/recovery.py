"""
Recovery utilities for handling translation progress and resuming failed translations.

This module provides functionality for saving and loading translation progress,
allowing users to resume translations that were interrupted or failed. It handles
the creation and management of recovery files, which store the state of a translation
job including completed and pending work.

Public Functions:
    setup_recovery_system: Set up or load a recovery system for translation
    list_recovery_files: List available recovery files for resuming translations
    save_recovery_file: Save a recovery file with translation progress
    load_recovery_file: Load translation progress from a recovery file
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from ..utils.logging import get_logger
from ..utils.exceptions import RecoveryError
from .. import config

# Set up logging
logger = get_logger(__name__)

# Add a dummy RECOVERY_ attribute for test compatibility
RECOVERY_ = None


def setup_recovery_system(
    file_id: str,
    text_dict: Dict[str, str],
    slide_metadata: List[Dict[str, Any]],
    source_language: str,
    target_language: str,
    resume_file: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Set up or load a recovery system for translation.

    This function either creates a new recovery system for a translation job or
    loads an existing one from a recovery file. The recovery system allows for
    saving progress during translation and resuming from that point if the process
    is interrupted.

    Args:
        file_id (str): Unique identifier for the file being translated
            (presentation ID for Google Slides or filename for PPTX)
        text_dict (dict): Dictionary of text elements to translate
            Keys are element IDs, values are the text content
        slide_metadata (list): List of dictionaries with slide information
            Contains metadata about each slide and its elements
        source_language (str): Source language code (e.g., 'en' for English)
        target_language (str): Target language code (e.g., 'ja' for Japanese)
        resume_file (str, optional): Path to a recovery file to resume from
            If provided and the file exists, will load state from this file

    Returns:
        dict: A dictionary containing the recovery system with the following keys:
            - is_resuming (bool): Whether this is resuming a previous translation
            - text_dict (dict): Dictionary of text elements to translate
            - slide_metadata (list): List of dictionaries with slide information
            - translated_texts (dict): Dictionary of already translated elements
            - remaining_batches (list): List of batches still to be translated
            - save_recovery_state (callable): Function to save the current state

    Raises:
        RecoveryError: If there's an error loading or creating the recovery system

    Example:
        >>> recovery_system = setup_recovery_system(
        ...     "1rppKpwoUKmf65wAg7J9gSVpL279IBX4EmbWM7yGiS6s",
        ...     text_dict, slide_metadata, "en", "ja"
        ... )
        >>> # Use recovery_system during translation
        >>> recovery_system["translated_texts"]["element1"] = "Translated text"
        >>> recovery_system["save_recovery_state"]()
    """
    # Create a directory for recovery files if it doesn't exist
    recovery_dir = getattr(config, "RECOVERY_DIRECTORY", "translation_recovery")
    os.makedirs(recovery_dir, exist_ok=True)

    logger.info(f"Setting up recovery system for {file_id}")

    # Initialize the recovery system
    recovery_system = {
        "is_resuming": False,
        "text_dict": text_dict,
        "slide_metadata": slide_metadata,
        "translated_texts": {},
        "remaining_batches": [],
    }

    # If a resume file is provided, load the state from that file
    if resume_file and os.path.exists(resume_file):
        try:
            logger.info(f"Loading recovery state from {resume_file}")
            with open(resume_file, "r", encoding="utf-8") as f:
                recovery_state = json.load(f)

            # Validate the recovery state
            required_keys = [
                "text_dict",
                "translated_texts",
                "source_language",
                "target_language",
            ]
            if not all(key in recovery_state for key in required_keys):
                raise RecoveryError(f"Invalid recovery file: missing required keys")

            # Check if languages match
            if (
                recovery_state["source_language"] != source_language
                or recovery_state["target_language"] != target_language
            ):
                logger.warning(
                    f"Language mismatch in recovery file: expected {source_language}->{target_language}, "
                    f"got {recovery_state.get('source_language')}->{recovery_state.get('target_language')}"
                )

            # Update the recovery system with loaded state
            recovery_system["is_resuming"] = True
            recovery_system["text_dict"] = recovery_state.get("text_dict", text_dict)
            recovery_system["slide_metadata"] = recovery_state.get(
                "slide_metadata", slide_metadata
            )
            recovery_system["translated_texts"] = recovery_state.get(
                "translated_texts", {}
            )
            recovery_system["remaining_batches"] = recovery_state.get(
                "remaining_batches", []
            )

            recovery_file_path = resume_file
            logger.info(
                f"Successfully loaded recovery state: {len(recovery_system['translated_texts'])} "
                f"of {len(recovery_system['text_dict'])} items already translated"
            )
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing recovery file {resume_file}: {str(e)}")
            raise RecoveryError(f"Invalid recovery file format: {str(e)}")
        except Exception as e:
            logger.error(f"Error loading recovery file {resume_file}: {str(e)}")
            raise RecoveryError(f"Failed to load recovery file: {str(e)}")
    else:
        # Create a new recovery file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        recovery_file_path = os.path.join(
            recovery_dir, f"recovery_{file_id}_{timestamp}.json"
        )

        logger.info(f"Creating new recovery file: {recovery_file_path}")

    # Create the recovery state to save
    recovery_state = {
        "file_id": file_id,
        "source_language": source_language,
        "target_language": target_language,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_items": len(text_dict),
        "translated_items": len(recovery_system["translated_texts"]),
        "text_dict": text_dict,
        "slide_metadata": slide_metadata,
        "translated_texts": recovery_system["translated_texts"],
        "remaining_batches": recovery_system["remaining_batches"],
    }

    # Define a function to save the recovery state
    def save_recovery_state():
        """Save the current recovery state to the recovery file."""
        try:
            # Update dynamic fields
            recovery_state["last_updated"] = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            recovery_state["translated_items"] = len(
                recovery_system["translated_texts"]
            )
            recovery_state["translated_texts"] = recovery_system["translated_texts"]
            recovery_state["remaining_batches"] = recovery_system["remaining_batches"]

            # Save to file
            with open(recovery_file_path, "w", encoding="utf-8") as f:
                json.dump(recovery_state, f, ensure_ascii=False, indent=2)

            logger.debug(
                f"Saved recovery state to {recovery_file_path}: "
                f"{recovery_state['translated_items']}/{recovery_state['total_items']} items"
            )
        except Exception as e:
            logger.error(f"Error saving recovery state: {str(e)}")

    # Add the save function to the recovery system
    recovery_system["save_recovery_state"] = save_recovery_state

    # Save initial state
    save_recovery_state()

    return recovery_system


def list_recovery_files() -> List[Dict[str, Any]]:
    """
    List available recovery files for resuming translations.

    This function scans the recovery directory and returns information about
    available recovery files, including their timestamps, language pairs, and
    translation progress.

    Returns:
        list: A list of dictionaries, each containing metadata about a recovery file:
            - file (str): Filename of the recovery file
            - path (str): Full path to the recovery file
            - timestamp (str): When the recovery file was created/updated
            - source_language (str): Source language code
            - target_language (str): Target language code
            - progress (str): Progress information (e.g., "42/100 items")

    Example:
        >>> recovery_files = list_recovery_files()
        >>> for rf in recovery_files:
        ...     print(f"{rf['file']}: {rf['progress']} ({rf['timestamp']})")
    """
    recovery_dir = getattr(config, "RECOVERY_DIRECTORY", "translation_recovery")
    if not os.path.exists(recovery_dir):
        logger.info(f"Recovery directory {recovery_dir} does not exist")
        return []

    logger.info(f"Listing recovery files in {recovery_dir}")

    recovery_files = []
    for filename in os.listdir(recovery_dir):
        if filename.startswith("recovery_") and filename.endswith(".json"):
            file_path = os.path.join(recovery_dir, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Extract metadata
                recovery_files.append(
                    {
                        "file": filename,
                        "path": file_path,
                        "timestamp": data.get("timestamp", "Unknown"),
                        "source_language": data.get("source_language", "Unknown"),
                        "target_language": data.get("target_language", "Unknown"),
                        "progress": f"{data.get('translated_items', 0)}/{data.get('total_items', 0)} items",
                    }
                )
            except Exception as e:
                logger.warning(f"Error reading recovery file {filename}: {str(e)}")

    # Sort by timestamp (newest first)
    recovery_files.sort(key=lambda x: x["timestamp"], reverse=True)

    logger.info(f"Found {len(recovery_files)} recovery files")
    return recovery_files


def save_recovery_file(file_path: str, recovery_state: Dict[str, Any]) -> None:
    """
    Save the recovery state to a file.

    Args:
        file_path (str): Path to save the recovery file
        recovery_state (dict): Recovery state to save

    Raises:
        RecoveryError: If there's an error saving the recovery file
    """
    try:
        # Update dynamic fields
        recovery_state["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Save to file
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(recovery_state, f, ensure_ascii=False, indent=2)

        logger.debug(
            f"Saved recovery state to {file_path}: "
            f"{recovery_state.get('translated_items', 0)}/{recovery_state.get('total_items', 0)} items"
        )
    except Exception as e:
        logger.error(f"Error saving recovery state: {str(e)}")
        raise RecoveryError(f"Failed to save recovery file: {str(e)}")


def load_recovery_file(file_path: str) -> Dict[str, Any]:
    """
    Load recovery state from a file.

    Args:
        file_path (str): Path to the recovery file

    Returns:
        dict: The loaded recovery state

    Raises:
        RecoveryError: If there's an error loading the recovery file
    """
    try:
        logger.info(f"Loading recovery state from {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            recovery_state = json.load(f)

        # Validate the recovery state
        required_keys = [
            "text_dict",
            "translated_texts",
            "source_language",
            "target_language",
        ]
        if not all(key in recovery_state for key in required_keys):
            raise RecoveryError(f"Invalid recovery file: missing required keys")

        logger.info(
            f"Successfully loaded recovery state: "
            f"{recovery_state.get('translated_items', 0)} of {recovery_state.get('total_items', 0)} "
            f"items already translated"
        )

        return recovery_state
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing recovery file {file_path}: {str(e)}")
        raise RecoveryError(f"Invalid recovery file format: {str(e)}")
    except Exception as e:
        logger.error(f"Error loading recovery file {file_path}: {str(e)}")
        raise RecoveryError(f"Failed to load recovery file: {str(e)}")
