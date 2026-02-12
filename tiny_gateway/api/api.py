from fastapi import APIRouter

from tiny_gateway.api.v1.api import api_router as v1_router
from tiny_gateway.config import settings

api_router = APIRouter(prefix="/api")
api_router.include_router(v1_router, prefix="/v1")
