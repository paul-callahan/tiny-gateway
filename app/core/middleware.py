import json
import logging
import httpx
from typing import Dict, Optional, Any, Set
from starlette.requests import Request as StarletteRequest
from fastapi import HTTPException

from app.models.config_models import AppConfig, ProxyConfig
from app.models.schemas import TokenPayload
from app.core.security import validate_token_and_get_payload

logger = logging.getLogger(__name__)


class ProxyMiddleware:
    """
    Middleware for proxying authenticated requests to backend services.
    Validates JWT tokens and forwards requests with tenant context.
    """
    
    # Configuration constants
    DEFAULT_TIMEOUT = 30.0
    DEFAULT_MAX_KEEPALIVE = 100
    DEFAULT_MAX_CONNECTIONS = 1000
    DEFAULT_KEEPALIVE_EXPIRY = 60.0
    METHOD_ACTION_ALIASES = {
        "GET": {"read"},
        "HEAD": {"read"},
        "OPTIONS": {"read"},
        "POST": {"create", "write", "execute"},
        "PUT": {"update", "write"},
        "PATCH": {"update", "write"},
        "DELETE": {"delete", "write"},
    }
    
    def __init__(self, app, config: AppConfig, client: Optional[httpx.AsyncClient] = None):
        self.app = app
        self.config = config
        self.proxy_routes = {proxy.endpoint: proxy for proxy in config.proxy}
        self._client = client
        self._should_close_client = client is None
        
        if self._client is None:
            self._client = self._create_http_client()
            logger.debug("ProxyMiddleware initialized with new HTTP client")
        else:
            logger.debug("ProxyMiddleware initialized with provided HTTP client")
    
    def _create_http_client(self) -> httpx.AsyncClient:
        """Create a configured HTTP client with connection pooling and HTTP/2."""
        client = httpx.AsyncClient(
            timeout=self.DEFAULT_TIMEOUT,
            limits=httpx.Limits(
                max_keepalive_connections=self.DEFAULT_MAX_KEEPALIVE,
                max_connections=self.DEFAULT_MAX_CONNECTIONS,
                keepalive_expiry=self.DEFAULT_KEEPALIVE_EXPIRY,
            ),
            http2=True,
            follow_redirects=False,
        )
        logger.debug("HTTP/2 client initialized with connection pooling")
        return client
            
    @property
    def client(self) -> httpx.AsyncClient:
        """Get the HTTP client instance."""
        # Try to use shared client from app state, fallback to instance client
        if hasattr(self.app, 'state') and hasattr(self.app.state, 'http_client'):
            return self.app.state.http_client
        return self._client

    def _find_matching_proxy(self, path: str) -> Optional[ProxyConfig]:
        """Find the proxy configuration that matches the given path."""
        for endpoint, config in self.proxy_routes.items():
            if path.startswith(endpoint):
                return config
        return None
    
    async def _send_error_response(self, send, status_code: int, message: str) -> None:
        """Send a standardized error response."""
        await send({
            'type': 'http.response.start',
            'status': status_code,
            'headers': [(b'content-type', b'application/json')]
        })
        await send({
            'type': 'http.response.body',
            'body': json.dumps({"detail": message}).encode(),
            'more_body': False
        })
    
    async def _authenticate_request(self, headers: Dict[str, str]) -> TokenPayload:
        """
        Authenticate request and return canonical user payload bound to config.
        """
        auth_header = headers.get('authorization', '').split()
        if len(auth_header) != 2 or auth_header[0].lower() != 'bearer':
            raise ValueError("Missing or invalid Authorization header")

        try:
            token = auth_header[1]
            return validate_token_and_get_payload(token, self.config)
        except HTTPException:
            raise ValueError("Invalid or expired token")

    @staticmethod
    def _normalize_resource(resource: str) -> str:
        """Normalize resource identifiers for comparison."""
        normalized = "".join(char for char in resource.lower() if char.isalnum() or char in {"-", "_"})
        return normalized.strip("-_")

    @classmethod
    def _resource_matches(cls, permission_resource: str, request_resource: str) -> bool:
        """Compare resources with simple singular/plural tolerance."""
        if permission_resource == "*":
            return True

        permission = cls._normalize_resource(permission_resource)
        requested = cls._normalize_resource(request_resource)

        if not permission or not requested:
            return False

        if permission == requested:
            return True

        if permission.endswith("s") and permission[:-1] == requested:
            return True

        if requested.endswith("s") and requested[:-1] == permission:
            return True

        return False

    @staticmethod
    def _get_proxy_resource(proxy_config: ProxyConfig) -> str:
        """Get resource name for RBAC checks from proxy config or endpoint."""
        if proxy_config.resource:
            return proxy_config.resource

        endpoint_parts = [part for part in proxy_config.endpoint.strip("/").split("/") if part]
        return endpoint_parts[-1] if endpoint_parts else "resource"

    def _is_authorized_for_proxy(self, roles: list[str], method: str, proxy_config: ProxyConfig) -> bool:
        """Check whether any role grants permission for resource + action."""
        if not roles:
            return False

        required_actions: Set[str] = self.METHOD_ACTION_ALIASES.get(method.upper(), {"write"})
        resource = self._get_proxy_resource(proxy_config)

        for role in roles:
            permissions = self.config.roles.get(role, [])
            for permission in permissions:
                if not self._resource_matches(permission.resource, resource):
                    continue

                allowed_actions = {action.lower() for action in permission.actions}
                if "*" in allowed_actions or allowed_actions.intersection(required_actions):
                    return True

        return False
    
    def _prepare_proxy_headers(self, request_headers: Dict[str, str], 
                               proxy_config: ProxyConfig, tenant_id: str) -> Dict[str, str]:
        """Prepare headers for the proxied request."""
        headers = dict(request_headers)
        
        if proxy_config.change_origin:
            # Update Host header to target host
            target_host = proxy_config.target.split('//')[-1].split('/')[0]
            headers['host'] = target_host
        
        # Add tenant_id to headers for the proxied request
        headers['X-Tenant-ID'] = tenant_id
        
        return headers
    
    async def _proxy_request(self, request: StarletteRequest, proxy_config: ProxyConfig, 
                            headers: Dict[str, str]) -> httpx.Response:
        """Forward the request to the target service."""
        target_base = proxy_config.target.rstrip('/')
        target_url = f"{target_base}{request.url.path}"
        
        body = await request.body()
        
        return await self.client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=dict(request.query_params),
            content=body,
            follow_redirects=False
        )
    
    async def _send_proxy_response(self, send, response: httpx.Response) -> None:
        """Send the proxied response back to the client."""
        response_headers = dict(response.headers)
        response_headers.pop('content-encoding', None)  # Remove content-encoding
        
        await send({
            'type': 'http.response.start',
            'status': response.status_code,
            'headers': [
                (k.lower().encode(), v.encode())
                for k, v in response_headers.items()
                if k.lower() not in ['content-length', 'connection', 'transfer-encoding']
            ]
        })
        
        await send({
            'type': 'http.response.body',
            'body': response.content,
            'more_body': False
        })

    async def __call__(self, scope: Dict[str, Any], receive, send) -> None:
        """Main middleware entry point."""
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = StarletteRequest(scope, receive=receive)
        path = request.url.path

        # Find matching proxy route
        proxy_config = self._find_matching_proxy(path)
        if not proxy_config:
            return await self.app(scope, receive, send)

        try:
            # Authenticate the request
            token_payload = await self._authenticate_request(dict(request.headers))

            # Enforce RBAC before proxying to upstream services
            if not self._is_authorized_for_proxy(token_payload.roles, request.method, proxy_config):
                await self._send_error_response(send, 403, "Insufficient role permissions for proxied resource")
                return
            
            # Prepare headers for proxying
            headers = self._prepare_proxy_headers(
                dict(request.headers), proxy_config, token_payload.tenant_id
            )
            
            # Debug log the proxied request details
            target_url = f"{proxy_config.target.rstrip('/')}{request.url.path}"
            logger.debug(
                "Proxying request - Endpoint: %s, Target: %s, User: %s, Tenant: %s, Roles: %s, Headers: X-Tenant-ID=%s",
                proxy_config.endpoint,
                target_url,
                token_payload.sub,
                token_payload.tenant_id,
                token_payload.roles,
                headers.get('X-Tenant-ID', 'Not Set')
            )
            
            # Forward the request
            response = await self._proxy_request(request, proxy_config, headers)
            
            # Send the response back
            await self._send_proxy_response(send, response)
            
        except ValueError as e:
            # Authentication or validation errors
            await self._send_error_response(send, 401, str(e))
            
        except httpx.ConnectError as e:
            # Connection errors to upstream service
            error_msg = "Bad Gateway: Unable to connect to the upstream server"
            logger.error(f"Connection error while proxying to {proxy_config.target}: {str(e)}")
            await self._send_error_response(send, 502, error_msg)
            
        except Exception as e:
            # Unexpected errors
            error_msg = "Internal Server Error"
            logger.error(f"Unexpected error while proxying to {proxy_config.target}", exc_info=True)
            await self._send_error_response(send, 500, error_msg)
            
    async def close(self) -> None:
        """Close the HTTP client when the application shuts down."""
        # Only close if we own the client (not using shared app state client)
        if (self._should_close_client and self._client is not None and 
            not (hasattr(self.app, 'state') and hasattr(self.app.state, 'http_client'))):
            await self._client.aclose()
            self._client = None
            logger.debug("ProxyMiddleware HTTP client closed")
