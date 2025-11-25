"""Integration tests for authentication routes."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx


class TestAuthEndpoint:
    """Test POST /api/auth endpoint."""

    @respx.mock
    def test_auth_success_with_valid_key(self, test_client, mock_config):
        """Test successful authentication with valid API key."""
        # Mock the Anthropic API validation
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(200, json={"id": "msg_test"})
        )

        # Mock the config to use our test config
        with patch("src.api.routes.auth_routes.config", mock_config):
            response = test_client.post("/api/auth", json={"api_key": "sk-ant-valid-test-key"})

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "validated" in data["message"].lower()
            assert "stored" in data["message"].lower()

    @respx.mock
    def test_auth_failure_with_invalid_key(self, test_client, mock_config):
        """Test authentication failure with invalid API key."""
        # Mock the Anthropic API to return 401
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(401, json={"error": {"message": "Invalid API key"}})
        )

        with patch("src.api.routes.auth_routes.config", mock_config):
            response = test_client.post("/api/auth", json={"api_key": "sk-ant-invalid-key"})

            assert response.status_code == 400
            data = response.json()
            assert "detail" in data
            assert "Invalid API key" in data["detail"]

    def test_auth_failure_with_empty_key(self, test_client, mock_config):
        """Test authentication failure with empty API key."""
        with patch("src.api.routes.auth_routes.config", mock_config):
            response = test_client.post("/api/auth", json={"api_key": ""})

            # Empty string fails Pydantic validation (min_length=1) and returns 422
            assert response.status_code == 422
            data = response.json()
            assert "detail" in data

    def test_auth_failure_with_wrong_format(self, test_client, mock_config):
        """Test authentication failure with wrong API key format."""
        with patch("src.api.routes.auth_routes.config", mock_config):
            response = test_client.post("/api/auth", json={"api_key": "invalid-format"})

            assert response.status_code == 400
            data = response.json()
            assert "detail" in data
            assert "format" in data["detail"].lower()
            assert "sk-ant-" in data["detail"]

    def test_auth_failure_with_missing_key(self, test_client):
        """Test authentication failure with missing API key in request."""
        response = test_client.post("/api/auth", json={})

        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data

    def test_auth_failure_with_invalid_json(self, test_client):
        """Test authentication failure with invalid JSON."""
        response = test_client.post("/api/auth", data="invalid json", headers={"content-type": "application/json"})

        assert response.status_code == 422

    @respx.mock
    def test_auth_stores_key_in_config(self, test_client, mock_config):
        """Test that successful auth stores key in config."""
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(200, json={"id": "msg_test"})
        )

        with patch("src.api.routes.auth_routes.config", mock_config):
            test_key = "sk-ant-stored-key"
            response = test_client.post("/api/auth", json={"api_key": test_key})

            assert response.status_code == 200
            # Verify key was stored
            assert mock_config.get_api_key() == test_key

    @respx.mock
    def test_auth_failure_when_config_storage_fails(self, test_client, mock_config):
        """Test authentication failure when config storage fails."""
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(200, json={"id": "msg_test"})
        )

        # Mock set_api_key to fail
        with patch("src.api.routes.auth_routes.config", mock_config):
            with patch.object(mock_config, "set_api_key", return_value=False):
                response = test_client.post("/api/auth", json={"api_key": "sk-ant-test-key"})

                assert response.status_code == 500
                data = response.json()
                assert "detail" in data
                assert "Failed to store" in data["detail"]

    @respx.mock
    def test_auth_with_rate_limited_key(self, test_client, mock_config):
        """Test authentication with rate-limited but valid key."""
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(429, json={"error": {"message": "Rate limit"}})
        )

        with patch("src.api.routes.auth_routes.config", mock_config):
            response = test_client.post("/api/auth", json={"api_key": "sk-ant-ratelimited-key"})

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    @respx.mock
    def test_auth_response_model_validation(self, test_client, mock_config):
        """Test that auth response matches AuthResponse model."""
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(200, json={"id": "msg_test"})
        )

        with patch("src.api.routes.auth_routes.config", mock_config):
            response = test_client.post("/api/auth", json={"api_key": "sk-ant-test-key"})

            assert response.status_code == 200
            data = response.json()

            # Check response structure matches AuthResponse model
            assert "success" in data
            assert "message" in data
            assert isinstance(data["success"], bool)
            assert isinstance(data["message"], str)


class TestGetAuthEndpoint:
    """Test GET /api/get-auth endpoint."""

    def test_get_auth_when_authenticated(self, test_client, mock_config):
        """Test get auth status when user is authenticated."""
        mock_config.set_api_key("sk-ant-test-key")

        with patch("src.api.routes.auth_routes.config", mock_config):
            response = test_client.get("/api/get-auth")

            assert response.status_code == 200
            data = response.json()
            assert data["authenticated"] is True
            assert data["has_api_key"] is True

    def test_get_auth_when_not_authenticated(self, test_client, mock_config):
        """Test get auth status when user is not authenticated."""
        with patch("src.api.routes.auth_routes.config", mock_config):
            response = test_client.get("/api/get-auth")

            assert response.status_code == 200
            data = response.json()
            assert data["authenticated"] is False
            assert data["has_api_key"] is False

    def test_get_auth_with_empty_key(self, test_client, mock_config):
        """Test get auth status with empty API key."""
        mock_config.set_api_key("")

        with patch("src.api.routes.auth_routes.config", mock_config):
            response = test_client.get("/api/get-auth")

            assert response.status_code == 200
            data = response.json()
            assert data["authenticated"] is False

    def test_get_auth_response_model_validation(self, test_client, mock_config):
        """Test that get-auth response matches AuthStatusResponse model."""
        with patch("src.api.routes.auth_routes.config", mock_config):
            response = test_client.get("/api/get-auth")

            assert response.status_code == 200
            data = response.json()

            # Check response structure matches AuthStatusResponse model
            assert "authenticated" in data
            assert "has_api_key" in data
            assert isinstance(data["authenticated"], bool)
            assert isinstance(data["has_api_key"], bool)

    def test_get_auth_returns_json(self, test_client, mock_config):
        """Test that get-auth endpoint returns JSON."""
        with patch("src.api.routes.auth_routes.config", mock_config):
            response = test_client.get("/api/get-auth")

            assert response.headers["content-type"] == "application/json"

    def test_get_auth_no_side_effects(self, test_client, mock_config):
        """Test that get-auth doesn't modify authentication state."""
        initial_key = mock_config.get_api_key()

        with patch("src.api.routes.auth_routes.config", mock_config):
            response = test_client.get("/api/get-auth")

            assert response.status_code == 200
            # Verify key wasn't changed
            assert mock_config.get_api_key() == initial_key


class TestAuthRouterConfiguration:
    """Test auth router configuration."""

    def test_auth_router_prefix(self, test_client):
        """Test that auth routes use /api prefix."""
        # Auth endpoint should be at /api/auth
        response = test_client.post("/api/auth", json={"api_key": "test"})
        assert response.status_code != 404

        # Get-auth endpoint should be at /api/get-auth
        response = test_client.get("/api/get-auth")
        assert response.status_code != 404

    def test_auth_router_tags(self, test_client):
        """Test that auth routes have correct tags in OpenAPI schema."""
        response = test_client.get("/openapi.json")
        schema = response.json()

        # Check that auth endpoints have authentication tag
        auth_path = schema["paths"]["/api/auth"]["post"]
        assert "authentication" in auth_path["tags"]

        get_auth_path = schema["paths"]["/api/get-auth"]["get"]
        assert "authentication" in get_auth_path["tags"]


class TestAuthWorkflow:
    """Test complete authentication workflow."""

    @respx.mock
    def test_complete_auth_workflow(self, test_client, mock_config):
        """Test complete authentication workflow from unauthenticated to authenticated."""
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(200, json={"id": "msg_test"})
        )

        with patch("src.api.routes.auth_routes.config", mock_config):
            # 1. Check initial unauthenticated state
            response = test_client.get("/api/get-auth")
            assert response.json()["authenticated"] is False

            # 2. Authenticate with valid key
            response = test_client.post("/api/auth", json={"api_key": "sk-ant-workflow-key"})
            assert response.status_code == 200
            assert response.json()["success"] is True

            # 3. Verify authenticated state
            response = test_client.get("/api/get-auth")
            assert response.json()["authenticated"] is True
            assert response.json()["has_api_key"] is True


class TestAuthValidationErrors:
    """Test authentication validation error handling."""

    @respx.mock
    def test_auth_with_timeout_error(self, test_client, mock_config):
        """Test authentication when API request times out."""
        # Mock timeout error
        respx.post("https://api.anthropic.com/v1/messages").mock(
            side_effect=httpx.TimeoutException("Request timed out")
        )

        with patch("src.api.routes.auth_routes.config", mock_config):
            response = test_client.post("/api/auth", json={"api_key": "sk-ant-timeout-key"})

            assert response.status_code == 400
            data = response.json()
            assert "timed out" in data["detail"].lower()

    @respx.mock
    def test_auth_with_network_error(self, test_client, mock_config):
        """Test authentication with network/request error."""
        # Mock request error
        respx.post("https://api.anthropic.com/v1/messages").mock(
            side_effect=httpx.RequestError("Network error")
        )

        with patch("src.api.routes.auth_routes.config", mock_config):
            response = test_client.post("/api/auth", json={"api_key": "sk-ant-network-key"})

            assert response.status_code == 400
            data = response.json()
            assert "network error" in data["detail"].lower()

    @respx.mock
    def test_auth_with_unexpected_exception(self, test_client, mock_config):
        """Test authentication with unexpected exception."""
        # Mock unexpected exception
        respx.post("https://api.anthropic.com/v1/messages").mock(
            side_effect=Exception("Unexpected error")
        )

        with patch("src.api.routes.auth_routes.config", mock_config):
            response = test_client.post("/api/auth", json={"api_key": "sk-ant-error-key"})

            assert response.status_code == 400
            data = response.json()
            assert "unexpected error" in data["detail"].lower()

    @respx.mock
    def test_auth_with_404_model_not_found(self, test_client, mock_config):
        """Test authentication when model returns 404."""
        # Mock 404 response (model not found)
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(404, json={"error": {"message": "Model not found"}})
        )

        with patch("src.api.routes.auth_routes.config", mock_config):
            response = test_client.post("/api/auth", json={"api_key": "sk-ant-404-key"})

            # When we get 404, we retry with same model and then fail
            assert response.status_code == 400
            data = response.json()
            # Should have validation failure message
            assert "detail" in data

    @respx.mock
    def test_auth_with_404_then_200_retry(self, test_client, mock_config):
        """Test authentication retries successfully after 404."""
        # First request returns 404, second returns 200
        call_count = 0

        def side_effect_fn(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(404, json={"error": {"message": "Model not found"}})
            return httpx.Response(200, json={"id": "msg_test"})

        respx.post("https://api.anthropic.com/v1/messages").mock(side_effect=side_effect_fn)

        with patch("src.api.routes.auth_routes.config", mock_config):
            response = test_client.post("/api/auth", json={"api_key": "sk-ant-retry-key"})

            # Should succeed on retry
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    @respx.mock
    def test_auth_with_404_then_401_retry(self, test_client, mock_config):
        """Test authentication retry detects invalid key after 404."""
        # First request returns 404, second returns 401
        call_count = 0

        def side_effect_fn(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(404, json={"error": {"message": "Model not found"}})
            return httpx.Response(401, json={"error": {"message": "Invalid API key"}})

        respx.post("https://api.anthropic.com/v1/messages").mock(side_effect=side_effect_fn)

        with patch("src.api.routes.auth_routes.config", mock_config):
            response = test_client.post("/api/auth", json={"api_key": "sk-ant-invalid-retry-key"})

            # Should fail with invalid key message
            assert response.status_code == 400
            data = response.json()
            assert "invalid api key" in data["detail"].lower()

    @respx.mock
    def test_auth_with_500_status_code(self, test_client, mock_config):
        """Test authentication with 500 status from API."""
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(500, json={"error": {"message": "Internal server error"}})
        )

        with patch("src.api.routes.auth_routes.config", mock_config):
            response = test_client.post("/api/auth", json={"api_key": "sk-ant-500-key"})

            assert response.status_code == 400
            data = response.json()
            assert "validation failed" in data["detail"].lower()
            assert "500" in data["detail"]
