import pytest
from fastapi import status

from tests.constants import TestConstants


class TestMainEndpoints:
    """Test suite for main application endpoints."""
    
    def test_health_check_success(self, client):
        """Test health check endpoint returns correct status."""
        response = client.get(TestConstants.ENDPOINTS["HEALTH"])
        
        assert response.status_code == status.HTTP_200_OK, \
            f"Health check failed with status {response.status_code}: {response.text}"
        
        response_data = response.json()
        assert response_data == {"status": "healthy"}, \
            f"Expected health status, got: {response_data}"

    def test_test_login_endpoint_serves_login_page(self, client):
        """Test /test_login endpoint serves the login page HTML file."""
        response = client.get("/test_login")
        
        assert response.status_code == status.HTTP_200_OK, \
            f"Expected 200 for test_login endpoint, got {response.status_code}"
        
        # Check that it returns HTML content
        assert response.headers.get("content-type") == "text/html; charset=utf-8", \
            f"Expected HTML content type, got {response.headers.get('content-type')}"
        
        # Check for some expected content in the HTML
        content = response.text
        assert "Tiny Gateway - Login" in content, "HTML should contain the page title"
        assert "login" in content.lower(), "HTML should contain login-related content"

    def test_root_endpoint_not_found(self, client):
        """Test root endpoint returns 404 now that login page moved."""
        response = client.get("/")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND, \
            f"Expected 404 for root endpoint, got {response.status_code}"

    def test_nonexistent_route_not_found(self, client):
        """Test non-existent route returns 404."""
        response = client.get("/nonexistent-route")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND, \
            f"Expected 404 for non-existent route, got {response.status_code}"
    
    def test_health_check_response_format(self, client):
        """Test health check response has correct format."""
        response = client.get(TestConstants.ENDPOINTS["HEALTH"])
        
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        
        assert isinstance(response_data, dict), "Health check should return a dictionary"
        assert "status" in response_data, "Health check should contain 'status' field"
        assert response_data["status"] == "healthy", "Status should be 'healthy'"
