import pytest
from fastapi.testclient import TestClient
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

    def test_create_application_missing_config_file_raises(self, monkeypatch):
        """Test startup fails with missing config file."""
        from tiny_gateway.main import ConfigLoadError, create_application

        monkeypatch.setenv("CONFIG_FILE", "/tmp/definitely-missing-config.yml")
        with pytest.raises(ConfigLoadError, match="file not found"):
            create_application()

    def test_create_application_invalid_yaml_raises(self, tmp_path, monkeypatch):
        """Test startup fails with malformed YAML config."""
        from tiny_gateway.main import ConfigLoadError, create_application

        broken_config = tmp_path / "broken-config.yml"
        broken_config.write_text("tenants: [\n", encoding="utf-8")

        monkeypatch.setenv("CONFIG_FILE", str(broken_config))
        with pytest.raises(ConfigLoadError, match="invalid YAML syntax"):
            create_application()

    def test_create_application_uses_packaged_default_config_outside_repo_cwd(self, tmp_path, monkeypatch):
        """Test app starts from arbitrary cwd when CONFIG_FILE is not set."""
        from tiny_gateway.main import create_application

        monkeypatch.delenv("CONFIG_FILE", raising=False)
        monkeypatch.chdir(tmp_path)

        app = create_application()
        with TestClient(app) as local_client:
            response = local_client.get("/health")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "healthy"}

    def test_test_login_uses_packaged_html_outside_repo_cwd(self, tmp_path, monkeypatch):
        """Test login page is served from package resources regardless of cwd."""
        from tiny_gateway.main import create_application

        monkeypatch.delenv("CONFIG_FILE", raising=False)
        monkeypatch.chdir(tmp_path)

        app = create_application()
        with TestClient(app) as local_client:
            response = local_client.get("/test_login")

        assert response.status_code == status.HTTP_200_OK
        assert "Tiny Gateway - Login" in response.text
