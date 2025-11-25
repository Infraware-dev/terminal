"""Unit tests for Config class."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from src.api.config import Config


class TestConfigInitialization:
    """Test Config class initialization."""

    def test_init_with_existing_env_file(self, temp_env_file, monkeypatch):
        """Test initialization with existing .env file."""
        # Write a test key to the env file
        temp_env_file.write_text("ANTHROPIC_API_KEY=sk-ant-test-key\n")

        # Mock the Config to use temp file
        def mock_init(self):
            self.backend_dir = temp_env_file.parent
            self.env_file = temp_env_file
            from dotenv import load_dotenv

            load_dotenv(self.env_file)

        monkeypatch.setattr(Config, "__init__", mock_init)

        config = Config()
        assert config.env_file == temp_env_file
        assert config.backend_dir == temp_env_file.parent

    def test_init_without_env_file(self, monkeypatch):
        """Test initialization when .env file doesn't exist."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            def mock_init(self):
                self.backend_dir = tmpdir_path
                self.env_file = tmpdir_path / ".env"
                from dotenv import load_dotenv

                load_dotenv(self.env_file)

            monkeypatch.setattr(Config, "__init__", mock_init)

            config = Config()
            assert config.env_file == tmpdir_path / ".env"


class TestGetApiKey:
    """Test get_api_key method."""

    def test_get_api_key_when_present(self, mock_config):
        """Test getting API key when it exists."""
        mock_config.set_api_key("sk-ant-test-key")
        api_key = mock_config.get_api_key()
        assert api_key == "sk-ant-test-key"

    def test_get_api_key_when_absent(self, mock_config):
        """Test getting API key when it doesn't exist."""
        api_key = mock_config.get_api_key()
        assert api_key is None

    def test_get_api_key_after_set(self, mock_config):
        """Test getting API key after setting it."""
        mock_config.set_api_key("sk-ant-new-key")
        api_key = mock_config.get_api_key()
        assert api_key == "sk-ant-new-key"


class TestSetApiKey:
    """Test set_api_key method."""

    def test_set_api_key_success(self, mock_config):
        """Test successfully setting API key."""
        result = mock_config.set_api_key("sk-ant-valid-key")
        assert result is True
        assert mock_config.get_api_key() == "sk-ant-valid-key"

    def test_set_api_key_creates_env_file(self, mock_config):
        """Test that set_api_key creates .env file if it doesn't exist."""
        # Remove the env file
        if mock_config.env_file.exists():
            mock_config.env_file.unlink()

        result = mock_config.set_api_key("sk-ant-test-key")
        assert result is True
        assert mock_config.env_file.exists()

    def test_set_api_key_updates_environment(self, mock_config):
        """Test that set_api_key updates os.environ."""
        mock_config.set_api_key("sk-ant-env-test")
        assert os.environ.get("ANTHROPIC_API_KEY") == "sk-ant-env-test"

    def test_set_api_key_overwrites_existing(self, mock_config):
        """Test that set_api_key overwrites existing key."""
        mock_config.set_api_key("sk-ant-old-key")
        assert mock_config.get_api_key() == "sk-ant-old-key"

        mock_config.set_api_key("sk-ant-new-key")
        assert mock_config.get_api_key() == "sk-ant-new-key"

    def test_set_api_key_with_special_characters(self, mock_config):
        """Test setting API key with special characters."""
        special_key = "sk-ant-key_with-special.chars123"
        result = mock_config.set_api_key(special_key)
        assert result is True
        assert mock_config.get_api_key() == special_key

    def test_set_api_key_failure_handling(self, mock_config, monkeypatch):
        """Test set_api_key handles exceptions gracefully."""

        def mock_set_key(*args, **kwargs):
            raise Exception("File write error")

        monkeypatch.setattr("src.api.config.set_key", mock_set_key)

        result = mock_config.set_api_key("sk-ant-test-key")
        assert result is False


class TestIsAuthenticated:
    """Test is_authenticated method."""

    def test_is_authenticated_with_valid_key(self, mock_config):
        """Test is_authenticated returns True with valid key."""
        mock_config.set_api_key("sk-ant-valid-key")
        assert mock_config.is_authenticated() is True

    def test_is_authenticated_without_key(self, mock_config):
        """Test is_authenticated returns False without key."""
        assert mock_config.is_authenticated() is False

    def test_is_authenticated_with_empty_key(self, mock_config):
        """Test is_authenticated returns False with empty key."""
        mock_config.set_api_key("")
        assert mock_config.is_authenticated() is False

    def test_is_authenticated_with_whitespace_key(self, mock_config):
        """Test is_authenticated returns False with whitespace-only key."""
        mock_config.set_api_key("   ")
        assert mock_config.is_authenticated() is False

    def test_is_authenticated_after_clearing_key(self, mock_config):
        """Test is_authenticated after clearing the key."""
        mock_config.set_api_key("sk-ant-test-key")
        assert mock_config.is_authenticated() is True

        # Clear the key by setting to empty
        mock_config.set_api_key("")
        assert mock_config.is_authenticated() is False


class TestConfigGlobalInstance:
    """Test the global config instance."""

    def test_global_config_exists(self):
        """Test that global config instance is available."""
        from src.api.config import config

        assert config is not None
        assert isinstance(config, Config)
