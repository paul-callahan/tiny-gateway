"""Integration tests for complete authentication flows."""

import pytest
from fastapi import status

from tests.constants import TestConstants
from tests.factories import TestDataFactory


class TestAuthenticationFlow:
    """Integration tests for complete authentication workflows."""
    
    def test_complete_login_and_profile_access_flow(self, client, test_config):
        """Test complete flow from login to accessing protected resources."""
        test_user = test_config.users[0]
        
        # Step 1: Login
        login_data = TestDataFactory.create_login_data(
            username=test_user.name,
            password=test_user.password
        )
        
        login_response = client.post(
            TestConstants.ENDPOINTS["LOGIN"],
            data=login_data,
            headers=TestConstants.HEADERS["CONTENT_TYPE_FORM"]
        )
        
        assert login_response.status_code == status.HTTP_200_OK, \
            f"Login failed: {login_response.text}"
        
        login_data = login_response.json()
        assert "access_token" in login_data
        token = login_data["access_token"]
        
        # Step 2: Access protected resource
        headers = TestDataFactory.create_auth_headers(token)
        
        profile_response = client.get(
            TestConstants.ENDPOINTS["USER_ME"],
            headers=headers
        )
        
        assert profile_response.status_code == status.HTTP_200_OK, \
            f"Profile access failed: {profile_response.text}"
        
        profile_data = profile_response.json()
        assert profile_data["username"] == test_user.name
        assert profile_data["tenant_id"] == test_user.tenant_id
        assert set(profile_data["roles"]) == set(test_user.roles)

    def test_multiple_user_authentication_flow(self, client, test_config):
        """Test that multiple users can authenticate independently."""
        users_to_test = [
            (TestConstants.TEST_USER, TestConstants.TEST_PASSWORD),
            (TestConstants.EDITOR_USER, TestConstants.EDITOR_PASSWORD),
            (TestConstants.VIEWER_USER, TestConstants.VIEWER_PASSWORD)
        ]
        
        tokens = {}
        
        # Authenticate all users
        for username, password in users_to_test:
            login_data = TestDataFactory.create_login_data(username, password)
            
            response = client.post(
                TestConstants.ENDPOINTS["LOGIN"],
                data=login_data,
                headers=TestConstants.HEADERS["CONTENT_TYPE_FORM"]
            )
            
            assert response.status_code == status.HTTP_200_OK, \
                f"Failed to authenticate {username}: {response.text}"
            
            tokens[username] = response.json()["access_token"]
        
        # Verify each user can access their own profile
        for username, token in tokens.items():
            headers = TestDataFactory.create_auth_headers(token)
            
            response = client.get(
                TestConstants.ENDPOINTS["USER_ME"],
                headers=headers
            )
            
            assert response.status_code == status.HTTP_200_OK, \
                f"Failed to access profile for {username}: {response.text}"
            
            profile_data = response.json()
            assert profile_data["username"] == username, \
                f"Token returned wrong user: expected {username}, got {profile_data['username']}"

    def test_token_reuse_across_requests(self, client, test_config):
        """Test that tokens can be reused across multiple requests."""
        test_user = test_config.users[0]
        
        # Get token
        login_data = TestDataFactory.create_login_data(
            username=test_user.name,
            password=test_user.password
        )
        
        login_response = client.post(
            TestConstants.ENDPOINTS["LOGIN"],
            data=login_data,
            headers=TestConstants.HEADERS["CONTENT_TYPE_FORM"]
        )
        
        token = login_response.json()["access_token"]
        headers = TestDataFactory.create_auth_headers(token)
        
        # Make multiple requests with same token
        for i in range(3):
            response = client.get(
                TestConstants.ENDPOINTS["USER_ME"],
                headers=headers
            )
            
            assert response.status_code == status.HTTP_200_OK, \
                f"Request {i+1} failed with reused token: {response.text}"
            
            profile_data = response.json()
            assert profile_data["username"] == test_user.name

    def test_failed_login_does_not_affect_subsequent_attempts(self, client, test_config):
        """Test that failed login attempts don't block subsequent valid attempts."""
        test_user = test_config.users[0]
        
        # Make failed login attempt
        invalid_login_data = TestDataFactory.create_login_data(
            username=test_user.name,
            password="wrong_password"
        )
        
        failed_response = client.post(
            TestConstants.ENDPOINTS["LOGIN"],
            data=invalid_login_data,
            headers=TestConstants.HEADERS["CONTENT_TYPE_FORM"]
        )
        
        assert failed_response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # Make successful login attempt
        valid_login_data = TestDataFactory.create_login_data(
            username=test_user.name,
            password=test_user.password
        )
        
        success_response = client.post(
            TestConstants.ENDPOINTS["LOGIN"],
            data=valid_login_data,
            headers=TestConstants.HEADERS["CONTENT_TYPE_FORM"]
        )
        
        assert success_response.status_code == status.HTTP_200_OK, \
            f"Valid login failed after invalid attempt: {success_response.text}"
        
        # Verify token works
        token = success_response.json()["access_token"]
        headers = TestDataFactory.create_auth_headers(token)
        
        profile_response = client.get(
            TestConstants.ENDPOINTS["USER_ME"],
            headers=headers
        )
        
        assert profile_response.status_code == status.HTTP_200_OK
