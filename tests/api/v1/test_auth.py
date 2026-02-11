import pytest
from fastapi import status

from tests.constants import TestConstants
from tests.factories import TestDataFactory


class TestAuthentication:
    """Test suite for authentication endpoints."""
    
    def test_login_success(self, client, test_config):
        """Test successful login with valid credentials."""
        test_user = test_config.users[0]
        login_data = TestDataFactory.create_login_data(
            username=test_user.name,
            password=test_user.password
        )
        
        response = client.post(
            TestConstants.ENDPOINTS["LOGIN"],
            data=login_data,
            headers=TestConstants.HEADERS["CONTENT_TYPE_FORM"]
        )
        
        assert response.status_code == status.HTTP_200_OK, \
            f"Login failed with status {response.status_code}: {response.text}"
        
        response_data = response.json()
        assert "access_token" in response_data, \
            f"Missing access_token in response: {response_data}"
        assert response_data["token_type"] == "bearer", \
            f"Expected token_type 'bearer', got: {response_data.get('token_type')}"
        assert response_data["access_token"], \
            "Access token should not be empty"

    def test_login_invalid_username(self, client):
        """Test login with non-existent username."""
        login_data = TestDataFactory.create_login_data(
            username="nonexistent_user",
            password=TestConstants.TEST_PASSWORD
        )
        
        response = client.post(
            TestConstants.ENDPOINTS["LOGIN"],
            data=login_data,
            headers=TestConstants.HEADERS["CONTENT_TYPE_FORM"]
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, \
            f"Expected 401 for invalid username, got {response.status_code}"
        assert "Incorrect username or password" in response.json().get("detail", "")

    def test_login_invalid_password(self, client):
        """Test login with invalid password."""
        login_data = TestDataFactory.create_login_data(
            username=TestConstants.TEST_USER,
            password="wrong_password"
        )
        
        response = client.post(
            TestConstants.ENDPOINTS["LOGIN"],
            data=login_data,
            headers=TestConstants.HEADERS["CONTENT_TYPE_FORM"]
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, \
            f"Expected 401 for invalid password, got {response.status_code}"
        assert "Incorrect username or password" in response.json().get("detail", "")

    def test_login_missing_credentials(self, client):
        """Test login with missing credentials."""
        response = client.post(
            TestConstants.ENDPOINTS["LOGIN"],
            data={},
            headers=TestConstants.HEADERS["CONTENT_TYPE_FORM"]
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT, \
            f"Expected 422 for missing credentials, got {response.status_code}"

    def test_login_malformed_request(self, client):
        """Test login with malformed request data."""
        response = client.post(
            TestConstants.ENDPOINTS["LOGIN"],
            json={"username": TestConstants.TEST_USER},  # Wrong content type
            headers=TestConstants.HEADERS["CONTENT_TYPE_JSON"]
        )
        
        assert response.status_code in [status.HTTP_422_UNPROCESSABLE_CONTENT, status.HTTP_400_BAD_REQUEST], \
            f"Expected 4xx for malformed request, got {response.status_code}"
