import logging
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm

from app.core.security import authenticate_user, create_access_token
from app.models.schemas import Token
from app.models.config_models import AppConfig
from app.api.deps import get_config
from app.config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/login", response_model=Token)
async def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    config: AppConfig = Depends(get_config)
):
    """OAuth2 compatible token login, get an access token for future requests"""
    client_ip = request.client.host if request.client else "unknown"
    
    logger.info("Login attempt for user '%s' from IP %s", form_data.username, client_ip)
    
    user = authenticate_user(form_data.username, form_data.password, config)
    if not user:
        logger.warning("Failed login attempt for user '%s' from IP %s", form_data.username, client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.info("Successful login for user '%s' (tenant: %s) from IP %s", 
                user.name, user.tenant_id, client_ip)
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.name,
        data={
            "roles": user.roles,
            "tenant_id": user.tenant_id
        },
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}
