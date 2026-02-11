import pytest
from fastapi import status

from tests.constants import TestConstants
from tests.factories import TestDataFactory


class TestUsers:
    """Test suite for user-related endpoints."""
    
    def test_get_current_user_success(self, client, auth_headers, test_config):
        """Test getting current user information with valid authentication."""
        test_user = test_config.users[0]
        
        response = client.get(
            TestConstants.ENDPOINTS["USER_ME"],
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK, \
            f"Failed to get current user, status: {response.status_code}, response: {response.text}"
        
        data = response.json()
        assert data["username"] == test_user.name, \
            f"Expected username '{test_user.name}', got '{data.get('username')}'"
        assert set(data["roles"]) == set(test_user.roles), \
            f"Expected roles {test_user.roles}, got {data.get('roles')}"
        assert data["tenant_id"] == test_user.tenant_id, \
            f"Expected tenant_id '{test_user.tenant_id}', got '{data.get('tenant_id')}'"

    def test_get_current_user_unauthorized(self, client):
        """Test getting current user without authentication."""
        response = client.get(TestConstants.ENDPOINTS["USER_ME"])
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, \
            f"Expected 401 for unauthorized request, got {response.status_code}"
        
        response_data = response.json()
        assert "detail" in response_data, \
            "Error response should contain 'detail' field"

    def test_get_current_user_invalid_token(self, client):
        """Test getting current user with invalid token."""
        invalid_headers = {"Authorization": "Bearer invalid_token"}
        
        response = client.get(
            TestConstants.ENDPOINTS["USER_ME"],
            headers=invalid_headers
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, \
            f"Expected 401 for invalid token, got {response.status_code}"

    def test_get_current_user_malformed_header(self, client):
        """Test getting current user with malformed authorization header."""
        malformed_headers = {"Authorization": "InvalidFormat token"}
        
        response = client.get(
            TestConstants.ENDPOINTS["USER_ME"],
            headers=malformed_headers
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, \
            f"Expected 401 for malformed auth header, got {response.status_code}"

    def test_get_current_user_expired_token(self, client):
        """Test getting current user with expired token."""
        # Create an expired token
        expired_token = TestDataFactory.create_jwt_token(expires_minutes=-1)
        expired_headers = TestDataFactory.create_auth_headers(expired_token)
        
        response = client.get(
            TestConstants.ENDPOINTS["USER_ME"],
            headers=expired_headers
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, \
            f"Expected 401 for expired token, got {response.status_code}"

    def test_get_current_user_not_found(self):
        """Test 404 when token user payload is valid but user no longer exists in config."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.v1.endpoints import users as users_endpoint
        from app.api.deps import get_config, get_current_active_user
        from app.models.config_models import AppConfig
        from app.models.schemas import TokenPayload

        app = FastAPI()
        app.include_router(users_endpoint.router, prefix="/api/v1/users")

        config = AppConfig.from_dict(
            {
                "tenants": [{"id": "test-tenant"}],
                "users": [
                    {
                        "name": "existing-user",
                        "password": "pass",
                        "tenant_id": "test-tenant",
                        "roles": ["admin"],
                    }
                ],
                "roles": {"admin": [{"resource": "*", "actions": ["read"]}]},
                "proxy": [],
            }
        )

        app.dependency_overrides[get_config] = lambda: config
        app.dependency_overrides[get_current_active_user] = lambda: TokenPayload(
            sub="missing-user",
            roles=["admin"],
            tenant_id="test-tenant",
        )

        with TestClient(app) as local_client:
            response = local_client.get("/api/v1/users/me")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "User not found"
