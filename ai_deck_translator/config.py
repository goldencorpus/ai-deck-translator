"""
Configuration module for the AI Deck Translator application.

This module manages configuration settings and environment variables
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# Load dotenv before any imports that might use environment variables
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # dotenv is optional

from ai_deck_translator.utils.exceptions import ConfigurationError
from ai_deck_translator.utils.logging import logger

# Default paths
CONFIG_DIR = os.path.join(str(Path.home()), ".gslides_translator")
CREDENTIALS_PATH = os.path.join(CONFIG_DIR, "credentials.json")
TOKEN_PATH = os.path.join(CONFIG_DIR, "token.json")

# Add CLAUDE_MODEL and RECOVERY_DIRECTORY for test compatibility
CLAUDE_MODEL = "claude-haiku-4-5"
RECOVERY_DIRECTORY = "translation_recovery"

# Required environment variables
REQUIRED_ENV_VARS = ["CLAUDE_API_KEY"]

# Optional environment variables with their config paths
OPTIONAL_ENV_VARS = {
    "ANTHROPIC_MODEL": ["api", "anthropic", "model"],
    "ANTHROPIC_MAX_TOKENS": ["api", "anthropic", "max_tokens"],
    "ANTHROPIC_TEMPERATURE": ["api", "anthropic", "temperature"],
    "GOOGLE_CREDENTIALS_FILE": ["api", "google", "credentials_file"],
    "GOOGLE_TOKEN_FILE": ["api", "google", "token_file"],
    "TRANSLATION_BATCH_SIZE": ["translation", "batch_size"],
    "TRANSLATION_MAX_RETRIES": ["translation", "max_retries"],
    "TRANSLATION_TIMEOUT": ["translation", "timeout"],
    "LOGGING_LEVEL": ["logging", "level"],
    "RECOVERY_ENABLED": ["recovery", "enabled"],
    "RECOVERY_DIRECTORY": ["recovery", "directory"],
    "WEB_SECRET_KEY": ["web", "secret_key"],
    "WEB_HOST": ["web", "host"],
    "WEB_PORT": ["web", "port"],
    "WEB_DEBUG": ["web", "debug"],
}

# Default configuration
DEFAULT_CONFIG = {
    "presentation": {
        "create_copy": True,
        "copy_title_suffix": " (Translated)",
        "open_browser": True,
    },
    "translation": {
        "batch_size": 100000,  # Input token budget per batch
        "blocks_per_batch": 40,  # Text blocks per API call. Larger = more document context
        # (better terminology coherence) and fewer calls; the completeness gate + retry
        # still recover any blocks a truncated response would drop. Was 10 (over-cautious
        # legacy from the original truncation skip-bug).
        "max_retries": 3,  # Maximum number of retries for API calls
        "timeout": 120,  # Timeout for API calls in seconds
    },
    "api": {
        "anthropic": {
            "model": "claude-sonnet-4-6",
            "max_tokens": 16000,  # Output cap per call — well within the model's limit;
            # sized to comfortably hold ~40 translated blocks. (150000 caused truncation.)
            "temperature": 0.0,
        },
        "anthropic_api_base": "https://api.anthropic.com/v1",
        "google": {
            "scopes": [
                "https://www.googleapis.com/auth/presentations",
                "https://www.googleapis.com/auth/drive",
            ],
            "credentials_file": "credentials.json",
            "token_file": "token.json",
        },
    },
    "logging": {
        "level": "INFO",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "date_format": "%Y-%m-%d %H:%M:%S",
    },
    # Coherence Contract (compile-then-execute) — see docs/plans/coherence-contract-*.md.
    # All knobs default to the new coherent path; flip CONTRACT_ENABLED / PROMPT_CACHE /
    # SWEEP_ENABLED to false for the exact pre-contract proven path (kill switch).
    "coherence": {
        "contract_enabled": True,  # P0: build + inject the deck-wide Coherence Contract
        "contract_min_blocks": 8,  # decks smaller than this skip the contract (overhead)
        "prompt_cache": True,  # P1: cache the stable prefix + seed-then-fan-out batches
        "single_call_first": False,  # P1: attempt one full-deck JSONL call when it fits (opt-in)
        "single_call_max_fraction": 0.7,  # only single-call when est. output < this * max_tokens
        "sweep_enabled": True,  # P2: deterministic sweep + one surgical patch call
        "max_concurrent_batches": 8,  # post-seed fan-out cap (bounded by account rate limits)
    },
    "recovery": {"enabled": True, "directory": "translation_recovery"},
    "web": {
        "secret_key": os.urandom(24).hex(),
        "host": "127.0.0.1",
        "port": 5000,
        "debug": False,
    },
}


def _env_bool(name: str, default: bool) -> bool:
    """Parse a boolean environment variable; falls back to default when unset."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    """Parse a float environment variable; falls back to default when unset/invalid."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


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
    required_sections = [
        "presentation",
        "translation",
        "api",
        "logging",
        "recovery",
        "web",
    ]
    for section in required_sections:
        if section not in config:
            raise ConfigurationError(
                f"Missing required configuration section: {section}"
            )

    # Check for required nested keys
    if "create_copy" not in config["presentation"]:
        raise ConfigurationError("Missing 'create_copy' in presentation config")

    if "model" not in config["api"]["anthropic"]:
        raise ConfigurationError("Missing 'model' in anthropic config")

    if "max_tokens" not in config["api"]["anthropic"]:
        raise ConfigurationError("Missing 'max_tokens' in anthropic config")

    if "temperature" not in config["api"]["anthropic"]:
        raise ConfigurationError("Missing 'temperature' in anthropic config")

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
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, "r") as f:
        config = json.load(f)
    # Ensure required keys are present
    required_keys = ["model", "api_key"]
    for key in required_keys:
        if key not in config:
            raise ConfigurationError(f"Missing required config key: {key}")
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
        config["api"]["anthropic"]["model"] = os.environ.get("GSLIDES_MODEL")

    if os.environ.get("ANTHROPIC_MAX_TOKENS"):
        try:
            config["api"]["anthropic"]["max_tokens"] = int(
                os.environ.get("ANTHROPIC_MAX_TOKENS")
            )
        except ValueError:
            raise ConfigurationError("ANTHROPIC_MAX_TOKENS must be an integer")

    if os.environ.get("TRANSLATION_BLOCKS_PER_BATCH"):
        try:
            config["translation"]["blocks_per_batch"] = int(
                os.environ.get("TRANSLATION_BLOCKS_PER_BATCH")
            )
        except ValueError:
            raise ConfigurationError("TRANSLATION_BLOCKS_PER_BATCH must be an integer")

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

# Export configuration values as module-level variables
API_CONFIG = config["api"]
TRANSLATION_CONFIG = config["translation"]
LOGGING_CONFIG = config["logging"]
RECOVERY_CONFIG = config["recovery"]
WEB_CONFIG = config["web"]

# Convenience variables
ANTHROPIC_API_KEY = os.environ.get("CLAUDE_API_KEY")
ANTHROPIC_MODEL = API_CONFIG["anthropic"]["model"]
ANTHROPIC_MAX_TOKENS = API_CONFIG["anthropic"]["max_tokens"]
ANTHROPIC_TEMPERATURE = API_CONFIG["anthropic"]["temperature"]

GOOGLE_SCOPES = API_CONFIG["google"]["scopes"]
GOOGLE_CREDENTIALS_FILE = API_CONFIG["google"]["credentials_file"]
GOOGLE_TOKEN_FILE = API_CONFIG["google"]["token_file"]

BATCH_SIZE = TRANSLATION_CONFIG["batch_size"]
BLOCKS_PER_BATCH = TRANSLATION_CONFIG.get("blocks_per_batch", 10)
MAX_RETRIES = TRANSLATION_CONFIG["max_retries"]
TIMEOUT = TRANSLATION_CONFIG["timeout"]

LOGGING_LEVEL = LOGGING_CONFIG["level"]
LOGGING_FORMAT = LOGGING_CONFIG["format"]
LOGGING_DATE_FORMAT = LOGGING_CONFIG["date_format"]

RECOVERY_ENABLED = RECOVERY_CONFIG["enabled"]
RECOVERY_DIRECTORY = RECOVERY_CONFIG["directory"]

# Coherence Contract knobs. Read from the (possibly file-loaded) config with safe
# defaults, then allow per-run environment overrides. Defaults keep the new coherent
# path ON; export CONTRACT_ENABLED=false / PROMPT_CACHE=false / SWEEP_ENABLED=false to
# fall back to the exact pre-contract proven path.
COHERENCE_CONFIG = config.get("coherence", DEFAULT_CONFIG["coherence"])
CONTRACT_ENABLED = _env_bool(
    "CONTRACT_ENABLED", COHERENCE_CONFIG.get("contract_enabled", True)
)
CONTRACT_MIN_BLOCKS = int(COHERENCE_CONFIG.get("contract_min_blocks", 8))
if os.environ.get("CONTRACT_MIN_BLOCKS"):
    try:
        CONTRACT_MIN_BLOCKS = int(os.environ["CONTRACT_MIN_BLOCKS"])
    except ValueError:
        pass
PROMPT_CACHE = _env_bool("PROMPT_CACHE", COHERENCE_CONFIG.get("prompt_cache", True))
SINGLE_CALL_FIRST = _env_bool(
    "SINGLE_CALL_FIRST", COHERENCE_CONFIG.get("single_call_first", False)
)
SINGLE_CALL_MAX_FRACTION = _env_float(
    "SINGLE_CALL_MAX_FRACTION", COHERENCE_CONFIG.get("single_call_max_fraction", 0.7)
)
SWEEP_ENABLED = _env_bool("SWEEP_ENABLED", COHERENCE_CONFIG.get("sweep_enabled", True))
MAX_CONCURRENT_BATCHES = int(COHERENCE_CONFIG.get("max_concurrent_batches", 8))
if os.environ.get("MAX_CONCURRENT_BATCHES"):
    try:
        MAX_CONCURRENT_BATCHES = int(os.environ["MAX_CONCURRENT_BATCHES"])
    except ValueError:
        pass

SECRET_KEY = WEB_CONFIG["secret_key"]
WEB_HOST = WEB_CONFIG["host"]
WEB_PORT = WEB_CONFIG["port"]
WEB_DEBUG = WEB_CONFIG["debug"]
