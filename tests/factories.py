"""Test data factories for creating test objects."""

from datetime import datetime, timedelta, UTC
from typing import List, Optional
from jose import jwt

from app.models.config_models import User, Tenant, ProxyConfig, Permission
from app.config.settings import settings
from tests.constants import TestConstants


class TestDataFactory:
    """Factory for creating test data objects."""
    
    @staticmethod
    def create_user(
        name: str = TestConstants.TEST_USER,
        password: str = TestConstants.TEST_PASSWORD,
        tenant_id: str = TestConstants.TEST_TENANT,
        roles: Optional[List[str]] = None
    ) -> User:
        """Create a test user."""
        return User(
            name=name,
            password=password,
            tenant_id=tenant_id,
            roles=roles or [TestConstants.ROLES["ADMIN"]]
        )
    
    @staticmethod
    def create_tenant(tenant_id: str = TestConstants.TEST_TENANT) -> Tenant:
        """Create a test tenant."""
        return Tenant(id=tenant_id)
    
    @staticmethod
    def create_proxy_config(
        endpoint: str = "/api/v1/test",
        target: str = "http://test-server/",
        change_origin: bool = True
    ) -> ProxyConfig:
        """Create a test proxy configuration."""
        return ProxyConfig(
            endpoint=endpoint,
            target=target,
            rewrite="",
            change_origin=change_origin
        )
    
    @staticmethod
    def create_permission(
        resource: str = "*",
        actions: Optional[List[str]] = None
    ) -> Permission:
        """Create a test permission."""
        return Permission(resource=resource, actions=actions or ["read", "write"])
    
    @staticmethod
    def create_jwt_token(
        username: str = TestConstants.TEST_USER,
        tenant_id: str = TestConstants.TEST_TENANT,
        roles: Optional[List[str]] = None,
        expires_minutes: int = 30
    ) -> str:
        """Create a JWT token for testing."""
        token_data = {
            "sub": username,
            "roles": roles or [TestConstants.ROLES["ADMIN"]],
            "tenant_id": tenant_id,
            "exp": datetime.now(UTC) + timedelta(minutes=expires_minutes)
        }
        
        return jwt.encode(
            token_data,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
    
    @staticmethod
    def create_auth_headers(token: Optional[str] = None) -> dict:
        """Create authorization headers with JWT token."""
        return {"Authorization": f"Bearer {token or TestDataFactory.create_jwt_token()}"}
    
    @staticmethod
    def create_login_data(
        username: str = TestConstants.TEST_USER,
        password: str = TestConstants.TEST_PASSWORD
    ) -> dict:
        """Create login form data."""
        return {
            "username": username,
            "password": password
        }
