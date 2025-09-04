import json
import logging
import httpx
from typing import Dict, Optional, Any, Tuple
from starlette.requests import Request as StarletteRequest
from jose import JWTError, jwt

from app.models.config_models import AppConfig, ProxyConfig
from app.config.settings import settings

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
    
    async def _authenticate_request(self, headers: Dict[str, str]) -> Tuple[str, str, list]:
        """
        Authenticate the request and return authentication details.
        Returns tuple of (tenant_id, username, roles) if valid.
        """
        auth_header = headers.get('authorization', '').split()
        if len(auth_header) != 2 or auth_header[0].lower() != 'bearer':
            raise ValueError("Missing or invalid Authorization header")

        try:
            token = auth_header[1]
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            
            tenant_id = payload.get('tenant_id')
            username = payload.get('sub')
            roles = payload.get('roles', [])
            
            if not tenant_id:
                raise JWTError("Missing tenant_id in token")
            if not username:
                raise JWTError("Missing username in token")
                
            return tenant_id, username, roles
            
        except JWTError as e:
            raise ValueError(f"Invalid or expired token: {str(e)}")
    
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
            tenant_id, username, roles = await self._authenticate_request(dict(request.headers))
            
            # Prepare headers for proxying
            headers = self._prepare_proxy_headers(
                dict(request.headers), proxy_config, tenant_id
            )
            
            # Debug log the proxied request details
            target_url = f"{proxy_config.target.rstrip('/')}{request.url.path}"
            logger.debug(
                "Proxying request - Endpoint: %s, Target: %s, User: %s, Tenant: %s, Roles: %s, Headers: X-Tenant-ID=%s",
                proxy_config.endpoint,
                target_url,
                username,
                tenant_id,
                roles,
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
