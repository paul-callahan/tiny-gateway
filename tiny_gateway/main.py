import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from fastapi import FastAPI
from starlette.responses import FileResponse

from tiny_gateway.api.api import api_router
from tiny_gateway.config.settings import settings
from tiny_gateway.core.middleware import ProxyMiddleware
from tiny_gateway.models.config_models import AppConfig

logger = logging.getLogger(__name__)

PACKAGE_DIR = Path(__file__).resolve().parent
RESOURCE_DIR = PACKAGE_DIR / "resources"
DEFAULT_CONFIG_FILE = RESOURCE_DIR / "default_config.yml"
LOGIN_PAGE_FILE = RESOURCE_DIR / "index.html"


def _resolve_config_path() -> Path:
    configured_path = os.getenv("CONFIG_FILE")
    if configured_path:
        return Path(configured_path).expanduser().resolve()
    return DEFAULT_CONFIG_FILE


def _load_config() -> AppConfig:
    config_path = _resolve_config_path()

    try:
        with config_path.open("r", encoding="utf-8") as config_file:
            config_data = yaml.safe_load(config_file) or {}
        config = AppConfig.from_dict(config_data)
        logger.info("Configuration loaded from %s", config_path)
    except FileNotFoundError:
        logger.error("Configuration file not found: %s", config_path)
        raise
    except yaml.YAMLError as exc:
        logger.error("Error parsing YAML configuration: %s", exc)
        raise

    if config.default_config:
        logger.warning(
            "The service is using the default config and that's probably not intended. "
            "Remove the default_config flag in your version."
        )

    return config


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings.configure_logging()
    config = _load_config()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Manage application lifecycle events."""
        logger.info("Starting up API Gateway...")

        app.state.config = config

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

        yield

        logger.info("Shutting down API Gateway...")
        await shared_client.aclose()
        logger.info("HTTP client closed successfully")

    app = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(ProxyMiddleware, config=config)
    app.include_router(api_router)

    @app.get("/health")
    async def health_check():
        """Health check endpoint for monitoring."""
        return {"status": "healthy"}

    @app.get("/test_login")
    async def read_index():
        """Serve the login web page."""
        return FileResponse(LOGIN_PAGE_FILE)

    return app


def run() -> None:
    """CLI entrypoint for running the gateway."""
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload_enabled = os.getenv("RELOAD", "").lower() in {"1", "true", "yes"}
    uvicorn.run("tiny_gateway.main:app", host=host, port=port, reload=reload_enabled)


app = create_application()


if __name__ == "__main__":
    run()
