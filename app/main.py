import os
import yaml
from fastapi import FastAPI

from app.core.middleware import ProxyMiddleware
from app.api.api import api_router
from app.config.settings import settings
from app.models.config_models import AppConfig


def create_application() -> FastAPI:
    # Get config file path from environment variable or use default
    config_path = os.getenv("CONFIG_FILE", "config.yml")
    
    # Load configuration
    with open(config_path, "r") as f:
        config_data = yaml.safe_load(f)
    config = AppConfig.from_dict(config_data)
    
    # Create FastAPI app
    app = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json"
    )
    
    # Add proxy middleware
    app.add_middleware(ProxyMiddleware, config=config)
    
    # Include API router
    app.include_router(api_router)
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}
    
    return app

app = create_application()

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)
