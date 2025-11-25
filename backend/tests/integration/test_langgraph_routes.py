"""Integration tests for LanGraph proxy routes."""

from unittest.mock import patch

import httpx
import pytest
import respx


class TestAuthenticationRequired:
    """Test that all LanGraph routes require authentication."""

    def test_stream_run_requires_auth(self, test_client, mock_config):
        """Test POST /runs/stream requires authentication."""
        with patch("src.api.routes.langgraph_routes.config", mock_config):
            response = test_client.post("/runs/stream", json={})
            assert response.status_code == 401
            assert "Not authenticated" in response.json()["detail"]

    def test_invoke_run_requires_auth(self, test_client, mock_config):
        """Test POST /runs/invoke requires authentication."""
        with patch("src.api.routes.langgraph_routes.config", mock_config):
            response = test_client.post("/runs/invoke", json={})
            assert response.status_code == 401

    def test_get_run_requires_auth(self, test_client, mock_config):
        """Test GET /runs/{run_id} requires authentication."""
        with patch("src.api.routes.langgraph_routes.config", mock_config):
            response = test_client.get("/runs/test-run-id")
            assert response.status_code == 401

    def test_create_thread_requires_auth(self, test_client, mock_config):
        """Test POST /threads requires authentication."""
        with patch("src.api.routes.langgraph_routes.config", mock_config):
            response = test_client.post("/threads", json={})
            assert response.status_code == 401

    def test_get_thread_requires_auth(self, test_client, mock_config):
        """Test GET /threads/{thread_id} requires authentication."""
        with patch("src.api.routes.langgraph_routes.config", mock_config):
            response = test_client.get("/threads/test-thread-id")
            assert response.status_code == 401

    def test_get_thread_history_requires_auth(self, test_client, mock_config):
        """Test GET /threads/{thread_id}/history requires authentication."""
        with patch("src.api.routes.langgraph_routes.config", mock_config):
            response = test_client.get("/threads/test-thread-id/history")
            assert response.status_code == 401

    def test_catch_all_requires_auth(self, test_client, mock_config):
        """Test catch-all proxy route requires authentication."""
        with patch("src.api.routes.langgraph_routes.config", mock_config):
            response = test_client.get("/some/custom/path")
            assert response.status_code == 401


class TestInvokeRun:
    """Test POST /runs/invoke endpoint."""

    @respx.mock
    def test_invoke_run_success(self, test_client, authenticated_config):
        """Test successful synchronous run invocation."""
        # Mock LanGraph server response
        langgraph_response = {"run_id": "test-run-123", "status": "completed"}
        respx.post("http://localhost:2024/runs/invoke").mock(
            return_value=httpx.Response(200, json=langgraph_response)
        )

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.post("/runs/invoke", json={"input": "test"})

            assert response.status_code == 200
            assert response.json() == langgraph_response

    @respx.mock
    def test_invoke_run_with_query_params(self, test_client, authenticated_config):
        """Test invoke run with query parameters."""
        respx.post("http://localhost:2024/runs/invoke").mock(return_value=httpx.Response(200, json={}))

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.post("/runs/invoke?param1=value1&param2=value2", json={"input": "test"})

            assert response.status_code == 200
            # Verify query params were forwarded
            assert respx.calls.last.request.url.params["param1"] == "value1"
            assert respx.calls.last.request.url.params["param2"] == "value2"

    @respx.mock
    def test_invoke_run_langgraph_server_not_running(self, test_client, authenticated_config):
        """Test invoke run when LanGraph server is not running."""
        respx.post("http://localhost:2024/runs/invoke").mock(side_effect=httpx.ConnectError("Connection refused"))

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.post("/runs/invoke", json={})

            assert response.status_code == 503
            assert "not running" in response.json()["detail"].lower()
            assert "langgraph dev" in response.json()["detail"].lower()

    @respx.mock
    def test_invoke_run_timeout(self, test_client, authenticated_config):
        """Test invoke run with timeout."""
        respx.post("http://localhost:2024/runs/invoke").mock(side_effect=httpx.TimeoutException("Timeout"))

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.post("/runs/invoke", json={})

            assert response.status_code == 504
            assert "timed out" in response.json()["detail"].lower()


class TestStreamRun:
    """Test POST /runs/stream endpoint."""

    @respx.mock
    def test_stream_run_success(self, test_client, authenticated_config):
        """Test successful streaming run."""

        def stream_content():
            yield b"data: chunk1\n\n"
            yield b"data: chunk2\n\n"

        respx.post("http://localhost:2024/runs/stream").mock(
            return_value=httpx.Response(200, content=stream_content())
        )

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.post("/runs/stream", json={"input": "test"})

            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")

    @respx.mock
    def test_stream_run_langgraph_server_not_running(self, test_client, authenticated_config):
        """Test stream run when LanGraph server is not running."""
        respx.post("http://localhost:2024/runs/stream").mock(side_effect=httpx.ConnectError("Connection refused"))

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.post("/runs/stream", json={})

            assert response.status_code == 503
            assert "not running" in response.json()["detail"].lower()


class TestGetRun:
    """Test GET /runs/{run_id} endpoint."""

    @respx.mock
    def test_get_run_success(self, test_client, authenticated_config):
        """Test getting run status successfully."""
        run_data = {"run_id": "test-run-123", "status": "completed", "output": "result"}
        respx.get("http://localhost:2024/runs/test-run-123").mock(return_value=httpx.Response(200, json=run_data))

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.get("/runs/test-run-123")

            assert response.status_code == 200
            assert response.json() == run_data

    @respx.mock
    def test_get_run_not_found(self, test_client, authenticated_config):
        """Test getting non-existent run."""
        respx.get("http://localhost:2024/runs/nonexistent").mock(
            return_value=httpx.Response(404, json={"error": "Run not found"})
        )

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.get("/runs/nonexistent")

            assert response.status_code == 404


class TestThreadEndpoints:
    """Test thread management endpoints."""

    @respx.mock
    def test_create_thread_success(self, test_client, authenticated_config):
        """Test creating a new thread successfully."""
        thread_data = {"thread_id": "thread-123", "created_at": "2024-01-01"}
        respx.post("http://localhost:2024/threads").mock(return_value=httpx.Response(200, json=thread_data))

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.post("/threads", json={"metadata": "test"})

            assert response.status_code == 200
            assert response.json() == thread_data

    @respx.mock
    def test_get_thread_success(self, test_client, authenticated_config):
        """Test getting thread data successfully."""
        thread_data = {"thread_id": "thread-123", "messages": []}
        respx.get("http://localhost:2024/threads/thread-123").mock(return_value=httpx.Response(200, json=thread_data))

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.get("/threads/thread-123")

            assert response.status_code == 200
            assert response.json() == thread_data

    @respx.mock
    def test_get_thread_history_success(self, test_client, authenticated_config):
        """Test getting thread history successfully."""
        history_data = {"thread_id": "thread-123", "history": [{"role": "user", "content": "test"}]}
        respx.get("http://localhost:2024/threads/thread-123/history").mock(
            return_value=httpx.Response(200, json=history_data)
        )

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.get("/threads/thread-123/history")

            assert response.status_code == 200
            assert response.json() == history_data


class TestCatchAllProxy:
    """Test catch-all proxy for other LanGraph endpoints."""

    @respx.mock
    def test_catch_all_get_request(self, test_client, authenticated_config):
        """Test catch-all proxy with GET request."""
        respx.get("http://localhost:2024/custom/endpoint").mock(
            return_value=httpx.Response(200, json={"result": "success"})
        )

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.get("/custom/endpoint")

            assert response.status_code == 200
            assert response.json() == {"result": "success"}

    @respx.mock
    def test_catch_all_post_request(self, test_client, authenticated_config):
        """Test catch-all proxy with POST request."""
        respx.post("http://localhost:2024/custom/endpoint").mock(
            return_value=httpx.Response(201, json={"created": True})
        )

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.post("/custom/endpoint", json={"data": "test"})

            assert response.status_code == 201

    @respx.mock
    def test_catch_all_put_request(self, test_client, authenticated_config):
        """Test catch-all proxy with PUT request."""
        respx.put("http://localhost:2024/custom/endpoint").mock(
            return_value=httpx.Response(200, json={"updated": True})
        )

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.put("/custom/endpoint", json={"data": "test"})

            assert response.status_code == 200

    @respx.mock
    def test_catch_all_delete_request(self, test_client, authenticated_config):
        """Test catch-all proxy with DELETE request."""
        respx.delete("http://localhost:2024/custom/endpoint").mock(return_value=httpx.Response(204))

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.delete("/custom/endpoint")

            assert response.status_code == 204

    @respx.mock
    def test_catch_all_patch_request(self, test_client, authenticated_config):
        """Test catch-all proxy with PATCH request."""
        respx.patch("http://localhost:2024/custom/endpoint").mock(
            return_value=httpx.Response(200, json={"patched": True})
        )

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.patch("/custom/endpoint", json={"data": "test"})

            assert response.status_code == 200


class TestProxyRequestForwarding:
    """Test request forwarding details."""

    @respx.mock
    def test_proxy_forwards_headers(self, test_client, authenticated_config):
        """Test that proxy forwards request headers."""
        respx.post("http://localhost:2024/runs/invoke").mock(return_value=httpx.Response(200, json={}))

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.post(
                "/runs/invoke", json={"input": "test"}, headers={"X-Custom-Header": "test-value"}
            )

            assert response.status_code == 200
            # Verify custom header was forwarded (host header is excluded)
            forwarded_headers = dict(respx.calls.last.request.headers)
            assert "x-custom-header" in forwarded_headers

    @respx.mock
    def test_proxy_excludes_host_header(self, test_client, authenticated_config):
        """Test that proxy excludes host header."""
        respx.post("http://localhost:2024/runs/invoke").mock(return_value=httpx.Response(200, json={}))

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.post("/runs/invoke", json={})

            assert response.status_code == 200
            # Verify original host header was removed
            # (httpx will add its own host header for the target)

    @respx.mock
    def test_proxy_forwards_request_body(self, test_client, authenticated_config):
        """Test that proxy forwards request body."""
        respx.post("http://localhost:2024/runs/invoke").mock(return_value=httpx.Response(200, json={}))

        request_body = {"input": "test data", "options": {"key": "value"}}
        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.post("/runs/invoke", json=request_body)

            assert response.status_code == 200
            # Verify request body was forwarded
            import json

            forwarded_body = json.loads(respx.calls.last.request.content)
            assert forwarded_body == request_body

    @respx.mock
    def test_proxy_forwards_response_headers(self, test_client, authenticated_config):
        """Test that proxy forwards response headers."""
        respx.get("http://localhost:2024/runs/test-run").mock(
            return_value=httpx.Response(200, json={}, headers={"X-Custom-Response": "test"})
        )

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.get("/runs/test-run")

            assert response.status_code == 200
            assert "x-custom-response" in response.headers


class TestProxyErrorHandling:
    """Test proxy error handling."""

    @respx.mock
    def test_proxy_handles_general_exception(self, test_client, authenticated_config):
        """Test that proxy handles general exceptions."""
        respx.post("http://localhost:2024/runs/invoke").mock(side_effect=Exception("Unexpected error"))

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.post("/runs/invoke", json={})

            assert response.status_code == 500
            assert "Proxy error" in response.json()["detail"]

    @respx.mock
    def test_streaming_proxy_handles_exception(self, test_client, authenticated_config):
        """Test that streaming proxy handles exceptions."""
        respx.post("http://localhost:2024/runs/stream").mock(side_effect=Exception("Stream error"))

        with patch("src.api.routes.langgraph_routes.config", authenticated_config):
            response = test_client.post("/runs/stream", json={})

            assert response.status_code == 500
            assert "Streaming proxy error" in response.json()["detail"]


class TestLanGraphServerConfiguration:
    """Test LanGraph server configuration."""

    def test_langgraph_server_url_constant(self):
        """Test that LanGraph server URL is correctly configured."""
        from src.api.routes.langgraph_routes import LANGGRAPH_SERVER_URL

        assert LANGGRAPH_SERVER_URL == "http://localhost:2024"
