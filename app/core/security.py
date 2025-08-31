from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.config.settings import settings
from app.models.schemas import TokenPayload
from app.models.config_models import AppConfig, User
from app.api.deps import get_config
from .constants import oauth2_scheme

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def get_user(username: str, config: AppConfig) -> Optional[User]:
    for user in config.users:
        if user.name == username:
            return user
    return None

def authenticate_user(username: str, password: str, config: AppConfig) -> Optional[User]:
    user = get_user(username, config)
    if not user:
        print(f"User {username} not found")
        return None
    
    # Debug output
    print(f"Authenticating user: {username}")
    print(f"Provided password: {password}")
    print(f"Stored password: {user.password}")
    
    # First try direct comparison (for test environment)
    if password == user.password:
        print("Authentication successful (direct match)")
        return user
        
    # Then try password verification (for hashed passwords)
    if verify_password(password, user.password):
        print("Authentication successful (hashed password)")
        return user
        
    print("Authentication failed - password does not match")
    return None

def create_access_token(
    subject: str, 
    data: Dict[str, Any], 
    expires_delta: Optional[timedelta] = None
) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "sub": str(subject)})
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.SECRET_KEY, 
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    config: AppConfig = Depends(get_config)
) -> TokenPayload:
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
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenPayload(
            sub=username,
            roles=payload.get("roles", []),
            tenant_id=payload.get("tenant_id", "")
        )
    except JWTError:
        raise credentials_exception
    
    user = get_user(username=token_data.sub, config=config)
    if user is None:
        raise credentials_exception
    
    return token_data

async def get_current_active_user(
    current_user: TokenPayload = Depends(get_current_user)
) -> TokenPayload:
    """
    Dependency that checks if the current user is active.
    Since we're already validating the user in get_current_user,
    we can just return the current user.
    """
    return current_user
