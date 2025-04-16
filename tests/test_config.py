"""Tests for the configuration module."""

import os
import json
import tempfile
from unittest import mock
import unittest

import pytest

from ai_deck_translator.config import (
    DEFAULT_CONFIG,
    validate_config,
    load_config,
    save_config,
    get_config,
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


class TestConfig(unittest.TestCase):
    def test_load_config_nonexistent(self):
        with self.assertRaises(FileNotFoundError):
            load_config("nonexistent_file.json")

    def test_load_config_invalid_json(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as temp_file:
            temp_file.write("")  # Write invalid JSON (empty)
            temp_file_path = temp_file.name
        try:
            with self.assertRaises(json.JSONDecodeError):
                load_config(temp_file_path)
        finally:
            os.remove(temp_file_path)

    def test_load_config_valid(self):
        # Provide all required keys: model and api_key
        valid_config = {"model": "test-model", "api_key": "test-key"}
        with tempfile.NamedTemporaryFile("w", delete=False) as temp_file:
            json.dump(valid_config, temp_file)
            temp_file_path = temp_file.name
        try:
            config = load_config(temp_file_path)
            self.assertEqual(config["model"], "test-model")
            self.assertEqual(config["api_key"], "test-key")
        finally:
            os.remove(temp_file_path)

    def test_env_var_override(self):
        # Set environment variable for model override
        os.environ["GSLIDES_MODEL"] = "claude-3-haiku-20240307"
        config = get_config()
        self.assertEqual(config["api"]["anthropic"]["model"], "claude-3-haiku-20240307")
        del os.environ["GSLIDES_MODEL"]


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
    config = get_config()
    assert config["api"]["anthropic"]["model"] == "claude-3-haiku-20240307"
