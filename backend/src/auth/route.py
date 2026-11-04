from fastapi import APIRouter, status

from src.auth.dependency import AuthServiceDependency
from src.auth.schema import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    ResendCodeRequest,
    VerifyEmailRequest,
)

auth_router = APIRouter(prefix="/auth", tags=["Auth"])


@auth_router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterRequest, service: AuthServiceDependency
) -> RegisterResponse:
    return await service.register(data)


@auth_router.post("/verify-email")
async def verify_email(
    data: VerifyEmailRequest, service: AuthServiceDependency
) -> AuthResponse:
    return await service.verify_email(data)


@auth_router.post(
    "/resend-code", status_code=status.HTTP_204_NO_CONTENT
)
async def resend_code(
    data: ResendCodeRequest, service: AuthServiceDependency
) -> None:
    await service.resend_code(data)


@auth_router.post("/login")
async def login(
    data: LoginRequest, service: AuthServiceDependency
) -> AuthResponse:
    return await service.login(data)
