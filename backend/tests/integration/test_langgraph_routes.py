"""Integration tests for LanGraph proxy routes."""

from unittest.mock import patch

import httpx
import pytest
import respx


class TestAuthenticationRequired:
    """Test that all thread endpoints require authentication."""

    @respx.mock
    def test_create_thread_requires_auth(self, test_client, mock_config):
        """Test POST /threads requires authentication."""
        with patch("src.api.routes.langgraph_routes.config", mock_config):
            response = test_client.post("/threads", json={})
            assert response.status_code == 401
            assert "Not authenticated" in response.json()["detail"]

    @respx.mock
    def test_get_thread_requires_auth(self, test_client, mock_config):
        """Test GET /threads/{thread_id} requires authentication."""
        with patch("src.api.routes.langgraph_routes.config", mock_config):
            response = test_client.get("/threads/test-thread-id")
            assert response.status_code == 401

    @respx.mock
    def test_get_thread_history_requires_auth(self, test_client, mock_config):
        """Test GET /threads/{thread_id}/history requires authentication."""
        with patch("src.api.routes.langgraph_routes.config", mock_config):
            response = test_client.get("/threads/test-thread-id/history")
            assert response.status_code == 401


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
