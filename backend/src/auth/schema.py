from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    EmailStr,
    StringConstraints,
    field_validator,
)

from src.user.schema import NewPassword, Nickname, Password, ProfileRead

Email = Annotated[EmailStr, AfterValidator(str.lower)]


class RegisterRequest(BaseModel):
    nickname: Nickname
    email: Email
    password: NewPassword
    pd_consent: bool

    @field_validator("pd_consent")
    @classmethod
    def require_consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError(
                "Consent to personal data processing is required"
            )
        return value


class VerifyEmailRequest(BaseModel):
    email: Email
    code: Annotated[str, StringConstraints(pattern=r"^\d{6}$")]


class ResendCodeRequest(BaseModel):
    email: Email


class LoginRequest(BaseModel):
    email: Email
    password: Password


class RegisterResponse(BaseModel):
    email: str


class AuthResponse(BaseModel):
    access_token: str
    profile: ProfileRead
