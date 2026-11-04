import asyncio
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import UTC, datetime

import pytest
import pytest_asyncio

from src.bonfire.repository import BonfireRepository
from src.common import session_factory
from src.common.exception import ConflictError, TooManyRequestsError
from src.membership.repository import BonfireMemberRepository
from src.membership.service import MembershipService
from src.message.repository import MessageRepository
from src.message.schema import SendMessageRequest
from src.message.service import MessageService
from src.user.repository import UserRepository

CreateUsers = Callable[[int], Awaitable[list[int]]]


@pytest.fixture(autouse=True)
def slow_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    for repository, name in (
        (BonfireMemberRepository, "count_by_user"),
        (BonfireMemberRepository, "count_by_bonfires"),
        (MessageRepository, "read_last_by_author"),
    ):
        original = getattr(repository, name)

        async def slow(self, *args, _original=original):
            result = await _original(self, *args)
            await asyncio.sleep(0.2)
            return result

        monkeypatch.setattr(repository, name, slow)


@pytest_asyncio.fixture
async def committed_users() -> AsyncGenerator[CreateUsers]:
    created: list[int] = []
    prefix = uuid.uuid4().hex[:8]

    async def create(count: int) -> list[int]:
        async with session_factory() as session, session.begin():
            repository = UserRepository(session)
            for _ in range(count):
                index = len(created)
                user = await repository.create(
                    email=f"race-{prefix}-{index}@test.com",
                    password_hash="unused",
                    nickname=f"race{prefix}{index}",
                    pd_consent_at=datetime.now(UTC),
                    email_verified=True,
                )
                created.append(user.id)
        return created[-count:]

    yield create

    async with session_factory() as session, session.begin():
        repository = UserRepository(session)
        for user_id in created:
            await repository.delete(user_id)


async def create_bonfire(owner_id: int, member_ids: list[int]) -> int:
    async with session_factory() as session, session.begin():
        bonfire = await BonfireRepository(session).create(
            owner_id=owner_id, name="Гонка", color="red"
        )
        members = BonfireMemberRepository(session)
        for user_id in [owner_id, *member_ids]:
            await members.create(bonfire_id=bonfire.id, user_id=user_id)
        return bonfire.id


async def try_join(user_id: int, bonfire_id: int) -> str:
    async with session_factory() as session, session.begin():
        [user] = await UserRepository(session).read(id=user_id)
        try:
            await MembershipService(session).join(user, bonfire_id)
        except ConflictError as exc:
            return exc.code
        return "JOINED"


async def count_members(bonfire_id: int) -> int:
    async with session_factory() as session:
        counts = await BonfireMemberRepository(
            session
        ).count_by_bonfires([bonfire_id])
        return counts.get(bonfire_id, 0)


@pytest.mark.asyncio
async def test_concurrent_joins_respect_capacity(
    committed_users: CreateUsers,
):
    owner, *members = await committed_users(4)
    bonfire_id = await create_bonfire(owner, members)
    joiners = await committed_users(4)

    results = await asyncio.gather(
        *(try_join(user_id, bonfire_id) for user_id in joiners)
    )

    assert sorted(results) == ["BONFIRE_FULL"] * 3 + ["JOINED"]
    assert await count_members(bonfire_id) == 5


@pytest.mark.asyncio
async def test_concurrent_joins_respect_user_limit(
    committed_users: CreateUsers,
):
    [user] = await committed_users(1)
    hosts = await committed_users(6)
    for host in hosts[:4]:
        await create_bonfire(host, [user])
    targets = [await create_bonfire(host, []) for host in hosts[4:]]

    results = await asyncio.gather(
        *(try_join(user, bonfire_id) for bonfire_id in targets)
    )

    assert sorted(results) == ["BONFIRE_LIMIT_REACHED", "JOINED"]


async def try_send(user_id: int, bonfire_id: int) -> str:
    async with session_factory() as session, session.begin():
        [user] = await UserRepository(session).read(id=user_id)
        try:
            await MessageService(session).send(
                user, bonfire_id, SendMessageRequest(body="гонка")
            )
        except TooManyRequestsError as exc:
            return exc.code
        return "SENT"


@pytest.mark.asyncio
async def test_concurrent_sends_respect_pause(
    committed_users: CreateUsers,
):
    [user] = await committed_users(1)
    bonfire_id = await create_bonfire(user, [])

    results = await asyncio.gather(
        *(try_send(user, bonfire_id) for _ in range(3))
    )

    assert sorted(results) == ["PAUSE_ACTIVE"] * 2 + ["SENT"]
