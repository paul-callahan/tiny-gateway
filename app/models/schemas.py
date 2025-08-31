from pydantic import BaseModel
from typing import List, Optional

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: str
    roles: List[str] = []
    tenant_id: str

class User(BaseModel):
    username: str
    password: str
    roles: List[str] = []
    tenant_id: str

class UserInDB(User):
    """User model for database representation"""
    pass

class UserResponse(BaseModel):
    """User model for API responses (excludes password)"""
    username: str
    roles: List[str] = []
    tenant_id: str

class ProxyRequest(BaseModel):
    method: str
    url: str
    headers: dict = {}
    params: dict = {}
    data: Optional[dict] = None
    json_data: Optional[dict] = None
