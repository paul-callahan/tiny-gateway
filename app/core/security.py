import logging
from datetime import datetime, timedelta, UTC
from typing import Optional, Dict, Any, Iterable

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.config.settings import settings
from app.models.schemas import TokenPayload
from app.models.config_models import AppConfig, User
from .constants import oauth2_scheme

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def _permission_allows(resource: str, action: str, permission_resource: str, permission_actions: Iterable[str]) -> bool:
    """Check if a permission allows the requested resource/action."""
    resource_match = permission_resource == "*" or permission_resource == resource
    action_match = "*" in permission_actions or action in permission_actions
    return resource_match and action_match

def authorize_request(user_roles: Iterable[str], resource: str, action: str, config: AppConfig) -> None:
    """
    Authorize a request based on user roles and configured permissions.

    Args:
        user_roles: Roles associated with the user
        resource: Resource being accessed
        action: Action being performed
        config: Application configuration containing role permissions

    Raises:
        HTTPException: If the user lacks permission for the requested resource/action
    """
    if not user_roles:
        logger.warning("Authorization failed: no roles provided for resource '%s' action '%s'", resource, action)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    for role in user_roles:
        permissions = config.roles.get(role, [])
        for permission in permissions:
            if _permission_allows(resource, action, permission.resource, permission.actions):
                logger.debug("Authorization granted for role '%s' on %s:%s", role, resource, action)
                return

    logger.warning("Authorization denied for roles %s on %s:%s", list(user_roles), resource, action)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)

def get_user(username: str, config: AppConfig) -> Optional[User]:
    """
    Find a user by username in the configuration.
    
    Args:
        username: Username to search for
        config: Application configuration containing users
        
    Returns:
        User object if found, None otherwise
    """
    return next((user for user in config.users if user.name == username), None)

def _is_password_hashed(password: str) -> bool:
    """Check if password is hashed (bcrypt format)."""
    return password.startswith('$2b$') or password.startswith('$2a$')

def _validate_password(password: str, stored_password: str) -> bool:
    """Validate password against stored hash or plaintext."""
    if _is_password_hashed(stored_password):
        return verify_password(password, stored_password)
    else:
        # Development mode: plaintext comparison
        return password == stored_password

def authenticate_user(username: str, password: str, config: AppConfig) -> Optional[User]:
    """
    Authenticate a user with username and password.
    
    Args:
        username: Username to authenticate
        password: Password to verify
        config: Application configuration containing users
        
    Returns:
        User object if authentication successful, None otherwise
    """
    user = get_user(username, config)
    if not user:
        logger.debug("Authentication failed: user '%s' not found", username)
        return None
    
    if _validate_password(password, user.password):
        auth_method = "hashed" if _is_password_hashed(user.password) else "plaintext"
        logger.debug("User '%s' authenticated successfully using %s password", username, auth_method)
        return user
    
    logger.debug("Authentication failed: invalid password for user '%s'", username)
    return None

def create_access_token(
    subject: str, 
    data: Dict[str, Any], 
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.
    
    Args:
        subject: Token subject (typically username)
        data: Additional data to include in token payload
        expires_delta: Custom expiration time, uses default if None
        
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "sub": str(subject)})
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.SECRET_KEY, 
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt

async def get_current_user(
    token: str,
    config: AppConfig
) -> TokenPayload:
    """
    Get current user from JWT token.
    
    Args:
        token: JWT token from Authorization header
        config: Application configuration
        
    Returns:
        TokenPayload with user information
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
    except JWTError as e:
        logger.debug("JWT validation error: %s", str(e))
        raise credentials_exception
    except Exception as e:
        logger.error("Unexpected error during JWT validation: %s", str(e))
        raise credentials_exception
    
    # Extract and validate token data
    username: str = payload.get("sub")
    if not username:
        logger.debug("JWT token missing 'sub' field")
        raise credentials_exception
    
    tenant_id = payload.get("tenant_id", "")
    if not tenant_id:
        logger.debug("JWT token missing 'tenant_id' field")
        raise credentials_exception
    
    # Verify user still exists in configuration
    user = get_user(username=username, config=config)
    if user is None:
        logger.debug("User '%s' from token not found in configuration", username)
        raise credentials_exception
    
    return TokenPayload(
        sub=username,
        roles=payload.get("roles", []),
        tenant_id=tenant_id
    )

async def get_current_active_user(
    current_user: TokenPayload = Depends(get_current_user)
) -> TokenPayload:
    """
    Dependency that checks if the current user is active.
    Since we're already validating the user in get_current_user,
    we can just return the current user.
    """
    return current_user
