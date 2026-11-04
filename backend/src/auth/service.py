import math
import secrets
from datetime import UTC, datetime

from src.auth.schema import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    ResendCodeRequest,
    VerifyEmailRequest,
)
from src.auth.token import create_access_token
from src.common.config import (
    EMAIL_CODE_MAX_ATTEMPTS,
    EMAIL_CODE_RESEND_COOLDOWN,
    EMAIL_CODE_TTL,
)
from src.common.database import SessionDependency
from src.common.exception import (
    ConflictError,
    PermissionDeniedError,
    ServiceUnavailableError,
    TooManyRequestsError,
    UnauthorizedError,
    UnprocessableError,
)
from src.common.hashing import hash_secret, verify_secret
from src.email_code.model import EmailCode
from src.email_code.repository import EmailCodeRepository
from src.mailer import sender
from src.user.model import User
from src.user.repository import UserRepository
from src.user.service import ProfileService


def _generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


class AuthService:
    def __init__(self, session: SessionDependency) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.codes = EmailCodeRepository(session)
        self.profiles = ProfileService(session)

    async def register(self, data: RegisterRequest) -> RegisterResponse:
        user = await self._find_user(data.email)
        password_hash = hash_secret(data.password)
        now = datetime.now(UTC)

        if user is None:
            user = await self.users.create(
                email=data.email,
                password_hash=password_hash,
                nickname=data.nickname,
                pd_consent_at=now,
            )
        elif user.email_verified:
            raise ConflictError("EMAIL_TAKEN")
        else:
            await self._check_resend_cooldown(user)
            await self.users.update(
                user.id,
                nickname=data.nickname,
                password_hash=password_hash,
                pd_consent_at=now,
            )

        await self._send_code(user)
        return RegisterResponse(email=user.email)

    async def verify_email(
        self, data: VerifyEmailRequest
    ) -> AuthResponse:
        user = await self._find_user(data.email)
        code = None
        if user is not None and not user.email_verified:
            code = await self._find_code(user)

        if user is None or code is None:
            raise UnprocessableError("CODE_INVALID")
        if code.expires_at <= datetime.now(UTC):
            raise UnprocessableError("CODE_EXPIRED")
        if code.attempts >= EMAIL_CODE_MAX_ATTEMPTS:
            raise UnprocessableError("CODE_ATTEMPTS_EXCEEDED")

        if not verify_secret(data.code, code.code_hash):
            attempts = code.attempts + 1
            await self.codes.update(code.id, attempts=attempts)
            await self.session.commit()
            raise UnprocessableError(
                "CODE_INVALID",
                attempts_left=EMAIL_CODE_MAX_ATTEMPTS - attempts,
            )

        await self.users.update(user.id, email_verified=True)
        await self.codes.delete(code.id)
        return await self._auth_response(user)

    async def resend_code(self, data: ResendCodeRequest) -> None:
        user = await self._find_user(data.email)
        if user is None or user.email_verified:
            return

        await self._check_resend_cooldown(user)
        await self._send_code(user)

    async def login(self, data: LoginRequest) -> AuthResponse:
        user = await self._find_user(data.email)
        if user is None or not verify_secret(
            data.password, user.password_hash
        ):
            raise UnauthorizedError("INVALID_CREDENTIALS")
        if not user.email_verified:
            raise PermissionDeniedError("EMAIL_NOT_VERIFIED")
        return await self._auth_response(user)

    async def _find_user(self, email: str) -> User | None:
        users = await self.users.read(email=email)
        return users[0] if users else None

    async def _find_code(self, user: User) -> EmailCode | None:
        codes = await self.codes.read(user_id=user.id)
        return codes[0] if codes else None

    async def _check_resend_cooldown(self, user: User) -> None:
        code = await self._find_code(user)
        if code is None:
            return
        wait = (
            code.sent_at
            + EMAIL_CODE_RESEND_COOLDOWN
            - datetime.now(UTC)
        )
        if wait.total_seconds() > 0:
            raise TooManyRequestsError(
                "RESEND_TOO_EARLY",
                retry_after=math.ceil(wait.total_seconds()),
            )

    async def _send_code(self, user: User) -> None:
        code = _generate_code()
        now = datetime.now(UTC)
        values = {
            "code_hash": hash_secret(code),
            "attempts": 0,
            "sent_at": now,
            "expires_at": now + EMAIL_CODE_TTL,
        }

        existing = await self._find_code(user)
        if existing is None:
            await self.codes.create(user_id=user.id, **values)
        else:
            await self.codes.update(existing.id, **values)

        try:
            await sender.send_verification_code(user.email, code)
        except Exception as exc:
            raise ServiceUnavailableError("EMAIL_SEND_FAILED") from exc

    async def _auth_response(self, user: User) -> AuthResponse:
        return AuthResponse(
            access_token=create_access_token(user.id),
            profile=await self.profiles.build(user),
        )
