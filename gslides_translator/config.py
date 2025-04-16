"""
Configuration module for Google Slides Translator.

This module manages configuration settings and environment variables
used throughout the application, with validation and defaults.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

# Load dotenv before any imports that might use environment variables
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # dotenv is optional

from gslides_translator.utils.exceptions import ConfigurationError
from gslides_translator.utils.logging import logger

# Default paths
CONFIG_DIR = os.path.join(str(Path.home()), ".gslides_translator")
CREDENTIALS_PATH = os.path.join(CONFIG_DIR, "credentials.json")
TOKEN_PATH = os.path.join(CONFIG_DIR, "token.json")

# Required environment variables
REQUIRED_ENV_VARS = ["CLAUDE_API_KEY"]

# Default configuration
DEFAULT_CONFIG = {
    "presentation": {
        "create_copy": True,
        "copy_title_suffix": " (Translated)",
        "open_browser": True,
    },
    "translation": {
        "batch_size": 10,
        "max_tokens": 100000,
        "model": "claude-3-opus-20240229",
    },
    "api": {
        "anthropic_api_base": "https://api.anthropic.com",
        "anthropic_version": "2023-06-01",
    },
    "web": {
        "host": "127.0.0.1",
        "port": 5000,
        "debug": False,
    },
}


def validate_config(config: Dict[str, Any]) -> bool:
    """
    Validate that the configuration contains all required fields.

    Args:
        config (Dict[str, Any]): Configuration dictionary to validate

    Returns:
        bool: True if valid, raises ConfigurationError otherwise

    Raises:
        ConfigurationError: If configuration is invalid
    """
    # Check for required top-level keys
    required_sections = ["presentation", "translation", "api", "web"]
    for section in required_sections:
        if section not in config:
            raise ConfigurationError(
                f"Missing required configuration section: {section}"
            )

    # Check for required nested keys
    if "create_copy" not in config["presentation"]:
        raise ConfigurationError("Missing 'create_copy' in presentation config")

    if "model" not in config["translation"]:
        raise ConfigurationError("Missing 'model' in translation config")

    if "anthropic_api_base" not in config["api"]:
        raise ConfigurationError("Missing 'anthropic_api_base' in API config")

    if "host" not in config["web"] or "port" not in config["web"]:
        raise ConfigurationError("Missing 'host' or 'port' in web config")

    return True


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from file or use defaults.

    Args:
        config_path (str, optional): Path to configuration file

    Returns:
        Dict[str, Any]: Configuration dictionary

    Raises:
        ConfigurationError: If configuration file cannot be loaded or is invalid
    """
    config = DEFAULT_CONFIG.copy()

    # If config_path is provided, load from file
    if config_path:
        try:
            with open(config_path, "r") as f:
                file_config = json.load(f)
                # Deep merge with defaults
                for section, values in file_config.items():
                    if section in config and isinstance(config[section], dict):
                        config[section].update(values)
                    else:
                        config[section] = values
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load configuration file: {e}")
            raise ConfigurationError(
                f"Could not load config from {config_path}: {str(e)}"
            )

    # Validate loaded config
    validate_config(config)

    return config


def save_config(config: Dict[str, Any], config_path: str) -> None:
    """
    Save configuration to file.

    Args:
        config (Dict[str, Any]): Configuration to save
        config_path (str): Path to save configuration to

    Raises:
        ConfigurationError: If configuration cannot be saved
    """
    # Ensure directory exists
    os.makedirs(os.path.dirname(config_path), exist_ok=True)

    try:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
    except IOError as e:
        logger.error(f"Failed to save configuration: {e}")
        raise ConfigurationError(f"Could not save config to {config_path}: {str(e)}")


def check_environment() -> None:
    """
    Check that all required environment variables are set.

    Raises:
        ConfigurationError: If any required variables are missing
    """
    missing_vars = [var for var in REQUIRED_ENV_VARS if not os.environ.get(var)]
    if missing_vars:
        missing_list = ", ".join(missing_vars)
        logger.error(f"Missing required environment variables: {missing_list}")
        raise ConfigurationError(
            f"Missing required environment variables: {missing_list}. "
            f"Please set these variables before running the application."
        )


def get_config() -> Dict[str, Any]:
    """
    Get the application configuration.

    This is the main function to use when getting configuration.

    Returns:
        Dict[str, Any]: Complete configuration with defaults and environment overrides

    Raises:
        ConfigurationError: If configuration is invalid
    """
    # Check environment variables
    check_environment()

    # Set up config directory
    os.makedirs(CONFIG_DIR, exist_ok=True)

    # Default config path
    default_config_path = os.path.join(CONFIG_DIR, "config.json")

    # Use environment variable for config path if available
    config_path = os.environ.get("GSLIDES_CONFIG_PATH", default_config_path)

    # Try to load from path, falling back to defaults if file doesn't exist
    try:
        if os.path.exists(config_path):
            config = load_config(config_path)
        else:
            logger.info(f"No configuration file found at {config_path}, using defaults")
            config = DEFAULT_CONFIG.copy()
    except ConfigurationError:
        logger.warning("Error loading configuration, falling back to defaults")
        config = DEFAULT_CONFIG.copy()

    # Apply environment variable overrides
    if os.environ.get("GSLIDES_CREATE_COPY"):
        config["presentation"]["create_copy"] = (
            os.environ.get("GSLIDES_CREATE_COPY").lower() == "true"
        )

    if os.environ.get("GSLIDES_OPEN_BROWSER"):
        config["presentation"]["open_browser"] = (
            os.environ.get("GSLIDES_OPEN_BROWSER").lower() == "true"
        )

    if os.environ.get("GSLIDES_MODEL"):
        config["translation"]["model"] = os.environ.get("GSLIDES_MODEL")

    if os.environ.get("GSLIDES_WEB_HOST"):
        config["web"]["host"] = os.environ.get("GSLIDES_WEB_HOST")

    if os.environ.get("GSLIDES_WEB_PORT"):
        try:
            config["web"]["port"] = int(os.environ.get("GSLIDES_WEB_PORT"))
        except ValueError:
            raise ConfigurationError("GSLIDES_WEB_PORT must be an integer")

    return config


# Global configuration instance
config = get_config()
