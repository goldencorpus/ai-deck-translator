"""
Logging configuration for Google Slides Translator.

This module provides a centralized logging configuration for the application,
enabling consistent logging across all modules with configurable log levels.
"""

import os
import logging
import logging.handlers
import sys
from pathlib import Path


def setup_logging(log_level=logging.INFO, log_file=None, console=True):
    """
    Configure the logging system for the application.

    Args:
        log_level (int): The logging level (default: logging.INFO)
        log_file (str, optional): Path to log file. If None, logs will only go to console.
        console (bool): Whether to output logs to console (default: True)

    Returns:
        logging.Logger: Configured logger object
    """
    # Create logger
    logger = logging.getLogger("gslides_translator")
    logger.setLevel(log_level)
    logger.handlers = []  # Clear existing handlers to avoid duplicates

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Add console handler if requested
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Add file handler if log file specified
    if log_file:
        # Ensure log directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
            
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10485760, backupCount=5
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# Default logger
default_log_dir = os.path.join(str(Path.home()), ".gslides_translator", "logs")
os.makedirs(default_log_dir, exist_ok=True)
default_log_file = os.path.join(default_log_dir, "gslides_translator.log")

logger = setup_logging(
    log_level=os.environ.get("GSLIDES_LOG_LEVEL", logging.INFO),
    log_file=os.environ.get("GSLIDES_LOG_FILE", default_log_file),
    console=os.environ.get("GSLIDES_LOG_CONSOLE", "1") == "1"
) 