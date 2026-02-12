from fastapi import APIRouter

from tiny_gateway.api.v1.endpoints import auth, users
from tiny_gateway.config import settings

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
