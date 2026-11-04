from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_code: str = "INTERNAL_ERROR"

    def __init__(
        self,
        code: str | None = None,
        detail: str | None = None,
        **extra: Any,
    ) -> None:
        self.code = code or self.default_code
        self.detail = detail
        self.extra = extra
        super().__init__(self.code)


class BadRequestError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "BAD_REQUEST"


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_code = "UNAUTHORIZED"


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "FORBIDDEN"


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    default_code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "CONFLICT"


class UnprocessableError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_code = "UNPROCESSABLE"


class TooManyRequestsError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_code = "TOO_MANY_REQUESTS"


class ServiceUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = "SERVICE_UNAVAILABLE"


async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "detail": exc.detail, **exc.extra},
    )


async def handle_validation_error(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = [
        {
            "field": ".".join(
                str(part) for part in error["loc"] if part != "body"
            ),
            "message": error["msg"],
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": "VALIDATION_FAILED",
            "detail": None,
            "errors": errors,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.exception_handler(AppError)(handle_app_error)
    app.exception_handler(RequestValidationError)(
        handle_validation_error
    )
