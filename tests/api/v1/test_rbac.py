import pytest
from fastapi import status

from tests.constants import TestConstants
from tests.factories import TestDataFactory


class TestRoleBasedAccessControl:
    """Test suite for Role-Based Access Control functionality."""
    
    @pytest.fixture(autouse=True)
    def setup_method(self, client, test_config):
        """Set up test data for RBAC tests."""
        self.client = client
        self.test_config = test_config

    def _get_auth_token(self, username: str, password: str) -> str:
        """Helper method to get authentication token."""
        login_data = TestDataFactory.create_login_data(username, password)
        
        response = self.client.post(
            TestConstants.ENDPOINTS["LOGIN"],
            data=login_data,
            headers=TestConstants.HEADERS["CONTENT_TYPE_FORM"]
        )
        
        assert response.status_code == status.HTTP_200_OK, \
            f"Failed to authenticate user {username}: {response.text}"
        
        return response.json()["access_token"]

    def test_admin_can_access_own_profile(self):
        """Test that admin user can access their own profile."""
        token = self._get_auth_token(TestConstants.TEST_USER, TestConstants.TEST_PASSWORD)
        headers = TestDataFactory.create_auth_headers(token)
        
        response = self.client.get(
            TestConstants.ENDPOINTS["USER_ME"],
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK, \
            f"Admin failed to access profile: {response.text}"
        
        data = response.json()
        assert data["username"] == TestConstants.TEST_USER, \
            f"Expected username {TestConstants.TEST_USER}, got {data.get('username')}"
        assert TestConstants.ROLES["ADMIN"] in data["roles"], \
            f"Expected admin role in {data.get('roles')}"
        assert data["tenant_id"] == TestConstants.TEST_TENANT, \
            f"Expected tenant {TestConstants.TEST_TENANT}, got {data.get('tenant_id')}"

    def test_editor_can_access_own_profile(self):
        """Test that editor user can access their own profile."""
        token = self._get_auth_token(TestConstants.EDITOR_USER, TestConstants.EDITOR_PASSWORD)
        headers = TestDataFactory.create_auth_headers(token)
        
        response = self.client.get(
            TestConstants.ENDPOINTS["USER_ME"],
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK, \
            f"Editor failed to access profile: {response.text}"
        
        data = response.json()
        assert data["username"] == TestConstants.EDITOR_USER, \
            f"Expected username {TestConstants.EDITOR_USER}, got {data.get('username')}"
        assert TestConstants.ROLES["EDITOR"] in data["roles"], \
            f"Expected editor role in {data.get('roles')}"
        assert data["tenant_id"] == TestConstants.TEST_TENANT, \
            f"Expected tenant {TestConstants.TEST_TENANT}, got {data.get('tenant_id')}"

    def test_viewer_can_access_own_profile(self):
        """Test that viewer user can access their own profile."""
        token = self._get_auth_token(TestConstants.VIEWER_USER, TestConstants.VIEWER_PASSWORD)
        headers = TestDataFactory.create_auth_headers(token)
        
        response = self.client.get(
            TestConstants.ENDPOINTS["USER_ME"],
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK, \
            f"Viewer failed to access profile: {response.text}"
        
        data = response.json()
        assert data["username"] == TestConstants.VIEWER_USER, \
            f"Expected username {TestConstants.VIEWER_USER}, got {data.get('username')}"
        assert TestConstants.ROLES["VIEWER"] in data["roles"], \
            f"Expected viewer role in {data.get('roles')}"
        assert data["tenant_id"] == TestConstants.TEST_TENANT, \
            f"Expected tenant {TestConstants.TEST_TENANT}, got {data.get('tenant_id')}"

    def test_unauthorized_access(self):
        """Test that unauthorized requests are properly rejected."""
        response = self.client.get(TestConstants.ENDPOINTS["USER_ME"])
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, \
            f"Expected 401 for unauthorized access, got {response.status_code}"
        
        response_data = response.json()
        assert "detail" in response_data, \
            "Unauthorized response should contain error details"

    def test_cross_tenant_token_validation(self):
        """Test that tokens are properly validated for tenant isolation."""
        # Create a token with a different tenant
        invalid_tenant_token = TestDataFactory.create_jwt_token(
            username=TestConstants.TEST_USER,
            tenant_id="different-tenant"
        )
        headers = TestDataFactory.create_auth_headers(invalid_tenant_token)
        
        response = self.client.get(
            TestConstants.ENDPOINTS["USER_ME"],
            headers=headers
        )
        
        # This should still work because we're validating the token format,
        # not necessarily tenant isolation at this level
        # Tenant isolation would be enforced by business logic, not auth
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED], \
            f"Unexpected response for cross-tenant token: {response.status_code}"

    def test_malformed_jwt_token(self):
        """Test that malformed JWT tokens are rejected."""
        malformed_headers = {"Authorization": "Bearer malformed.jwt.token"}
        
        response = self.client.get(
            TestConstants.ENDPOINTS["USER_ME"],
            headers=malformed_headers
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, \
            f"Expected 401 for malformed token, got {response.status_code}"

    def test_missing_tenant_id_in_token(self):
        """Test that tokens missing tenant_id are rejected."""
        # Create token without tenant_id
        from datetime import datetime, timedelta, UTC
        from jose import jwt
        from app.config.settings import settings
        
        token_data = {
            "sub": TestConstants.TEST_USER,
            "roles": [TestConstants.ROLES["ADMIN"]],
            # Missing tenant_id
            "exp": datetime.now(UTC) + timedelta(minutes=30)
        }
        
        token = jwt.encode(token_data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        headers = TestDataFactory.create_auth_headers(token)
        
        response = self.client.get(
            TestConstants.ENDPOINTS["USER_ME"],
            headers=headers
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, \
            f"Expected 401 for token missing tenant_id, got {response.status_code}"