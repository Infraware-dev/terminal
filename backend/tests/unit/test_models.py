"""Unit tests for Pydantic models."""

import pytest
from pydantic import ValidationError

from src.api.models import AuthRequest, AuthResponse, AuthStatusResponse


class TestAuthRequest:
    """Test AuthRequest model validation."""

    def test_valid_api_key(self):
        """Test that valid API key is accepted."""
        request = AuthRequest(api_key="sk-ant-test-key")
        assert request.api_key == "sk-ant-test-key"

    def test_empty_api_key_fails(self):
        """Test that empty API key fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            AuthRequest(api_key="")

        errors = exc_info.value.errors()
        assert any("at least 1 character" in str(error) for error in errors)

    def test_missing_api_key_fails(self):
        """Test that missing API key fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            AuthRequest()

        errors = exc_info.value.errors()
        assert any(error["type"] == "missing" for error in errors)

    def test_whitespace_only_api_key(self):
        """Test that whitespace-only API key passes pydantic but should fail in auth logic."""
        # Pydantic allows whitespace (min_length checks character count)
        request = AuthRequest(api_key="   ")
        assert request.api_key == "   "

    def test_long_api_key(self):
        """Test that very long API keys are accepted."""
        long_key = "sk-ant-" + "x" * 1000
        request = AuthRequest(api_key=long_key)
        assert request.api_key == long_key


class TestAuthResponse:
    """Test AuthResponse model."""

    def test_success_response(self):
        """Test successful authentication response."""
        response = AuthResponse(success=True, message="API key validated")
        assert response.success is True
        assert response.message == "API key validated"

    def test_failure_response(self):
        """Test failed authentication response."""
        response = AuthResponse(success=False, message="Invalid API key")
        assert response.success is False
        assert response.message == "Invalid API key"

    def test_missing_fields_fail(self):
        """Test that missing required fields fail validation."""
        with pytest.raises(ValidationError):
            AuthResponse(success=True)

        with pytest.raises(ValidationError):
            AuthResponse(message="test")

    def test_wrong_type_fails(self):
        """Test that wrong field types fail validation."""
        with pytest.raises(ValidationError):
            AuthResponse(success="yes", message="test")

        with pytest.raises(ValidationError):
            AuthResponse(success=True, message=123)


class TestAuthStatusResponse:
    """Test AuthStatusResponse model."""

    def test_authenticated_status(self):
        """Test authenticated status response."""
        response = AuthStatusResponse(authenticated=True, has_api_key=True)
        assert response.authenticated is True
        assert response.has_api_key is True

    def test_unauthenticated_status(self):
        """Test unauthenticated status response."""
        response = AuthStatusResponse(authenticated=False, has_api_key=False)
        assert response.authenticated is False
        assert response.has_api_key is False

    def test_has_key_but_not_authenticated(self):
        """Test edge case where key exists but not authenticated."""
        response = AuthStatusResponse(authenticated=False, has_api_key=True)
        assert response.authenticated is False
        assert response.has_api_key is True

    def test_missing_fields_fail(self):
        """Test that missing required fields fail validation."""
        with pytest.raises(ValidationError):
            AuthStatusResponse(authenticated=True)

        with pytest.raises(ValidationError):
            AuthStatusResponse(has_api_key=True)

    def test_wrong_type_fails(self):
        """Test that wrong field types fail validation."""
        with pytest.raises(ValidationError):
            AuthStatusResponse(authenticated="yes", has_api_key=True)

        with pytest.raises(ValidationError):
            AuthStatusResponse(authenticated=True, has_api_key="no")
