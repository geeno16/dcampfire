from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import CurrentUserDependency
from src.common import get_session, register_exception_handlers
from src.email_code.repository import EmailCodeRepository
from src.mailer import sender
from src.user.repository import UserRepository

EMAIL = "user@test.com"
PASSWORD = "password123"


async def register(
    client: AsyncClient,
    email: str = EMAIL,
    nickname: str = "camper",
    password: str = PASSWORD,
    pd_consent: bool = True,
):
    return await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "nickname": nickname,
            "password": password,
            "pd_consent": pd_consent,
        },
    )


async def verify(client: AsyncClient, code: str, email: str = EMAIL):
    return await client.post(
        "/api/v1/auth/verify-email", json={"email": email, "code": code}
    )


async def login(
    client: AsyncClient, email: str = EMAIL, password: str = PASSWORD
):
    return await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )


def wrong(code: str) -> str:
    return "000000" if code != "000000" else "111111"


@pytest.mark.asyncio
async def test_full_registration_flow(
    async_client: AsyncClient, sent_codes: list[str]
):
    response = await register(async_client, email="User@Test.com")
    assert response.status_code == 201
    assert response.json() == {"email": EMAIL}

    response = await verify(async_client, sent_codes[-1])
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["profile"] == {
        "id": body["profile"]["id"],
        "nickname": "camper",
        "email": EMAIL,
        "avatar_url": None,
        "topics": [],
    }

    response = await login(async_client)
    assert response.status_code == 200
    assert response.json()["profile"]["id"] == body["profile"]["id"]


@pytest.mark.asyncio
async def test_register_verified_email_taken(
    async_client: AsyncClient, sent_codes: list[str]
):
    await register(async_client)
    await verify(async_client, sent_codes[-1])

    response = await register(async_client, nickname="other")
    assert response.status_code == 409
    assert response.json()["code"] == "EMAIL_TAKEN"


@pytest.mark.asyncio
async def test_register_unverified_email_overwrites(
    async_client: AsyncClient,
    db_session: AsyncSession,
    sent_codes: list[str],
):
    await register(async_client, nickname="first")

    response = await register(
        async_client, nickname="second", password="newpassword1"
    )
    assert response.status_code == 429
    assert response.json()["code"] == "RESEND_TOO_EARLY"
    assert 0 < response.json()["retry_after"] <= 60
    assert len(sent_codes) == 1
    [user] = await UserRepository(db_session).read(email=EMAIL)
    assert user.nickname == "first"

    codes = EmailCodeRepository(db_session)
    [stored] = await codes.read(user_id=user.id)
    await codes.update(
        stored.id, sent_at=datetime.now(UTC) - timedelta(minutes=2)
    )

    response = await register(
        async_client, nickname="second", password="newpassword1"
    )
    assert response.status_code == 201
    assert len(sent_codes) == 2

    response = await verify(async_client, sent_codes[-1])
    assert response.json()["profile"]["nickname"] == "second"
    assert (
        await login(async_client, password="newpassword1")
    ).status_code == 200


@pytest.mark.asyncio
async def test_register_nickname_taken(
    async_client: AsyncClient, sent_codes: list[str]
):
    await register(async_client)

    response = await register(async_client, email="other@test.com")
    assert response.status_code == 409
    assert response.json()["code"] == "NICKNAME_TAKEN"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"pd_consent": False}, "pd_consent"),
        ({"password": "short"}, "password"),
        ({"nickname": "ab"}, "nickname"),
        ({"email": "not-an-email"}, "email"),
    ],
)
async def test_register_validation_failed(
    async_client: AsyncClient,
    sent_codes: list[str],
    overrides: dict,
    field: str,
):
    response = await register(async_client, **overrides)
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_FAILED"
    assert [error["field"] for error in body["errors"]] == [field]


@pytest.mark.asyncio
async def test_register_email_send_failed(
    async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    async def broken_send(email: str, code: str) -> None:
        raise OSError("smtp down")

    monkeypatch.setattr(sender, "send_verification_code", broken_send)

    response = await register(async_client)
    assert response.status_code == 503
    assert response.json()["code"] == "EMAIL_SEND_FAILED"


@pytest.mark.asyncio
async def test_verify_wrong_code_counts_attempts(
    async_client: AsyncClient,
    db_session: AsyncSession,
    sent_codes: list[str],
):
    await register(async_client)
    code = sent_codes[-1]

    for attempts_left in range(4, -1, -1):
        response = await verify(async_client, wrong(code))
        assert response.status_code == 422
        assert response.json()["code"] == "CODE_INVALID"
        assert response.json()["attempts_left"] == attempts_left

    response = await verify(async_client, code)
    assert response.status_code == 422
    assert response.json()["code"] == "CODE_ATTEMPTS_EXCEEDED"

    user = (await UserRepository(db_session).read(email=EMAIL))[0]
    stored = (
        await EmailCodeRepository(db_session).read(user_id=user.id)
    )[0]
    assert stored.attempts == 5


@pytest.mark.asyncio
async def test_verify_expired_code(
    async_client: AsyncClient,
    db_session: AsyncSession,
    sent_codes: list[str],
):
    await register(async_client)
    user = (await UserRepository(db_session).read(email=EMAIL))[0]
    codes = EmailCodeRepository(db_session)
    stored = (await codes.read(user_id=user.id))[0]
    await codes.update(
        stored.id, expires_at=datetime.now(UTC) - timedelta(seconds=1)
    )

    response = await verify(async_client, sent_codes[-1])
    assert response.status_code == 422
    assert response.json()["code"] == "CODE_EXPIRED"


@pytest.mark.asyncio
async def test_verify_unknown_email(
    async_client: AsyncClient, sent_codes: list[str]
):
    response = await verify(
        async_client, "123456", email="nobody@test.com"
    )
    assert response.status_code == 422
    assert response.json()["code"] == "CODE_INVALID"


@pytest.mark.asyncio
async def test_resend_code(
    async_client: AsyncClient,
    db_session: AsyncSession,
    sent_codes: list[str],
):
    await register(async_client)
    old_code = sent_codes[-1]

    response = await async_client.post(
        "/api/v1/auth/resend-code", json={"email": EMAIL}
    )
    assert response.status_code == 429
    assert response.json()["code"] == "RESEND_TOO_EARLY"
    assert 0 < response.json()["retry_after"] <= 60

    user = (await UserRepository(db_session).read(email=EMAIL))[0]
    codes = EmailCodeRepository(db_session)
    stored = (await codes.read(user_id=user.id))[0]
    await codes.update(
        stored.id, sent_at=datetime.now(UTC) - timedelta(minutes=2)
    )

    response = await async_client.post(
        "/api/v1/auth/resend-code", json={"email": EMAIL}
    )
    assert response.status_code == 204
    new_code = sent_codes[-1]

    if new_code != old_code:
        assert (await verify(async_client, old_code)).status_code == 422
    assert (await verify(async_client, new_code)).status_code == 200


@pytest.mark.asyncio
async def test_resend_code_unknown_email_is_silent(
    async_client: AsyncClient, sent_codes: list[str]
):
    response = await async_client.post(
        "/api/v1/auth/resend-code", json={"email": "nobody@test.com"}
    )
    assert response.status_code == 204
    assert sent_codes == []


@pytest.mark.asyncio
async def test_login_errors(
    async_client: AsyncClient, sent_codes: list[str]
):
    await register(async_client)

    response = await login(async_client)
    assert response.status_code == 403
    assert response.json()["code"] == "EMAIL_NOT_VERIFIED"

    response = await login(async_client, password="wrongpassword")
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"

    response = await login(async_client, email="nobody@test.com")
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


@pytest_asyncio.fixture
async def protected_client(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient]:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/whoami")
    async def whoami(user: CurrentUserDependency) -> dict:
        return {"id": user.id}

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(
        transport=ASGITransport(app=app),  # ty: ignore[invalid-argument-type]
        base_url="http://test",
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_current_user_dependency(
    async_client: AsyncClient,
    protected_client: AsyncClient,
    sent_codes: list[str],
):
    await register(async_client)
    body = (await verify(async_client, sent_codes[-1])).json()

    response = await protected_client.get(
        "/whoami",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert response.status_code == 200
    assert response.json() == {"id": body["profile"]["id"]}

    for headers in ({}, {"Authorization": "Bearer garbage"}):
        response = await protected_client.get(
            "/whoami", headers=headers
        )
        assert response.status_code == 401
        assert response.json()["code"] == "UNAUTHORIZED"
