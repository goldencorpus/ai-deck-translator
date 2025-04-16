"""Tests for the configuration module."""

import os
import json
import tempfile
from unittest import mock

import pytest

from ai_deck_translator.config import (
    DEFAULT_CONFIG,
    validate_config,
    load_config,
    save_config,
)
from ai_deck_translator.utils.exceptions import ConfigurationError


def test_validate_config_valid():
    """Test that a valid configuration passes validation."""
    assert validate_config(DEFAULT_CONFIG) is True


def test_validate_config_missing_section():
    """Test that validation fails with missing sections."""
    invalid_config = DEFAULT_CONFIG.copy()
    invalid_config.pop("presentation")

    with pytest.raises(ConfigurationError):
        validate_config(invalid_config)


def test_load_config_nonexistent():
    """Test that loading a nonexistent config falls back to defaults."""
    config = load_config("nonexistent_file.json")
    assert config == DEFAULT_CONFIG


def test_load_config_invalid_json():
    """Test that loading an invalid JSON file raises an error."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
        temp_file.write("This is not valid JSON")
        temp_file_path = temp_file.name

    try:
        with pytest.raises(ConfigurationError):
            load_config(temp_file_path)
    finally:
        os.unlink(temp_file_path)


def test_load_config_valid():
    """Test that loading a valid config file works."""
    custom_config = {
        "presentation": {
            "create_copy": False,
            "copy_title_suffix": " (Custom)",
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
        json.dump(custom_config, temp_file)
        temp_file_path = temp_file.name

    try:
        config = load_config(temp_file_path)
        assert config["presentation"]["create_copy"] is False
        assert config["presentation"]["copy_title_suffix"] == " (Custom)"
        # Other values should come from defaults
        assert "translation" in config
        assert "api" in config
    finally:
        os.unlink(temp_file_path)


def test_save_config():
    """Test that saving configuration works."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = os.path.join(temp_dir, "config.json")
        save_config(DEFAULT_CONFIG, config_path)

        assert os.path.exists(config_path)

        with open(config_path, "r") as f:
            saved_config = json.load(f)

        assert saved_config == DEFAULT_CONFIG


@mock.patch.dict(os.environ, {"GSLIDES_MODEL": "claude-3-haiku-20240307"})
def test_env_var_override():
    """Test that environment variables override config settings."""
    from ai_deck_translator.config import get_config

    # Patch the home directory to avoid interference with user's actual config
    with mock.patch("ai_deck_translator.config.CONFIG_DIR", "/tmp/nonexistent_dir"):
        config = get_config()
        assert config["translation"]["model"] == "claude-3-haiku-20240307"
