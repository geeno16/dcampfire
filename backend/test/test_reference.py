import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.reference.repository import TopicRepository
from src.reference.seed import TOPICS, seed_topics


@pytest.mark.asyncio
async def test_config_is_public(async_client: AsyncClient):
    response = await async_client.get("/api/v1/config")
    assert response.status_code == 200
    body = response.json()
    assert body["limits"]["user_topics_max"] == 10
    assert body["limits"]["bonfire_capacity"] == 5
    assert body["limits"]["message_pause_seconds"] == 10
    assert [color["key"] for color in body["colors"]][:2] == [
        "orange",
        "red",
    ]


@pytest.mark.asyncio
async def test_topics_require_auth(async_client: AsyncClient):
    response = await async_client.get("/api/v1/topics")
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_topics_list(
    async_client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: dict[str, str],
):
    topic = await TopicRepository(db_session).create(name="test-topic")

    response = await async_client.get(
        "/api/v1/topics", headers=auth_headers
    )
    assert response.status_code == 200
    topics = response.json()
    assert {"id": topic.id, "name": "test-topic"} in topics
    assert [t["id"] for t in topics] == sorted(t["id"] for t in topics)


@pytest.mark.asyncio
async def test_seed_topics_is_idempotent(db_session: AsyncSession):
    await seed_topics(db_session)
    await seed_topics(db_session)

    names = [
        topic.name for topic in await TopicRepository(db_session).read()
    ]
    for name in TOPICS:
        assert names.count(name) == 1
