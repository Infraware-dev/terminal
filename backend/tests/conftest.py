import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
def test_client():
    """Create a FastAPI test client."""
    from src.api.main import app

    return TestClient(app)


@pytest.fixture
def temp_env_file():
    """Create a temporary .env file for testing."""
    with TemporaryDirectory() as tmpdir:
        env_path = Path(tmpdir) / ".env"
        env_path.touch()
        yield env_path


@pytest.fixture
def mock_config(temp_env_file, monkeypatch):
    """Mock the Config class with a temporary .env file."""
    from src.api.config import Config

    # Clear ANTHROPIC_API_KEY from environment before test to ensure test isolation.
    # Without this, API keys set by previous tests via config.set_api_key() persist
    # in os.environ and leak into subsequent tests, causing unexpected authentication state.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    # Patch the Config initialization to use temp file
    original_init = Config.__init__

    def mock_init(self):
        self.backend_dir = temp_env_file.parent
        self.env_file = temp_env_file
        from dotenv import load_dotenv

        load_dotenv(self.env_file)

    monkeypatch.setattr(Config, "__init__", mock_init)

    config = Config()
    return config


@pytest.fixture
def authenticated_config(mock_config):
    """Create a config instance with an authenticated API key."""
    mock_config.set_api_key("sk-ant-test-valid-key")
    return mock_config
