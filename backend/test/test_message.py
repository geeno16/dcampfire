from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.membership.repository import BonfireMemberRepository
from src.message.model import Message
from src.message.repository import MessageRepository
from src.user.repository import UserRepository
from test.conftest import UserFactory


async def create_bonfire(
    client: AsyncClient, headers: dict[str, str]
) -> int:
    response = await client.post(
        "/api/v1/bonfires",
        json={"name": "Ночные байки", "color": "orange"},
        headers=headers,
    )
    assert response.status_code == 201, response.json()
    return response.json()["id"]


async def send(
    client: AsyncClient, bonfire_id: int, body: str, headers: dict
):
    return await client.post(
        f"/api/v1/bonfires/{bonfire_id}/messages",
        json={"body": body},
        headers=headers,
    )


async def history(
    client: AsyncClient, bonfire_id: int, headers: dict, **params
):
    return await client.get(
        f"/api/v1/bonfires/{bonfire_id}/messages",
        params=params,
        headers=headers,
    )


async def expire_pause(session: AsyncSession, author_id: int) -> None:
    await session.execute(
        update(Message)
        .where(Message.author_id == author_id)
        .values(created_at=datetime.now(UTC) - timedelta(seconds=11))
    )


async def seed_messages(
    session: AsyncSession, bonfire_id: int, author_id: int, count: int
) -> list[int]:
    repository = MessageRepository(session)
    return [
        (
            await repository.create(
                bonfire_id=bonfire_id,
                author_id=author_id,
                body=f"message {i}",
                created_at=datetime.now(UTC) - timedelta(minutes=5),
            )
        ).id
        for i in range(count)
    ]


@pytest.mark.asyncio
async def test_send_message(
    async_client: AsyncClient, user_factory: UserFactory
):
    user, headers = await user_factory("author")
    bonfire_id = await create_bonfire(async_client, headers)

    response = await send(
        async_client, bonfire_id, "  Привет у костра  ", headers
    )
    assert response.status_code == 201
    body = response.json()
    message = body["message"]
    assert message["body"] == "Привет у костра"
    assert message["bonfire_id"] == bonfire_id
    assert message["author"] == {
        "id": user.id,
        "nickname": "author",
        "avatar_url": None,
    }
    created_at = datetime.fromisoformat(message["created_at"])
    next_at = datetime.fromisoformat(body["next_message_at"])
    assert next_at - created_at == timedelta(seconds=10)


@pytest.mark.asyncio
async def test_pause_is_per_user_across_bonfires(
    async_client: AsyncClient,
    db_session: AsyncSession,
    user_factory: UserFactory,
):
    user, headers = await user_factory("author")
    _, other_headers = await user_factory("other")
    first = await create_bonfire(async_client, headers)
    second = await create_bonfire(async_client, headers)
    await create_bonfire(async_client, other_headers)

    assert (
        await send(async_client, first, "раз", headers)
    ).status_code == 201

    for bonfire_id in (first, second):
        response = await send(async_client, bonfire_id, "два", headers)
        assert response.status_code == 429
        assert response.json()["code"] == "PAUSE_ACTIVE"
        assert 1 <= response.json()["retry_after"] <= 10
        assert response.json()["next_message_at"]

    detail = await async_client.get(
        f"/api/v1/bonfires/{second}", headers=headers
    )
    assert detail.json()["next_message_at"] is not None

    await expire_pause(db_session, user.id)
    assert (
        await send(async_client, second, "три", headers)
    ).status_code == 201


@pytest.mark.asyncio
async def test_next_message_at_without_messages(
    async_client: AsyncClient, user_factory: UserFactory
):
    _, headers = await user_factory("author")
    bonfire_id = await create_bonfire(async_client, headers)

    detail = await async_client.get(
        f"/api/v1/bonfires/{bonfire_id}", headers=headers
    )
    assert detail.json()["next_message_at"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("body", ["", "   ", "x" * 1001])
async def test_send_validation(
    async_client: AsyncClient, user_factory: UserFactory, body: str
):
    _, headers = await user_factory("author")
    bonfire_id = await create_bonfire(async_client, headers)

    response = await send(async_client, bonfire_id, body, headers)
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_messages_only_for_members(
    async_client: AsyncClient, user_factory: UserFactory
):
    _, owner_headers = await user_factory("owner")
    _, stranger_headers = await user_factory("stranger")
    bonfire_id = await create_bonfire(async_client, owner_headers)

    response = await send(
        async_client, bonfire_id, "чужой", stranger_headers
    )
    assert response.status_code == 404
    assert response.json()["code"] == "BONFIRE_NOT_FOUND"

    response = await history(async_client, bonfire_id, stranger_headers)
    assert response.status_code == 404
    assert response.json()["code"] == "BONFIRE_NOT_FOUND"


@pytest.mark.asyncio
async def test_history_pagination(
    async_client: AsyncClient,
    db_session: AsyncSession,
    user_factory: UserFactory,
):
    user, headers = await user_factory("author")
    bonfire_id = await create_bonfire(async_client, headers)
    ids = await seed_messages(db_session, bonfire_id, user.id, 5)

    def page_ids(response) -> list[int]:
        assert response.status_code == 200
        return [message["id"] for message in response.json()]

    assert (
        page_ids(await history(async_client, bonfire_id, headers))
        == ids
    )
    assert (
        page_ids(
            await history(async_client, bonfire_id, headers, limit=2)
        )
        == ids[-2:]
    )
    assert (
        page_ids(
            await history(
                async_client,
                bonfire_id,
                headers,
                before_id=ids[3],
                limit=2,
            )
        )
        == ids[1:3]
    )
    assert (
        page_ids(
            await history(
                async_client,
                bonfire_id,
                headers,
                after_id=ids[1],
                limit=2,
            )
        )
        == ids[2:4]
    )

    response = await history(
        async_client,
        bonfire_id,
        headers,
        before_id=ids[3],
        after_id=ids[1],
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_FAILED"

    for params in ({"limit": 0}, {"limit": 101}, {"before_id": 0}):
        response = await history(
            async_client, bonfire_id, headers, **params
        )
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_history_of_deleted_author(
    async_client: AsyncClient,
    db_session: AsyncSession,
    user_factory: UserFactory,
):
    _, owner_headers = await user_factory("owner")
    guest, _ = await user_factory("guest")
    bonfire_id = await create_bonfire(async_client, owner_headers)
    await BonfireMemberRepository(db_session).create(
        bonfire_id=bonfire_id, user_id=guest.id
    )
    await seed_messages(db_session, bonfire_id, guest.id, 1)
    await UserRepository(db_session).delete(guest.id)

    response = await history(async_client, bonfire_id, owner_headers)
    [message] = response.json()
    assert message["author"] is None
    assert message["body"] == "message 0"
