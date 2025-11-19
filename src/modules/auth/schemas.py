"""Auth module schemas."""

from pydantic import AliasChoices, BaseModel, Field

from src.modules.users.schemas import UserPublic


class LoginRequest(BaseModel):
    code: str = Field(..., min_length=1)


class PhoneLoginRequest(BaseModel):
    phone_number: str = Field(
        ...,
        min_length=4,
        validation_alias=AliasChoices("phone", "phone_number"),
        serialization_alias="phone",
    )
    verification_code: str | None = Field(
        default=None,
        min_length=4,
        max_length=10,
        validation_alias=AliasChoices("code", "otp", "verification_code"),
        serialization_alias="code",
    )


class TokenResponse(BaseModel):
    token: str
    user_info: UserPublic
