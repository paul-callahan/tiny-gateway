import os
import yaml
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from starlette.responses import FileResponse

from app.core.middleware import ProxyMiddleware
from app.api.api import api_router
from app.config.settings import settings
from app.models.config_models import AppConfig

logger = logging.getLogger(__name__)


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    # Configure logging first
    settings.configure_logging()
    
    # Get config file path from environment variable or use default
    config_path = os.getenv("CONFIG_FILE", "config/config.yml")
    
    # Load configuration
    try:
        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f)
        config = AppConfig.from_dict(config_data)
        logger.info(f"Configuration loaded from {config_path}")
        
        # Check for default configuration and warn
        if config.default_config:
            logger.warning(
                "The service is using the default config and that's probably not intended. "
                "Remove the default_config flag in your version."
            )
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
        raise
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML configuration: {e}")
        raise
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Manage application lifecycle events."""        
        logger.info("Starting up API Gateway...")
        
        # Store config in app state for reuse across requests
        app.state.config = config
        
        # Create shared HTTP client for middleware
        import httpx
        shared_client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(
                max_keepalive_connections=100,
                max_connections=1000,
                keepalive_expiry=60.0,
            ),
            http2=True,
            follow_redirects=False,
        )
        app.state.http_client = shared_client
        
        logger.info("Configuration and HTTP client initialized")
        
        yield  # Application is running
        
        # Shutdown: Clean up shared resources
        logger.info("Shutting down API Gateway...")
        await shared_client.aclose()
        logger.info("HTTP client closed successfully")
    
    # Create FastAPI app with lifespan management
    app = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        lifespan=lifespan
    )
    
    # Add proxy middleware
    app.add_middleware(ProxyMiddleware, config=config)
    
    # Include API router
    app.include_router(api_router)
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint for monitoring."""
        return {"status": "healthy"}
    
    # Serve login page
    @app.get("/test_login")
    async def read_index():
        """Serve the login web page."""
        return FileResponse('index.html')
    
    return app


app = create_application()

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)
