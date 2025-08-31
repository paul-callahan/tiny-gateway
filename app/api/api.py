from fastapi import APIRouter

from app.api.v1.api import api_router as v1_router
from app.config import settings

api_router = APIRouter(prefix="/api")
api_router.include_router(v1_router, prefix="/v1")
