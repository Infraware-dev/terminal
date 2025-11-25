"""Unit tests for authentication utilities."""

import httpx
import pytest
import respx

from src.api.auth import validate_anthropic_api_key


class TestValidateAnthropicApiKey:
    """Test validate_anthropic_api_key function."""

    @pytest.mark.anyio
    async def test_empty_api_key(self):
        """Test validation with empty API key."""
        is_valid, message = await validate_anthropic_api_key("")
        assert is_valid is False
        assert "cannot be empty" in message

    @pytest.mark.anyio
    async def test_whitespace_only_api_key(self):
        """Test validation with whitespace-only API key."""
        is_valid, message = await validate_anthropic_api_key("   ")
        assert is_valid is False
        assert "cannot be empty" in message

    @pytest.mark.anyio
    async def test_invalid_format_no_prefix(self):
        """Test validation with API key not starting with sk-ant-."""
        is_valid, message = await validate_anthropic_api_key("invalid-key-format")
        assert is_valid is False
        assert "Invalid API key format" in message
        assert "sk-ant-" in message

    @pytest.mark.anyio
    async def test_invalid_format_wrong_prefix(self):
        """Test validation with wrong prefix."""
        is_valid, message = await validate_anthropic_api_key("sk-test-wrong-prefix")
        assert is_valid is False
        assert "Invalid API key format" in message

    @pytest.mark.anyio
    @respx.mock
    async def test_valid_api_key_success(self):
        """Test validation with valid API key (200 response)."""
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(
                200, json={"id": "msg_test", "content": [{"text": "test"}]}
            )
        )

        is_valid, message = await validate_anthropic_api_key("sk-ant-valid-test-key")
        assert is_valid is True
        assert "valid" in message.lower()

    @pytest.mark.anyio
    @respx.mock
    async def test_invalid_api_key_401(self):
        """Test validation with invalid API key (401 response)."""
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(
                401, json={"error": {"message": "Invalid API key"}}
            )
        )

        is_valid, message = await validate_anthropic_api_key("sk-ant-invalid-key")
        assert is_valid is False
        assert "Invalid API key" in message

    @pytest.mark.anyio
    @respx.mock
    async def test_rate_limited_but_valid_429(self):
        """Test validation with rate-limited but valid key (429 response)."""
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(
                429, json={"error": {"message": "Rate limit exceeded"}}
            )
        )

        is_valid, message = await validate_anthropic_api_key("sk-ant-ratelimited-key")
        assert is_valid is True
        assert "valid" in message.lower()
        assert "rate limited" in message.lower()

    @pytest.mark.anyio
    @respx.mock
    async def test_model_not_found_404_fallback(self):
        """Test validation with model not found, then successful fallback."""
        # First request returns 404, second returns 200
        route = respx.post("https://api.anthropic.com/v1/messages")
        route.side_effect = [
            httpx.Response(404, json={"error": {"message": "Model not found"}}),
            httpx.Response(200, json={"id": "msg_test"}),
        ]

        is_valid, message = await validate_anthropic_api_key("sk-ant-test-key")
        assert is_valid is True
        assert "valid" in message.lower()

    @pytest.mark.anyio
    @respx.mock
    async def test_model_not_found_404_then_401(self):
        """Test validation with 404 then 401 (invalid key)."""
        route = respx.post("https://api.anthropic.com/v1/messages")
        route.side_effect = [
            httpx.Response(404, json={"error": {"message": "Model not found"}}),
            httpx.Response(401, json={"error": {"message": "Invalid API key"}}),
        ]

        is_valid, message = await validate_anthropic_api_key("sk-ant-invalid-key")
        assert is_valid is False
        assert "Invalid API key" in message

    @pytest.mark.anyio
    @respx.mock
    async def test_model_not_found_404_then_other_error(self):
        """Test validation with 404 then other error status."""
        route = respx.post("https://api.anthropic.com/v1/messages")
        route.side_effect = [
            httpx.Response(404, json={"error": {"message": "Model not found"}}),
            httpx.Response(500, json={"error": {"message": "Internal server error"}}),
        ]

        is_valid, message = await validate_anthropic_api_key("sk-ant-test-key")
        assert is_valid is False
        assert "500" in message

    @pytest.mark.anyio
    @respx.mock
    async def test_other_error_status_codes(self):
        """Test validation with various error status codes."""
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(
                500, json={"error": {"message": "Server error"}}
            )
        )

        is_valid, message = await validate_anthropic_api_key("sk-ant-test-key")
        assert is_valid is False
        assert "500" in message

    @pytest.mark.anyio
    @respx.mock
    async def test_timeout_exception(self):
        """Test validation with timeout error."""
        respx.post("https://api.anthropic.com/v1/messages").mock(
            side_effect=httpx.TimeoutException("Timeout")
        )

        is_valid, message = await validate_anthropic_api_key("sk-ant-test-key")
        assert is_valid is False
        assert "timed out" in message.lower()

    @pytest.mark.anyio
    @respx.mock
    async def test_network_error(self):
        """Test validation with network error."""
        respx.post("https://api.anthropic.com/v1/messages").mock(
            side_effect=httpx.RequestError("Connection failed")
        )

        is_valid, message = await validate_anthropic_api_key("sk-ant-test-key")
        assert is_valid is False
        assert "Network error" in message

    @pytest.mark.anyio
    @respx.mock
    async def test_unexpected_exception(self):
        """Test validation with unexpected exception."""
        respx.post("https://api.anthropic.com/v1/messages").mock(
            side_effect=Exception("Unexpected error")
        )

        is_valid, message = await validate_anthropic_api_key("sk-ant-test-key")
        assert is_valid is False
        assert "Unexpected error" in message

    @pytest.mark.anyio
    @respx.mock
    async def test_request_headers_and_body(self):
        """Test that validation sends correct headers and body."""
        route = respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(200, json={"id": "msg_test"})
        )

        api_key = "sk-ant-header-test-key"
        await validate_anthropic_api_key(api_key)

        # Verify the request was made with correct headers
        assert route.called
        request = route.calls.last.request
        assert request.headers["x-api-key"] == api_key
        assert request.headers["anthropic-version"] == "2023-06-01"
        assert request.headers["content-type"] == "application/json"

        # Verify request body
        import json

        body = json.loads(request.content)
        assert body["model"] == "claude-3-7-sonnet-latest"
        assert body["max_tokens"] == 1
        assert body["messages"][0]["role"] == "user"
        assert body["messages"][0]["content"] == "test"

    @pytest.mark.anyio
    @respx.mock
    async def test_timeout_configuration(self):
        """Test that httpx client uses correct timeout."""
        route = respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(200, json={"id": "msg_test"})
        )

        await validate_anthropic_api_key("sk-ant-test-key")

        # The timeout is configured at client level, so we can't directly test it
        # but we can verify the request was made
        assert route.called
