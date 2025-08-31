from typing import Generator
import yaml
from fastapi import Depends, HTTPException, status

from app.core.constants import oauth2_scheme
from app.models.config_models import AppConfig
from app.models.schemas import TokenPayload

def get_config() -> AppConfig:
    """Load and return the application configuration."""
    try:
        with open("config.yml", "r") as f:
            config_data = yaml.safe_load(f)
        return AppConfig.from_dict(config_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load configuration: {str(e)}"
        )

async def get_current_active_user(
    token: str = Depends(oauth2_scheme),
    config: AppConfig = Depends(get_config)
) -> TokenPayload:
    """Dependency to get the current active user.
    
    Args:
        token: The JWT token from the Authorization header
        config: The application configuration
        
    Returns:
        TokenPayload: The token payload containing user information
        
    Raises:
        HTTPException: If the token is invalid or the user is not found
    """
    from app.core.security import get_current_user
    
    try:
        # Get the token payload which includes roles and tenants
        token_data = await get_current_user(token, config)
        
        # Get the user from config to ensure they still exist
        user = next((u for u in config.users if u.name == token_data.sub), None)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
            
        # Return the full token data including roles and tenants
        return token_data
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
