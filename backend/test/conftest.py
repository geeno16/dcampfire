import asyncio
from collections.abc import (
    AsyncGenerator,
    Awaitable,
    Callable,
    Generator,
)
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from src import app
from src.auth.token import create_access_token
from src.common import (
    create_tables,
    discard_after_commit,
    engine,
    get_session,
    run_after_commit,
)
from src.mailer import sender
from src.realtime.hub import hub
from src.user.model import User
from src.user.repository import UserRepository

USER_EMAIL = "me@test.com"
USER_PASSWORD = "password123"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_tables() -> None:
    await create_tables()
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    async with engine.connect() as connection:
        transaction = await connection.begin()

        session_factory = async_sessionmaker(
            bind=connection,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        session = session_factory()

        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest_asyncio.fixture
async def async_client(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient]:
    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        try:
            yield db_session
        except Exception:
            discard_after_commit(db_session)
            raise
        await run_after_commit(db_session)

    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(
        transport=ASGITransport(app=app),  # ty: ignore[invalid-argument-type]
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def sent_codes(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    codes: list[str] = []

    async def fake_send(email: str, code: str) -> None:
        codes.append(code)

    monkeypatch.setattr(sender, "send_verification_code", fake_send)
    return codes


@pytest_asyncio.fixture
async def auth_headers(
    async_client: AsyncClient, sent_codes: list[str]
) -> dict[str, str]:
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": USER_EMAIL,
            "nickname": "me_user",
            "password": USER_PASSWORD,
            "pd_consent": True,
        },
    )
    response = await async_client.post(
        "/api/v1/auth/verify-email",
        json={"email": USER_EMAIL, "code": sent_codes[-1]},
    )
    return {
        "Authorization": f"Bearer {response.json()['access_token']}"
    }


UserFactory = Callable[[str], Awaitable[tuple[User, dict[str, str]]]]


@pytest.fixture
def user_factory(db_session: AsyncSession) -> UserFactory:
    async def create(nickname: str) -> tuple[User, dict[str, str]]:
        user = await UserRepository(db_session).create(
            email=f"{nickname}@test.com",
            password_hash="unused",
            nickname=nickname,
            pd_consent_at=datetime.now(UTC),
            email_verified=True,
        )
        token = create_access_token(user.id)
        return user, {"Authorization": f"Bearer {token}"}

    return create


class RecordedEvents:
    def __init__(self) -> None:
        self.sent: list[tuple[set[int], dict]] = []
        self.closed: list[int] = []

    def of_type(self, type: str) -> list[tuple[set[int], dict]]:
        return [
            (user_ids, event["data"])
            for user_ids, event in self.sent
            if event["type"] == type
        ]


@pytest.fixture
def events(monkeypatch: pytest.MonkeyPatch) -> RecordedEvents:
    recorded = RecordedEvents()

    async def send(user_ids, event) -> None:
        recorded.sent.append((set(user_ids), event))

    async def close_user(user_id: int) -> None:
        recorded.closed.append(user_id)

    monkeypatch.setattr(hub, "send", send)
    monkeypatch.setattr(hub, "close_user", close_user)
    return recorded
