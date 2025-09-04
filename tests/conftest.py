import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.api import api_router
from app.models.config_models import AppConfig
from app.api.deps import get_config
import yaml

@pytest.fixture(scope="session")
def test_config():
    """Load test configuration from config.yml"""
    with open("tests/fixtures/test_config.yml", "r") as f:
        config_data = yaml.safe_load(f)
    return AppConfig.from_dict(config_data)

@pytest.fixture(scope="module")
def client(test_config):
    """Create a test client for the FastAPI application with test configuration"""
    # Import here to avoid circular imports
    from app.main import create_application
    from app.config import settings as app_settings
    
    # Set test settings
    app_settings.ACCESS_TOKEN_EXPIRE_MINUTES = 30
    app_settings.SECRET_KEY = "test-secret-key"
    
    # Create the FastAPI app
    test_app = create_application()
    
    # Override the config dependency to use test config
    def get_test_config():
        return test_config
        
    test_app.dependency_overrides[get_config] = get_test_config
    
    with TestClient(test_app) as test_client:
        yield test_client

@pytest.fixture(scope="module")
def auth_headers(client, test_config):
    """Get authentication headers for a test user."""
    from tests.constants import TestConstants
    from tests.factories import TestDataFactory
    
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
    
    response_data = response.json()
    if "access_token" not in response_data:
        raise ValueError(f"Failed to get access token. Response: {response_data}")
    
    return TestDataFactory.create_auth_headers(response_data["access_token"])
