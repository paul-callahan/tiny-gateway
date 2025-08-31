import httpx
from typing import Dict, Optional, List
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response
from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.models.config_models import AppConfig, ProxyConfig
from app.config.settings import settings

class ProxyMiddleware:
    def __init__(self, app, config: AppConfig):
        self.app = app
        self.config = config
        self.proxy_routes = {}
        for proxy in config.proxy:
            self.proxy_routes[proxy.endpoint] = proxy

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = StarletteRequest(scope, receive=receive)
        path = request.url.path

        # Find matching proxy route
        proxy_config = None
        for endpoint, config in self.proxy_routes.items():
            if path.startswith(endpoint):
                proxy_config = config
                break

        if not proxy_config:
            await self.app(scope, receive, send)
            return

        # Always include the full request path in the target URL
        target_base = proxy_config.target.rstrip('/')
        target_url = f"{target_base}{path}"
        
        # Prepare headers
        headers = dict(request.headers)
        if proxy_config.change_origin:
            # Update Host header to target host
            target_host = proxy_config.target.split('//')[-1].split('/')[0]
            headers['host'] = target_host

        # Require valid JWT token with tenant_id
        auth_header = headers.get('authorization', '').split()
        if len(auth_header) != 2 or auth_header[0].lower() != 'bearer':
            await send({
                'type': 'http.response.start',
                'status': 401,
                'headers': [(b'content-type', b'application/json')]
            })
            await send({
                'type': 'http.response.body',
                'body': b'{"detail":"Missing or invalid Authorization header"}',
                'more_body': False
            })
            return

        try:
            # Validate and decode the JWT token
            token = auth_header[1]
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            
            # Require tenant_id in the token
            if 'tenant_id' not in payload or not payload['tenant_id']:
                raise JWTError("Missing tenant_id in token")
                
            # Add tenant_id to headers for the proxied request
            headers['X-Tenant-ID'] = payload['tenant_id']
            
        except (JWTError, jwt.JWTError) as e:
            await send({
                'type': 'http.response.start',
                'status': 401,
                'headers': [(b'content-type', b'application/json')]
            })
            await send({
                'type': 'http.response.body',
                'body': f'{{"detail":"Invalid or expired token: {str(e)}"}}'.encode(),
                'more_body': False
            })
            return

        # Forward the request
        async with httpx.AsyncClient() as client:
            # Get request body if present
            body = await request.body()
            
            try:
                # Forward the request with the same method, headers, and body
                response = await client.request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    params=dict(request.query_params),
                    content=body,
                    follow_redirects=False
                )
                
                # Return the response
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
                
            except httpx.ConnectError:
                await send({
                    'type': 'http.response.start',
                    'status': 502,
                    'headers': [
                        (b'content-type', b'application/json')
                    ]
                })
                await send({
                    'type': 'http.response.body',
                    'body': b'{"detail":"Bad Gateway: Unable to connect to the upstream server"}',
                    'more_body': False
                })
