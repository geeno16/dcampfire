import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.auth.schema import VerifyEmailRequest
from src.auth.service import AuthService
from src.common.database import session_factory
from src.common.exception import UnprocessableError
from src.common.hashing import hash_secret
from src.email_code.model import EmailCode
from src.email_code.repository import EmailCodeRepository
from src.main import app
from src.user.repository import UserRepository


def test_public_schema_exposes_database_ids_as_int64() -> None:
    schema = app.openapi()
    assert (
        schema["components"]["schemas"]["ProfileRead"]["properties"][
            "id"
        ]["format"]
        == "int64"
    )
    path = schema["paths"]["/api/v1/bonfires/{bonfire_id}"]["get"]
    assert (
        next(
            parameter
            for parameter in path["parameters"]
            if parameter["name"] == "bonfire_id"
        )["schema"]["format"]
        == "int64"
    )
    history = schema["paths"]["/api/v1/bonfires/{bonfire_id}/messages"][
        "get"
    ]
    assert "int64" in str(
        next(
            parameter
            for parameter in history["parameters"]
            if parameter["name"] == "after_id"
        )["schema"]
    )


@pytest.mark.asyncio
async def test_forged_png_header_cannot_replace_avatar(
    async_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await async_client.put(
        "/api/v1/me/avatar",
        files={
            "file": (
                "pretend.png",
                b"\x89PNG\r\n\x1a\nnot-a-picture",
                "image/png",
            )
        },
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_FAILED"
    profile = await async_client.get("/api/v1/me", headers=auth_headers)
    assert profile.json()["avatar_url"] is None


@pytest.mark.asyncio
async def test_simultaneous_wrong_codes_never_exceed_five_attempts() -> (
    None
):
    suffix = uuid4().hex[:8]
    email = f"code{suffix}@example.com"
    async with session_factory() as session, session.begin():
        user = await UserRepository(session).create(
            email=email,
            nickname=f"code{suffix}",
            password_hash=hash_secret("password123"),
            pd_consent_at=datetime.now(UTC),
        )
        user_id = user.id
        await EmailCodeRepository(session).create(
            user_id=user_id,
            code_hash=hash_secret("123456"),
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )

    async def attempt() -> str:
        async with session_factory() as session:
            try:
                async with session.begin():
                    await AuthService(session).verify_email(
                        VerifyEmailRequest(email=email, code="000000")
                    )
            except UnprocessableError as exc:
                return exc.code
        raise AssertionError("Unexpected verification success")

    try:
        outcomes = await asyncio.gather(*(attempt() for _ in range(8)))
        assert outcomes.count("CODE_INVALID") == 5
        assert outcomes.count("CODE_ATTEMPTS_EXCEEDED") == 3
        async with session_factory() as session:
            stored = await session.scalar(
                select(EmailCode).where(EmailCode.user_id == user_id)
            )
            assert stored is not None
            assert stored.attempts == 5
    finally:
        async with session_factory() as session, session.begin():
            await UserRepository(session).delete(user_id)
