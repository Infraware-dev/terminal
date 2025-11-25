"""Integration tests for main FastAPI application."""

import pytest
import respx


class TestRootEndpoint:
    """Test root endpoint (/)."""

    def test_root_returns_200(self, test_client):
        """Test that root endpoint returns 200 status."""
        response = test_client.get("/")
        assert response.status_code == 200

    def test_root_returns_json(self, test_client):
        """Test that root endpoint returns JSON."""
        response = test_client.get("/")
        assert response.headers["content-type"] == "application/json"

    def test_root_has_api_info(self, test_client):
        """Test that root endpoint returns API information."""
        response = test_client.get("/")
        data = response.json()

        assert "name" in data
        assert data["name"] == "Infraware Terminal API"
        assert "version" in data
        assert data["version"] == "0.1.0"

    def test_root_has_endpoints_list(self, test_client):
        """Test that root endpoint lists available endpoints."""
        response = test_client.get("/")
        data = response.json()

        assert "endpoints" in data
        endpoints = data["endpoints"]

        assert "auth" in endpoints
        assert "get_auth" in endpoints
        assert "langgraph" in endpoints

    def test_root_endpoint_structure(self, test_client):
        """Test complete root endpoint response structure."""
        response = test_client.get("/")
        data = response.json()

        # Check all expected keys exist
        assert set(data.keys()) == {"name", "version", "endpoints"}

        # Check endpoint values
        assert data["endpoints"]["auth"] == "/api/auth"
        assert data["endpoints"]["get_auth"] == "/api/get-auth"
        assert "proxied" in data["endpoints"]["langgraph"].lower()


class TestHealthEndpoint:
    """Test health check endpoint (/health)."""

    def test_health_returns_200(self, test_client):
        """Test that health endpoint returns 200 status."""
        response = test_client.get("/health")
        assert response.status_code == 200

    def test_health_returns_json(self, test_client):
        """Test that health endpoint returns JSON."""
        response = test_client.get("/health")
        assert response.headers["content-type"] == "application/json"

    def test_health_returns_healthy_status(self, test_client):
        """Test that health endpoint returns healthy status."""
        response = test_client.get("/health")
        data = response.json()

        assert "status" in data
        assert data["status"] == "healthy"

    def test_health_response_structure(self, test_client):
        """Test complete health endpoint response structure."""
        response = test_client.get("/health")
        data = response.json()

        assert data == {"status": "healthy"}


class TestCORSMiddleware:
    """Test CORS middleware configuration."""

    def test_cors_headers_present(self, test_client):
        """Test that CORS headers are present in response."""
        # TestClient requires Origin header for CORS middleware to activate
        response = test_client.get("/", headers={"Origin": "http://localhost:3000"})

        # Check for CORS headers
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "*"

    def test_cors_allows_credentials(self, test_client):
        """Test that CORS allows credentials."""
        response = test_client.options(
            "/api/auth", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"}
        )

        assert "access-control-allow-credentials" in response.headers
        assert response.headers["access-control-allow-credentials"] == "true"

    def test_cors_preflight_request(self, test_client):
        """Test CORS preflight OPTIONS request."""
        response = test_client.options(
            "/api/auth",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        assert response.status_code == 200
        assert "access-control-allow-methods" in response.headers
        assert "access-control-allow-headers" in response.headers


class TestAppMetadata:
    """Test FastAPI app metadata."""

    def test_openapi_schema_available(self, test_client):
        """Test that OpenAPI schema is available."""
        response = test_client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema

    def test_app_title_in_schema(self, test_client):
        """Test that app title is correct in OpenAPI schema."""
        response = test_client.get("/openapi.json")
        schema = response.json()

        assert schema["info"]["title"] == "Infraware Terminal API"
        assert schema["info"]["version"] == "0.1.0"
        assert "description" in schema["info"]

    def test_docs_endpoint_available(self, test_client):
        """Test that API docs endpoint is available."""
        response = test_client.get("/docs")
        assert response.status_code == 200


class TestRouterInclusion:
    """Test that routers are properly included."""

    def test_auth_routes_included(self, test_client):
        """Test that auth routes are included."""
        # Test that auth endpoints exist
        response = test_client.get("/api/get-auth")
        # Should not return 404
        assert response.status_code != 404

    @respx.mock
    def test_langgraph_routes_included(self, test_client):
        """Test that langgraph routes are included."""
        # Test that a langgraph thread endpoint exists (will fail auth)
        response = test_client.post("/threads", json={})
        # Should return 401 (auth error), not 404 (not found)
        assert response.status_code == 401
