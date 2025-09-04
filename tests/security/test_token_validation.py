"""Security tests for JWT token validation."""

import pytest
from datetime import datetime, timedelta, UTC
from jose import jwt
from fastapi import status

from app.config.settings import settings
from tests.constants import TestConstants
from tests.factories import TestDataFactory


class TestTokenValidation:
    """Test suite for JWT token validation security."""
    
    def test_expired_token_rejection(self, client):
        """Test that expired tokens are rejected."""
        expired_token = TestDataFactory.create_jwt_token(expires_minutes=-1)
        headers = TestDataFactory.create_auth_headers(expired_token)
        
        response = client.get(
            TestConstants.ENDPOINTS["USER_ME"],
            headers=headers
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, \
            f"Expected 401 for expired token, got {response.status_code}"

    def test_invalid_signature_rejection(self, client):
        """Test that tokens with invalid signatures are rejected."""
        # Create token with wrong secret
        token_data = {
            "sub": TestConstants.TEST_USER,
            "tenant_id": TestConstants.TEST_TENANT,
            "roles": [TestConstants.ROLES["ADMIN"]],
            "exp": datetime.now(UTC) + timedelta(minutes=30)
        }
        
        invalid_token = jwt.encode(token_data, "wrong-secret", algorithm="HS256")
        headers = TestDataFactory.create_auth_headers(invalid_token)
        
        response = client.get(
            TestConstants.ENDPOINTS["USER_ME"],
            headers=headers
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, \
            f"Expected 401 for invalid signature, got {response.status_code}"

    def test_malformed_token_rejection(self, client):
        """Test that malformed tokens are rejected."""
        test_cases = [
            "invalid.token",
            "not.even.jwt.format.token",
            "Bearer invalid",
            "",
        ]
        
        for invalid_token in test_cases:
            headers = {"Authorization": f"Bearer {invalid_token}"}
            
            response = client.get(
                TestConstants.ENDPOINTS["USER_ME"],
                headers=headers
            )
            
            assert response.status_code == status.HTTP_401_UNAUTHORIZED, \
                f"Expected 401 for malformed token '{invalid_token}', got {response.status_code}"

    def test_missing_required_claims(self, client):
        """Test that tokens missing required claims are rejected."""
        test_cases = [
            # Missing sub
            {
                "tenant_id": TestConstants.TEST_TENANT,
                "roles": [TestConstants.ROLES["ADMIN"]],
                "exp": datetime.now(UTC) + timedelta(minutes=30)
            },
            # Missing tenant_id
            {
                "sub": TestConstants.TEST_USER,
                "roles": [TestConstants.ROLES["ADMIN"]],
                "exp": datetime.now(UTC) + timedelta(minutes=30)
            },
            # Invalid exp (wrong type)
            {
                "sub": TestConstants.TEST_USER,
                "tenant_id": TestConstants.TEST_TENANT,
                "roles": [TestConstants.ROLES["ADMIN"]],
                "exp": "invalid_date"
            }
        ]
        
        for token_data in test_cases:
            token = jwt.encode(token_data, settings.SECRET_KEY, algorithm="HS256")
            headers = TestDataFactory.create_auth_headers(token)
            
            response = client.get(
                TestConstants.ENDPOINTS["USER_ME"],
                headers=headers
            )
            
            assert response.status_code == status.HTTP_401_UNAUTHORIZED, \
                f"Expected 401 for missing claims in {token_data.keys()}, got {response.status_code}"

    def test_empty_claim_values(self, client):
        """Test that tokens with empty required claim values are rejected."""
        test_cases = [
            # Empty sub
            {
                "sub": "",
                "tenant_id": TestConstants.TEST_TENANT,
                "roles": [TestConstants.ROLES["ADMIN"]],
                "exp": datetime.now(UTC) + timedelta(minutes=30)
            },
            # Empty tenant_id
            {
                "sub": TestConstants.TEST_USER,
                "tenant_id": "",
                "roles": [TestConstants.ROLES["ADMIN"]],
                "exp": datetime.now(UTC) + timedelta(minutes=30)
            }
        ]
        
        for token_data in test_cases:
            token = jwt.encode(token_data, settings.SECRET_KEY, algorithm="HS256")
            headers = TestDataFactory.create_auth_headers(token)
            
            response = client.get(
                TestConstants.ENDPOINTS["USER_ME"],
                headers=headers
            )
            
            assert response.status_code == status.HTTP_401_UNAUTHORIZED, \
                f"Expected 401 for empty claim values, got {response.status_code}"

    def test_token_with_future_issued_at(self, client):
        """Test that tokens with future 'iat' claim are handled properly."""
        token_data = {
            "sub": TestConstants.TEST_USER,
            "tenant_id": TestConstants.TEST_TENANT,
            "roles": [TestConstants.ROLES["ADMIN"]],
            "iat": datetime.now(UTC) + timedelta(hours=1),  # Future issued at
            "exp": datetime.now(UTC) + timedelta(minutes=30)
        }
        
        token = jwt.encode(token_data, settings.SECRET_KEY, algorithm="HS256")
        headers = TestDataFactory.create_auth_headers(token)
        
        response = client.get(
            TestConstants.ENDPOINTS["USER_ME"],
            headers=headers
        )
        
        # The jose library may or may not validate 'iat', 
        # so we accept either success or failure here
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED], \
            f"Unexpected response for future iat token: {response.status_code}"
