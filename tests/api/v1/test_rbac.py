import pytest
from fastapi import status, HTTPException
from fastapi.testclient import TestClient
from app.main import app
from app.models.config_models import AppConfig, User, Tenant, ProxyConfig, Permission
from app.models.schemas import UserResponse
from app.core.security import get_current_active_user, get_current_user

# Test data
TEST_USER = "testuser"
TEST_PASSWORD = "testpass"
TEST_TENANT = "test-tenant"

# Helper function to get auth token
def get_auth_token(client, username, password):
    print(f"\n=== Attempting to log in user: {username} ===")
    print(f"Using password: {password}")
    
    response = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    print(f"Response status: {response.status_code}")
    print(f"Response content: {response.text}")
    
    if response.status_code != status.HTTP_200_OK:
        print(f"Login failed for user: {username}")
        print(f"Response headers: {response.headers}")
    
    assert response.status_code == status.HTTP_200_OK, f"Login failed for {username}"
    return response.json()["access_token"]

# Test cases for RBAC
class TestRBAC:
    @pytest.fixture(autouse=True)
    def setup_method(self, client, test_config):
        self.client = client
        self.test_config = test_config
        
        # Print debug info
        print("\n=== Test Configuration ===")
        print(f"Tenants: {[t.id for t in test_config.tenants]}")
        print("Users:")
        for user in test_config.users:
            print(f"  - {user.name} (roles: {user.roles}, tenant_id: {user.tenant_id}")
        
        # Get auth token for the test user
        self.token = get_auth_token(self.client, TEST_USER, TEST_PASSWORD)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def test_admin_can_access_own_profile(self):
        # Test admin can access their own profile
        response = self.client.get(
            "/api/v1/users/me",
            headers=self.headers
        )
        print(f"\n=== Test Response ===")
        print(f"Status: {response.status_code}")
        print(f"Body: {response.text}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["username"] == TEST_USER
        assert "admin" in data["roles"]
        assert data["tenant_id"] == TEST_TENANT

    def test_editor_can_access_own_profile(self):
        # Test editor can access their own profile
        editor_token = get_auth_token(
            self.client,
            "editor_user",
            "editorpass"
        )
        
        response = self.client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {editor_token}"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["username"] == "editor_user"
        assert "editor" in data["roles"]
        assert data["tenant_id"] == TEST_TENANT

    def test_viewer_can_access_own_profile(self):
        # Test viewer can access their own profile
        viewer_token = get_auth_token(
            self.client,
            "viewer_user",
            "viewerpass"
        )
        
        response = self.client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {viewer_token}"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["username"] == "viewer_user"
        assert "viewer" in data["roles"]
        assert data["tenant_id"] == TEST_TENANT

    def test_unauthorized_access(self):
        # Test unauthorized access without token
        response = self.client.get("/api/v1/users/me")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # Test with invalid token
        response = self.client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
