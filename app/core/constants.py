from fastapi.security import OAuth2PasswordBearer
from app.config.settings import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")
