"""Auth module schemas."""

from pydantic import BaseModel, Field

from src.modules.users.schemas import UserPublic


class LoginRequest(BaseModel):
    code: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    token: str
    user_info: UserPublic
