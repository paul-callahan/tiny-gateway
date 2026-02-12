from pydantic import BaseModel
from typing import List

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: str
    roles: List[str] = []
    tenant_id: str


class UserResponse(BaseModel):
    """User model for API responses (excludes password)"""
    username: str
    roles: List[str] = []
    tenant_id: str

