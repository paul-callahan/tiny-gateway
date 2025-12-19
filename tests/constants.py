"""Test constants and configuration for the test suite."""

from fastapi import status


class TestConstants:
    """Test constants for consistent test data."""
    
    # Test users
    TEST_USER = "testuser"
    TEST_PASSWORD = "testpass"
    TEST_TENANT = "test-tenant"
    
    EDITOR_USER = "editor_user"
    EDITOR_PASSWORD = "editorpass"
    
    VIEWER_USER = "viewer_user"
    VIEWER_PASSWORD = "viewerpass"

    LIMITED_USER = "limited_user"
    LIMITED_PASSWORD = "limitedpass"
    
    # API endpoints
    ENDPOINTS = {
        "LOGIN": "/api/v1/auth/login",
        "USER_ME": "/api/v1/users/me",
        "HEALTH": "/health",
    }
    
    # HTTP headers
    HEADERS = {
        "CONTENT_TYPE_FORM": {"Content-Type": "application/x-www-form-urlencoded"},
        "CONTENT_TYPE_JSON": {"Content-Type": "application/json"},
    }
    
    # Test roles
    ROLES = {
        "ADMIN": "admin",
        "EDITOR": "editor", 
        "VIEWER": "viewer",
        "LIMITED": "limited",
    }
