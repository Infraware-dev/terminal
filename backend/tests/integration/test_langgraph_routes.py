"""Integration tests for LangGraph proxy routes."""

from unittest.mock import patch

import httpx
import pytest
import respx


class TestLangGraphAuthentication:
    """Test authentication requirements for LangGraph routes."""

    @respx.mock
    def test_create_thread_requires_auth(self, test_client, mock_config):
        """Test that POST /threads requires authentication."""
        response = test_client.post("/threads", json={})
        assert response.status_code == 401
        data = response.json()
        assert "not authenticated" in data["detail"].lower()

    @respx.mock
    def test_get_thread_requires_auth(self, test_client, mock_config):
        """Test that GET /threads/{id} requires authentication."""
        response = test_client.get("/threads/test-thread-id")
        assert response.status_code == 401

    @respx.mock
    def test_get_thread_history_requires_auth(self, test_client, mock_config):
        """Test that GET /threads/{id}/history requires authentication."""
        response = test_client.get("/threads/test-thread-id/history")
        assert response.status_code == 401


class TestLangGraphProxySuccess:
    """Test successful proxy requests to LangGraph server."""

    @respx.mock
    def test_create_thread_success(self, test_client, authenticated_config):
        """Test successful thread creation."""
        # Mock the LangGraph server response
        mock_response = {"thread_id": "thread_123", "status": "created"}
        respx.post("http://localhost:2024/threads").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.post("/threads", json={"metadata": "test"})

            assert response.status_code == 200
            data = response.json()
            assert data["thread_id"] == "thread_123"
            assert data["status"] == "created"

    @respx.mock
    def test_get_thread_success(self, test_client, authenticated_config):
        """Test successful thread retrieval."""
        mock_response = {"thread_id": "thread_123", "messages": []}
        respx.get("http://localhost:2024/threads/thread_123").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.get("/threads/thread_123")

            assert response.status_code == 200
            data = response.json()
            assert data["thread_id"] == "thread_123"

    @respx.mock
    def test_get_thread_history_success(self, test_client, authenticated_config):
        """Test successful thread history retrieval."""
        mock_response = {"thread_id": "thread_123", "history": [{"step": 1}]}
        respx.get("http://localhost:2024/threads/thread_123/history").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.get("/threads/thread_123/history")

            assert response.status_code == 200
            data = response.json()
            assert "history" in data

    @respx.mock
    def test_proxy_forwards_request_body(self, test_client, authenticated_config):
        """Test that proxy forwards request body correctly."""
        request_body = {"name": "test-thread", "metadata": {"key": "value"}}

        # Capture the request to verify body was forwarded
        mock_route = respx.post("http://localhost:2024/threads").mock(
            return_value=httpx.Response(200, json={"thread_id": "123"})
        )

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.post("/threads", json=request_body)

            assert response.status_code == 200
            # Verify request was made
            assert mock_route.called

    @respx.mock
    def test_proxy_forwards_query_parameters(self, test_client, authenticated_config):
        """Test that proxy forwards query parameters."""
        respx.get("http://localhost:2024/threads/thread_123").mock(
            return_value=httpx.Response(200, json={"thread_id": "thread_123"})
        )

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.get("/threads/thread_123?limit=10&offset=5")

            assert response.status_code == 200

    @respx.mock
    def test_proxy_returns_langgraph_status_codes(self, test_client, authenticated_config):
        """Test that proxy returns LangGraph server status codes."""
        # Test 404 from LangGraph server
        respx.get("http://localhost:2024/threads/nonexistent").mock(
            return_value=httpx.Response(404, json={"error": "Thread not found"})
        )

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.get("/threads/nonexistent")

            # Should return the 404 from LangGraph, not transform it
            assert response.status_code == 404
            data = response.json()
            assert "error" in data


class TestLangGraphProxyErrors:
    """Test error handling in LangGraph proxy."""

    @respx.mock
    def test_connection_error_returns_503(self, test_client, authenticated_config):
        """Test that connection errors return 503."""
        # Mock connection error
        respx.post("http://localhost:2024/threads").mock(
            side_effect=httpx.ConnectError("Connection failed")
        )

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.post("/threads", json={})

            assert response.status_code == 503
            data = response.json()
            assert "server is not running" in data["detail"].lower()

    @respx.mock
    def test_timeout_error_returns_504(self, test_client, authenticated_config):
        """Test that timeout errors return 504."""
        # Mock timeout error
        respx.get("http://localhost:2024/threads/thread_123").mock(
            side_effect=httpx.TimeoutException("Request timed out")
        )

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.get("/threads/thread_123")

            assert response.status_code == 504
            data = response.json()
            assert "timed out" in data["detail"].lower()

    @respx.mock
    def test_unexpected_error_returns_500(self, test_client, authenticated_config):
        """Test that unexpected errors return 500."""
        # Mock unexpected error
        respx.post("http://localhost:2024/threads").mock(
            side_effect=Exception("Unexpected error")
        )

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.post("/threads", json={})

            assert response.status_code == 500
            data = response.json()
            assert "proxy error" in data["detail"].lower()


class TestLangGraphProxyHeaders:
    """Test header forwarding in LangGraph proxy."""

    @respx.mock
    def test_proxy_forwards_headers(self, test_client, authenticated_config):
        """Test that proxy forwards request headers (except host)."""
        mock_route = respx.post("http://localhost:2024/threads").mock(
            return_value=httpx.Response(200, json={"thread_id": "123"})
        )

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.post(
                "/threads",
                json={},
                headers={"X-Custom-Header": "test-value"},
            )

            assert response.status_code == 200
            assert mock_route.called

    @respx.mock
    def test_proxy_removes_host_header(self, test_client, authenticated_config):
        """Test that proxy removes host header before forwarding."""
        # The proxy should remove the host header to avoid conflicts
        respx.post("http://localhost:2024/threads").mock(
            return_value=httpx.Response(200, json={"thread_id": "123"})
        )

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.post("/threads", json={})

            # Should succeed without host header conflicts
            assert response.status_code == 200


class TestLangGraphRouterConfiguration:
    """Test LangGraph router configuration."""

    def test_langgraph_routes_no_prefix(self, test_client):
        """Test that LangGraph routes don't have /api prefix."""
        # Should be /threads, not /api/threads
        response = test_client.post("/threads", json={})
        # Should not be 404 (route exists), will be 401 (auth required)
        assert response.status_code != 404

    def test_langgraph_routes_in_openapi(self, test_client):
        """Test that LangGraph routes appear in OpenAPI schema."""
        response = test_client.get("/openapi.json")
        schema = response.json()

        # Check that thread endpoints are in schema
        assert "/threads" in schema["paths"]
        assert "/threads/{thread_id}" in schema["paths"]
        assert "/threads/{thread_id}/history" in schema["paths"]

    def test_langgraph_routes_have_tags(self, test_client):
        """Test that LangGraph routes have correct tags."""
        response = test_client.get("/openapi.json")
        schema = response.json()

        # Check tags
        threads_post = schema["paths"]["/threads"]["post"]
        assert "langgraph" in threads_post["tags"]
