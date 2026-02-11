import pytest
import asyncio
import json
from typing import Dict, List, Any
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
import uvicorn
import threading
import time
import httpx
from unittest.mock import patch

from app.main import create_application
from app.models.config_models import AppConfig
from app.api.deps import get_config
from tests.constants import TestConstants
from tests.factories import TestDataFactory


class MockBackendServer:
    """Mock backend server to simulate proxy targets."""
    
    def __init__(self, port: int = 9999):
        self.port = port
        self.app = FastAPI()
        self.captured_requests: List[Dict[str, Any]] = []
        self.responses: Dict[str, Dict[str, Any]] = {}
        self.server = None
        self.server_thread = None
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup mock backend routes."""
        
        @self.app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
        async def catch_all(request: Request, path: str):
            """Catch all requests and record them."""
            body = await request.body()
            
            # Capture request details
            captured_request = {
                "method": request.method,
                "path": f"/{path}",
                "headers": dict(request.headers),
                "query_params": dict(request.query_params),
                "body": body.decode() if body else None,
                "url": str(request.url)
            }
            self.captured_requests.append(captured_request)
            
            # Return configured response or default
            response_key = f"{request.method} /{path}"
            if response_key in self.responses:
                response_data = self.responses[response_key]
                return JSONResponse(
                    content=response_data.get("content", {"message": "mock response"}),
                    status_code=response_data.get("status_code", 200),
                    headers=response_data.get("headers", {})
                )
            
            # Default response
            return JSONResponse(
                content={
                    "message": "mock backend response",
                    "path": f"/{path}",
                    "method": request.method,
                    "received_headers": {
                        "x-tenant-id": request.headers.get("x-tenant-id"),
                        "authorization": request.headers.get("authorization")
                    }
                },
                status_code=200
            )
    
    def configure_response(self, method: str, path: str, content: Dict[str, Any], 
                          status_code: int = 200, headers: Dict[str, str] = None):
        """Configure a specific response for a method/path combination."""
        key = f"{method} {path}"
        self.responses[key] = {
            "content": content,
            "status_code": status_code,
            "headers": headers or {}
        }
    
    def start(self):
        """Start the mock backend server."""
        def run_server():
            uvicorn.run(self.app, host="127.0.0.1", port=self.port, log_level="error")
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        time.sleep(1)  # Give server time to start
    
    def stop(self):
        """Stop the mock backend server."""
        if self.server_thread:
            # Server will stop when thread ends (daemon thread)
            pass
    
    def clear_requests(self):
        """Clear captured requests."""
        self.captured_requests.clear()
    
    def get_last_request(self) -> Dict[str, Any]:
        """Get the last captured request."""
        return self.captured_requests[-1] if self.captured_requests else None
    
    def get_requests_for_path(self, path: str) -> List[Dict[str, Any]]:
        """Get all requests for a specific path."""
        return [req for req in self.captured_requests if req["path"] == path]


@pytest.fixture(scope="class")
def mock_backend():
    """Create and start mock backend server."""
    backend = MockBackendServer(port=9999)
    backend.start()
    yield backend
    backend.stop()


@pytest.fixture
def proxy_test_config(mock_backend):
    """Create test configuration with proxy pointing to mock backend."""
    config_data = {
        "tenants": [
            {"id": "test-tenant-1"},
            {"id": "test-tenant-2"}
        ],
        "users": [
            {
                "name": "user1",
                "password": "pass123",
                "roles": ["user"],
                "tenant_id": "test-tenant-1"
            },
            {
                "name": "user2", 
                "password": "pass456",
                "roles": ["admin"],
                "tenant_id": "test-tenant-2"
            }
        ],
        "roles": {
            "user": [
                {"resource": "graph", "actions": ["read"]}
            ],
            "admin": [
                {"resource": "*", "actions": ["read", "write", "create", "update", "delete", "execute"]}
            ]
        },
        "proxy": [
            {
                "endpoint": "/api/v1/graph",
                "target": f"http://127.0.0.1:{mock_backend.port}/",
                "rewrite": "",
                "change_origin": True
            }
        ]
    }
    return AppConfig.from_dict(config_data)


@pytest.fixture
def proxy_client(proxy_test_config):
    """Create test client with proxy configuration."""
    from app.main import create_application
    from app.config.settings import settings
    
    # Temporarily override settings for test
    original_secret = settings.SECRET_KEY
    settings.SECRET_KEY = "test-secret-key-for-proxy-integration"
    
    # Create a new FastAPI app without loading config from file
    from fastapi import FastAPI
    from app.api.api import api_router
    from app.core.middleware import ProxyMiddleware
    
    app = FastAPI(
        title="Test API Gateway",
        openapi_url="/api/v1/openapi.json"
    )
    
    # Add proxy middleware with test config
    app.add_middleware(ProxyMiddleware, config=proxy_test_config)
    
    # Include API router
    app.include_router(api_router)
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}
    
    # Override config dependency
    def get_proxy_config():
        return proxy_test_config
    
    app.dependency_overrides[get_config] = get_proxy_config
    
    try:
        with TestClient(app) as client:
            yield client
    finally:
        # Restore original settings
        settings.SECRET_KEY = original_secret


@pytest.fixture
def auth_token_user1(proxy_client):
    """Get auth token for user1."""
    login_data = TestDataFactory.create_login_data("user1", "pass123")
    response = proxy_client.post(
        TestConstants.ENDPOINTS["LOGIN"],
        data=login_data,
        headers=TestConstants.HEADERS["CONTENT_TYPE_FORM"]
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def auth_token_user2(proxy_client):
    """Get auth token for user2."""
    login_data = TestDataFactory.create_login_data("user2", "pass456")
    response = proxy_client.post(
        TestConstants.ENDPOINTS["LOGIN"],
        data=login_data,
        headers=TestConstants.HEADERS["CONTENT_TYPE_FORM"]
    )
    assert response.status_code == 200
    return response.json()["access_token"]


class TestProxyIntegration:
    """Integration tests for proxy functionality."""
    
    def test_authenticated_proxy_request_success(self, proxy_client, auth_token_user1, mock_backend):
        """Test successful proxy with valid JWT token."""
        mock_backend.clear_requests()
        
        headers = TestDataFactory.create_auth_headers(auth_token_user1)
        
        # Make request through proxy
        response = proxy_client.get("/api/v1/graph/test", headers=headers)
        
        # Verify response
        assert response.status_code == 200
        response_data = response.json()
        assert "mock backend response" in response_data["message"]
        assert response_data["path"] == "/api/v1/graph/test"
        assert response_data["method"] == "GET"
        
        # Verify request was proxied correctly
        last_request = mock_backend.get_last_request()
        assert last_request is not None
        assert last_request["method"] == "GET"
        assert last_request["path"] == "/api/v1/graph/test"
        assert last_request["headers"]["x-tenant-id"] == "test-tenant-1"
        assert "authorization" in last_request["headers"]
    
    def test_unauthenticated_proxy_request_rejected(self, proxy_client, mock_backend):
        """Test proxy rejection without JWT token."""
        mock_backend.clear_requests()
        
        # Make request without auth header
        response = proxy_client.get("/api/v1/graph/test")
        
        # Should be rejected with 401
        assert response.status_code == 401
        assert "Missing or invalid Authorization header" in response.json()["detail"]
        
        # Verify request never reached backend
        assert len(mock_backend.captured_requests) == 0
    
    def test_invalid_token_proxy_request_rejected(self, proxy_client, mock_backend):
        """Test proxy rejection with invalid JWT token."""
        mock_backend.clear_requests()
        
        headers = {"Authorization": "Bearer invalid-token"}
        
        # Make request with invalid token
        response = proxy_client.get("/api/v1/graph/test", headers=headers)
        
        # Should be rejected with 401
        assert response.status_code == 401
        assert "Invalid or expired token" in response.json()["detail"]
        
        # Verify request never reached backend
        assert len(mock_backend.captured_requests) == 0
    
    def test_tenant_isolation_in_proxy(self, proxy_client, auth_token_user1, auth_token_user2, mock_backend):
        """Test that different tenants get correct tenant IDs in proxied requests."""
        mock_backend.clear_requests()
        
        # User1 request (tenant-1)
        headers1 = TestDataFactory.create_auth_headers(auth_token_user1)
        response1 = proxy_client.get("/api/v1/graph/tenant-test", headers=headers1)
        assert response1.status_code == 200
        
        # User2 request (tenant-2)
        headers2 = TestDataFactory.create_auth_headers(auth_token_user2)
        response2 = proxy_client.get("/api/v1/graph/tenant-test", headers=headers2)
        assert response2.status_code == 200
        
        # Verify both requests reached backend with correct tenant IDs
        requests = mock_backend.get_requests_for_path("/api/v1/graph/tenant-test")
        assert len(requests) == 2
        
        tenant_ids = [req["headers"]["x-tenant-id"] for req in requests]
        assert "test-tenant-1" in tenant_ids
        assert "test-tenant-2" in tenant_ids
    
    def test_proxy_request_methods_and_data(self, proxy_client, auth_token_user1, auth_token_user2, mock_backend):
        """Test proxy works with different HTTP methods and request data."""
        mock_backend.clear_requests()
        read_only_headers = TestDataFactory.create_auth_headers(auth_token_user1)
        write_headers = TestDataFactory.create_auth_headers(auth_token_user2)
        
        # GET request
        response = proxy_client.get("/api/v1/graph/items", headers=read_only_headers)
        assert response.status_code == 200
        
        # POST request with JSON data (admin user)
        post_data = {"name": "test item", "value": 123}
        response = proxy_client.post(
            "/api/v1/graph/items", 
            headers=write_headers, 
            json=post_data
        )
        assert response.status_code == 200
        
        # Verify both requests reached backend
        get_requests = [req for req in mock_backend.captured_requests if req["method"] == "GET"]
        post_requests = [req for req in mock_backend.captured_requests if req["method"] == "POST"]
        
        assert len(get_requests) == 1
        assert len(post_requests) == 1
        
        # Verify POST data was forwarded
        post_request = post_requests[0]
        assert json.loads(post_request["body"]) == post_data

    def test_proxy_rbac_denies_disallowed_action(self, proxy_client, auth_token_user1, mock_backend):
        """Test that read-only role cannot perform write action through proxy."""
        mock_backend.clear_requests()
        read_only_headers = TestDataFactory.create_auth_headers(auth_token_user1)

        response = proxy_client.post(
            "/api/v1/graph/items",
            headers=read_only_headers,
            json={"name": "blocked"}
        )

        assert response.status_code == 403
        assert "Insufficient role permissions" in response.json()["detail"]
        assert len(mock_backend.captured_requests) == 0
    
    def test_proxy_query_parameters(self, proxy_client, auth_token_user1, mock_backend):
        """Test that query parameters are forwarded correctly."""
        mock_backend.clear_requests()
        headers = TestDataFactory.create_auth_headers(auth_token_user1)
        
        response = proxy_client.get(
            "/api/v1/graph/search?q=test&limit=10&sort=name",
            headers=headers
        )
        assert response.status_code == 200
        
        last_request = mock_backend.get_last_request()
        assert last_request["query_params"]["q"] == "test"
        assert last_request["query_params"]["limit"] == "10" 
        assert last_request["query_params"]["sort"] == "name"
    
    def test_proxy_backend_error_handling(self, proxy_client, auth_token_user1, mock_backend):
        """Test proxy handling of backend errors."""
        # Configure mock to return error
        mock_backend.configure_response(
            "GET", "/api/v1/graph/error",
            content={"error": "Internal server error"},
            status_code=500
        )
        
        headers = TestDataFactory.create_auth_headers(auth_token_user1)
        response = proxy_client.get("/api/v1/graph/error", headers=headers)
        
        # Should forward the error status code
        assert response.status_code == 500
        assert response.json()["error"] == "Internal server error"
    
    def test_non_proxy_endpoint_unchanged(self, proxy_client, auth_token_user1, mock_backend):
        """Test that non-proxy endpoints work normally."""
        mock_backend.clear_requests()
        headers = TestDataFactory.create_auth_headers(auth_token_user1)
        
        # Call /users/me endpoint (not proxied)
        response = proxy_client.get("/api/v1/users/me", headers=headers)
        assert response.status_code == 200
        
        # Verify no request reached backend
        assert len(mock_backend.captured_requests) == 0
        
        # Verify normal API response
        response_data = response.json()
        assert response_data["username"] == "user1"
        assert response_data["tenant_id"] == "test-tenant-1"
    
    def test_proxy_backend_connection_error(self, auth_token_user1):
        """Test proxy handling when backend is unavailable."""
        from app.config.settings import settings
        from fastapi import FastAPI
        from app.api.api import api_router
        from app.core.middleware import ProxyMiddleware
        
        # Create client with config pointing to non-existent backend
        bad_config_data = {
            "tenants": [{"id": "test-tenant-1"}],
            "users": [{
                "name": "user1",
                "password": "pass123", 
                "roles": ["user"],
                "tenant_id": "test-tenant-1"
            }],
            "roles": {"user": [{"resource": "graph", "actions": ["read"]}]},
            "proxy": [{
                "endpoint": "/api/v1/graph",
                "target": "http://127.0.0.1:9998/",  # Non-existent port
                "rewrite": "",
                "change_origin": True
            }]
        }
        bad_config = AppConfig.from_dict(bad_config_data)
        
        # Create app with bad config
        app = FastAPI(title="Test API Gateway")
        app.add_middleware(ProxyMiddleware, config=bad_config)
        app.include_router(api_router)
        
        @app.get("/health")
        async def health_check():
            return {"status": "healthy"}
            
        app.dependency_overrides[get_config] = lambda: bad_config
        
        with TestClient(app) as client:
            headers = TestDataFactory.create_auth_headers(auth_token_user1)
            response = client.get("/api/v1/graph/test", headers=headers)
            
            # Should return 502 Bad Gateway
            assert response.status_code == 502
            assert "Bad Gateway" in response.json()["detail"]
