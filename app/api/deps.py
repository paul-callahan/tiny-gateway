from fastapi import Depends, Request
from app.core.constants import oauth2_scheme
from app.models.config_models import AppConfig
from app.models.schemas import TokenPayload

def get_config(request: Request) -> AppConfig:
    """
    Get the application configuration from app state.
    
    Configuration is loaded once at startup and stored in app.state,
    eliminating the need for file I/O on every request.
    
    Args:
        request: FastAPI request object containing app state
        
    Returns:
        AppConfig: The application configuration
    """
    return request.app.state.config

async def get_current_user_dependency(
    token: str = Depends(oauth2_scheme),
    config: AppConfig = Depends(get_config)
) -> TokenPayload:
    """
    FastAPI dependency to get the current user from JWT token.
    
    Args:
        token: JWT token from Authorization header
        config: Application configuration from app state
        
    Returns:
        TokenPayload: The validated token payload containing user information
    """
    # Import here to avoid circular import
    from app.core.security import get_current_user
    return await get_current_user(token, config)

# Alias for backwards compatibility
get_current_active_user = get_current_user_dependency
