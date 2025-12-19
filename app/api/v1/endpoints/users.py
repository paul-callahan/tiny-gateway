from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from app.models.schemas import UserResponse, TokenPayload
from app.models.config_models import AppConfig, User
from app.api.deps import get_current_active_user, get_config, require_permission

router = APIRouter()

@router.get("/me", response_model=UserResponse)
async def read_users_me(
    current_user: TokenPayload = Depends(require_permission("users", "read")),
    config: AppConfig = Depends(get_config)
):
    """Get current user information"""
    # Get the user from config to ensure they still exist
    user = next((u for u in config.users if u.name == current_user.sub), None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Return user data from the token payload which includes roles and tenant_id
    return UserResponse(
        username=current_user.sub,
        roles=current_user.roles,
        tenant_id=current_user.tenant_id
    )
