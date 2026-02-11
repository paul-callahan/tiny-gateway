import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock

from app.core.middleware import ProxyMiddleware
from app.models.config_models import AppConfig, ProxyConfig, User, Permission
from tests.factories import TestDataFactory

@pytest.fixture
def test_app():
    app = FastAPI()
    
    @app.get("/test-endpoint")
    async def test_endpoint():
        return {"message": "test"}
    
    return app

@pytest.fixture
def proxy_config():
    # Create a test user with necessary permissions
    test_user = User(
        name="testuser",
        password="testpassword",  # This will be hashed in the actual test
        tenant_id="test-tenant",
        roles=["test-role"]
    )
    
    # Create a test role with necessary permissions
    test_permission = Permission(
        resource="*",
        actions=["read", "write"]
    )
    
    return {
        "proxy": [
            ProxyConfig(
                endpoint="/api/v1/graph",
                target="http://test-server/",
                rewrite="",
                change_origin=True
            )
        ],
        "users": [test_user],
        "roles": {
            "test-role": [test_permission]
        },
        "tenants": [{"id": "test-tenant"}]
    }

@pytest.fixture
def mock_async_client():
    async def async_magic():
        pass
    
    with patch('httpx.AsyncClient') as mock_async_client:
        # Create a mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"data": "test data"}'
        
        # Create a mock client that returns the mock response
        mock_client = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        
        # Set up the async context manager
        mock_async_client.return_value.__aenter__.return_value = mock_client
        
        # Make the mock client awaitable
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        
        yield mock_client

@pytest.mark.parametrize("target_url", [
    "http://test-server/",  # With trailing slash
    "http://test-server"     # Without trailing slash
])
def test_proxy_middleware_path_preservation(test_app, mock_async_client, target_url):
    # The mock response is now set up in the fixture
    
    # Create test config with the parameterized target URL
    proxy_config = [
        ProxyConfig(
            endpoint="/api/v1/graph",
            target=target_url,
            rewrite="",
            change_origin=True
        )
    ]

    test_user = User(
        name="testuser",
        password="testpassword",
        tenant_id="test-tenant",
        roles=["admin"]
    )
    admin_permission = Permission(resource="*", actions=["read", "write", "create", "update", "delete"])
    
    # Create test client with middleware, passing the mock client
    test_app.add_middleware(
        ProxyMiddleware,
        config=AppConfig(
            proxy=proxy_config,
            users=[test_user],
            roles={"admin": [admin_permission]},
            tenants=[{"id": "test-tenant"}]
        ),
        client=mock_async_client
    )
    
    client = TestClient(test_app)
    
    # Create a test JWT token using factory
    token = TestDataFactory.create_jwt_token()
    
    # Make request to proxied endpoint with auth header
    response = client.get(
        "/api/v1/graph",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Verify the request was forwarded with the correct URL
    mock_async_client.request.assert_called_once()
    _, kwargs = mock_async_client.request.call_args
    
    # The final URL should be the same regardless of trailing slash in target
    expected_url = "http://test-server/api/v1/graph"
    assert kwargs["url"] == expected_url, \
        f"Expected URL: {expected_url}, got: {kwargs['url']}"
    assert kwargs["method"] == "GET"
    
    # Verify the response is correctly returned
    assert response.status_code == 200
    assert response.json() == {"data": "test data"}

def test_non_proxied_endpoint(test_app, proxy_config, mock_async_client):
    # Configure the test app with middleware and test config, passing the mock client
    test_app.add_middleware(
        ProxyMiddleware,
        config=AppConfig(**proxy_config),
        client=mock_async_client
    )
    
    client = TestClient(test_app)
    
    # Make request to non-proxied endpoint
    response = client.get("/test-endpoint")
    
    # Verify the request was not proxied
    mock_async_client.request.assert_not_called()
    
    # Verify the request was handled by the test endpoint
    assert response.status_code == 200
    assert response.json() == {"message": "test"}


def test_proxy_route_precedence_prefers_most_specific_endpoint(test_app, mock_async_client):
    proxy_routes = [
        ProxyConfig(
            endpoint="/api/v1",
            target="http://broad-target/",
            rewrite="",
            change_origin=True
        ),
        ProxyConfig(
            endpoint="/api/v1/graph",
            target="http://specific-target/",
            rewrite="",
            change_origin=True
        ),
    ]

    test_user = User(
        name="testuser",
        password="testpassword",
        tenant_id="test-tenant",
        roles=["admin"]
    )
    admin_permission = Permission(resource="*", actions=["read", "write", "create", "update", "delete"])

    test_app.add_middleware(
        ProxyMiddleware,
        config=AppConfig(
            proxy=proxy_routes,
            users=[test_user],
            roles={"admin": [admin_permission]},
            tenants=[{"id": "test-tenant"}]
        ),
        client=mock_async_client
    )

    client = TestClient(test_app)
    token = TestDataFactory.create_jwt_token()

    response = client.get(
        "/api/v1/graph/items",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    _, kwargs = mock_async_client.request.call_args
    assert kwargs["url"] == "http://specific-target/api/v1/graph/items"


def test_proxy_endpoint_matching_respects_path_boundaries(test_app, mock_async_client):
    proxy_routes = [
        ProxyConfig(
            endpoint="/api/v1/graph",
            target="http://graph-target/",
            rewrite="",
            change_origin=True
        )
    ]

    test_user = User(
        name="testuser",
        password="testpassword",
        tenant_id="test-tenant",
        roles=["admin"]
    )
    admin_permission = Permission(resource="*", actions=["read", "write", "create", "update", "delete"])

    test_app.add_middleware(
        ProxyMiddleware,
        config=AppConfig(
            proxy=proxy_routes,
            users=[test_user],
            roles={"admin": [admin_permission]},
            tenants=[{"id": "test-tenant"}]
        ),
        client=mock_async_client
    )

    client = TestClient(test_app)
    token = TestDataFactory.create_jwt_token()

    response = client.get(
        "/api/v1/graphical/items",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404
    mock_async_client.request.assert_not_called()


@pytest.mark.parametrize(
    "method,permission_actions,expected_allowed",
    [
        ("HEAD", ["read"], True),
        ("OPTIONS", ["read"], True),
        ("PATCH", ["update"], True),
        ("PATCH", ["write"], True),
        ("PATCH", ["read"], False),
        ("DELETE", ["delete"], True),
        ("DELETE", ["write"], True),
        ("DELETE", ["read"], False),
    ]
)
def test_proxy_method_action_mapping_edges(method, permission_actions, expected_allowed):
    app = FastAPI()
    proxy_config = ProxyConfig(
        endpoint="/api/v1/graph",
        target="http://test-server/",
        resource=None,
        rewrite="",
        change_origin=True
    )
    test_user = User(name="testuser", password="testpassword", tenant_id="test-tenant", roles=["role-a"])
    permission = Permission(resource="graph", actions=permission_actions)

    middleware = ProxyMiddleware(
        app=app,
        config=AppConfig(
            proxy=[proxy_config],
            users=[test_user],
            roles={"role-a": [permission]},
            tenants=[{"id": "test-tenant"}]
        ),
        client=MagicMock()
    )

    assert middleware._is_authorized_for_proxy(["role-a"], method, proxy_config) == expected_allowed


def test_proxy_resource_override_used_for_rbac():
    app = FastAPI()
    proxy_config = ProxyConfig(
        endpoint="/api/v1/graph",
        target="http://test-server/",
        resource="data",
        rewrite="",
        change_origin=True
    )
    test_user = User(name="testuser", password="testpassword", tenant_id="test-tenant", roles=["role-a"])
    permission = Permission(resource="data", actions=["read"])

    middleware = ProxyMiddleware(
        app=app,
        config=AppConfig(
            proxy=[proxy_config],
            users=[test_user],
            roles={"role-a": [permission]},
            tenants=[{"id": "test-tenant"}]
        ),
        client=MagicMock()
    )

    assert middleware._is_authorized_for_proxy(["role-a"], "GET", proxy_config) is True


def test_proxy_resource_override_enforced_in_request_flow(test_app, mock_async_client):
    proxy_config = ProxyConfig(
        endpoint="/api/v1/graph",
        target="http://test-server/",
        resource="data",
        rewrite="",
        change_origin=True
    )
    test_user = User(
        name="testuser",
        password="testpassword",
        tenant_id="test-tenant",
        roles=["role-a"]
    )
    permission = Permission(resource="data", actions=["read"])

    test_app.add_middleware(
        ProxyMiddleware,
        config=AppConfig(
            proxy=[proxy_config],
            users=[test_user],
            roles={"role-a": [permission]},
            tenants=[{"id": "test-tenant"}]
        ),
        client=mock_async_client
    )

    client = TestClient(test_app)
    token = TestDataFactory.create_jwt_token(roles=["role-a"])
    response = client.get("/api/v1/graph/items", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    mock_async_client.request.assert_called_once()


def test_proxy_resource_override_denies_when_permission_resource_differs(test_app, mock_async_client):
    proxy_config = ProxyConfig(
        endpoint="/api/v1/graph",
        target="http://test-server/",
        resource="data",
        rewrite="",
        change_origin=True
    )
    test_user = User(
        name="testuser",
        password="testpassword",
        tenant_id="test-tenant",
        roles=["role-a"]
    )
    permission = Permission(resource="graph", actions=["read"])

    test_app.add_middleware(
        ProxyMiddleware,
        config=AppConfig(
            proxy=[proxy_config],
            users=[test_user],
            roles={"role-a": [permission]},
            tenants=[{"id": "test-tenant"}]
        ),
        client=mock_async_client
    )

    client = TestClient(test_app)
    token = TestDataFactory.create_jwt_token(roles=["role-a"])
    response = client.get("/api/v1/graph/items", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    mock_async_client.request.assert_not_called()
