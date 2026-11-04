import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.album.resolver import AlbumResolver
from src.bonfire.repository import BonfireRepository
from src.membership.repository import BonfireMemberRepository
from src.reference.repository import TopicRepository
from src.user.repository import UserTopicRepository
from test.conftest import UserFactory

ALBUM_URL = "https://music.yandex.ru/album/3389005"


@pytest.fixture(autouse=True)
def album_api(monkeypatch: pytest.MonkeyPatch) -> dict:
    state = {"response": None}

    def handler(_: httpx.Request) -> httpx.Response:
        return state["response"] or httpx.Response(
            200,
            json={
                "result": {
                    "title": "Pablo Honey",
                    "artists": [{"name": "Radiohead"}],
                }
            },
        )

    monkeypatch.setattr(
        AlbumResolver, "transport", httpx.MockTransport(handler)
    )
    return state


async def create_topics(session: AsyncSession, count: int) -> list[int]:
    repository = TopicRepository(session)
    return [
        (await repository.create(name=f"bonfire-topic-{i}")).id
        for i in range(count)
    ]


async def create_bonfire(
    client: AsyncClient, headers: dict[str, str], **fields
) -> dict:
    payload = {"name": "Ночные байки", "color": "orange", **fields}
    response = await client.post(
        "/api/v1/bonfires", json=payload, headers=headers
    )
    assert response.status_code == 201, response.json()
    return response.json()


async def add_member(
    session: AsyncSession, bonfire_id: int, user_id: int
):
    await BonfireMemberRepository(session).create(
        bonfire_id=bonfire_id, user_id=user_id
    )


@pytest.mark.asyncio
async def test_create_bonfire(
    async_client: AsyncClient,
    db_session: AsyncSession,
    user_factory: UserFactory,
):
    owner, headers = await user_factory("owner")
    topics = await create_topics(db_session, 2)

    body = await create_bonfire(
        async_client,
        headers,
        topic_ids=topics,
        album_url=ALBUM_URL,
        is_open=False,
    )

    assert body["name"] == "Ночные байки"
    assert body["color"] == "orange"
    assert body["is_open"] is False
    assert body["owner_id"] == owner.id
    assert body["members_count"] == 1
    assert [t["id"] for t in body["topics"]] == topics
    assert body["album"] == {
        "url": ALBUM_URL,
        "title": "Pablo Honey — Radiohead",
    }
    assert [m["id"] for m in body["members"]] == [owner.id]
    assert body["members"][0]["joined_at"]
    assert body["next_message_at"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fields",
    [
        {"name": "ab"},
        {"name": "x" * 41},
        {"color": "black"},
        {"topic_ids": [1, 2, 3, 4, 5, 6]},
        {"topic_ids": [1, 1]},
        {"album_url": "https://example.com/album/1"},
    ],
)
async def test_create_bonfire_validation(
    async_client: AsyncClient, user_factory: UserFactory, fields: dict
):
    _, headers = await user_factory("owner")
    payload = {"name": "Ночные байки", "color": "orange", **fields}

    response = await async_client.post(
        "/api/v1/bonfires", json=payload, headers=headers
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_create_bonfire_unknown_topic(
    async_client: AsyncClient, user_factory: UserFactory
):
    _, headers = await user_factory("owner")

    response = await async_client.post(
        "/api/v1/bonfires",
        json={
            "name": "Ночные байки",
            "color": "red",
            "topic_ids": [32767],
        },
        headers=headers,
    )
    assert response.status_code == 404
    assert response.json()["code"] == "TOPIC_NOT_FOUND"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("api_response", "status", "code"),
    [
        (
            httpx.Response(
                200, json={"result": {"error": "not-found"}}
            ),
            404,
            "ALBUM_NOT_FOUND",
        ),
        (httpx.Response(503), 503, "ALBUM_LOOKUP_FAILED"),
    ],
)
async def test_create_bonfire_album_errors(
    async_client: AsyncClient,
    db_session: AsyncSession,
    user_factory: UserFactory,
    album_api: dict,
    api_response: httpx.Response,
    status: int,
    code: str,
):
    owner, headers = await user_factory("owner")
    album_api["response"] = api_response

    response = await async_client.post(
        "/api/v1/bonfires",
        json={
            "name": "Ночные байки",
            "color": "red",
            "album_url": ALBUM_URL,
        },
        headers=headers,
    )
    assert response.status_code == status
    assert response.json()["code"] == code
    assert (
        await BonfireRepository(db_session).read(owner_id=owner.id)
        == []
    )


@pytest.mark.asyncio
async def test_bonfire_limit(
    async_client: AsyncClient,
    db_session: AsyncSession,
    user_factory: UserFactory,
):
    user, headers = await user_factory("busy")
    other, other_headers = await user_factory("other")
    for _ in range(2):
        await create_bonfire(async_client, headers)
    for _ in range(3):
        bonfire = await create_bonfire(async_client, other_headers)
        await add_member(db_session, bonfire["id"], user.id)

    response = await async_client.post(
        "/api/v1/bonfires",
        json={"name": "Шестой", "color": "red"},
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["code"] == "BONFIRE_LIMIT_REACHED"


@pytest.mark.asyncio
async def test_get_bonfire_access(
    async_client: AsyncClient,
    db_session: AsyncSession,
    user_factory: UserFactory,
):
    _, owner_headers = await user_factory("owner")
    member, member_headers = await user_factory("member")
    _, stranger_headers = await user_factory("stranger")
    bonfire = await create_bonfire(async_client, owner_headers)
    await add_member(db_session, bonfire["id"], member.id)

    response = await async_client.get(
        f"/api/v1/bonfires/{bonfire['id']}", headers=member_headers
    )
    assert response.status_code == 200
    assert response.json()["members_count"] == 2
    assert member.id in [m["id"] for m in response.json()["members"]]

    for url in (
        f"/api/v1/bonfires/{bonfire['id']}",
        "/api/v1/bonfires/999999999",
    ):
        response = await async_client.get(url, headers=stranger_headers)
        assert response.status_code == 404
        assert response.json()["code"] == "BONFIRE_NOT_FOUND"


@pytest.mark.asyncio
async def test_update_bonfire(
    async_client: AsyncClient,
    db_session: AsyncSession,
    user_factory: UserFactory,
    album_api: dict,
):
    _, headers = await user_factory("owner")
    first, second = await create_topics(db_session, 2)
    bonfire = await create_bonfire(
        async_client, headers, topic_ids=[first], album_url=ALBUM_URL
    )
    url = f"/api/v1/bonfires/{bonfire['id']}"

    response = await async_client.patch(
        url, json={"name": "Новое имя"}, headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Новое имя"
    assert body["color"] == "orange"
    assert [t["id"] for t in body["topics"]] == [first]
    assert body["album"]["title"] == "Pablo Honey — Radiohead"

    album_api["response"] = httpx.Response(503)
    response = await async_client.patch(
        url,
        json={
            "topic_ids": [second],
            "is_open": False,
            "album_url": ALBUM_URL,
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert [t["id"] for t in body["topics"]] == [second]
    assert body["is_open"] is False

    response = await async_client.patch(
        url, json={"album_url": None}, headers=headers
    )
    assert response.json()["album"] is None

    response = await async_client.patch(
        url, json={"name": None}, headers=headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_and_delete_owner_only(
    async_client: AsyncClient,
    db_session: AsyncSession,
    user_factory: UserFactory,
):
    _, owner_headers = await user_factory("owner")
    member, member_headers = await user_factory("member")
    _, stranger_headers = await user_factory("stranger")
    bonfire = await create_bonfire(async_client, owner_headers)
    await add_member(db_session, bonfire["id"], member.id)
    url = f"/api/v1/bonfires/{bonfire['id']}"

    response = await async_client.patch(
        url, json={"name": "Захват"}, headers=member_headers
    )
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"

    response = await async_client.delete(url, headers=member_headers)
    assert response.status_code == 403

    response = await async_client.delete(url, headers=stranger_headers)
    assert response.status_code == 404

    response = await async_client.delete(url, headers=owner_headers)
    assert response.status_code == 204

    response = await async_client.get(url, headers=owner_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_my_bonfires(
    async_client: AsyncClient,
    db_session: AsyncSession,
    user_factory: UserFactory,
):
    me, headers = await user_factory("me")
    _, other_headers = await user_factory("other")
    owned = await create_bonfire(async_client, headers, name="Свой")
    joined = await create_bonfire(
        async_client, other_headers, name="Чужой"
    )
    await create_bonfire(async_client, other_headers, name="Не мой")
    await add_member(db_session, joined["id"], me.id)

    response = await async_client.get(
        "/api/v1/me/bonfires", headers=headers
    )
    assert response.status_code == 200
    cards = {card["id"]: card for card in response.json()}
    assert set(cards) == {owned["id"], joined["id"]}
    assert cards[owned["id"]]["owner_id"] == me.id
    assert cards[joined["id"]]["members_count"] == 2


@pytest.mark.asyncio
async def test_recommended(
    async_client: AsyncClient,
    db_session: AsyncSession,
    user_factory: UserFactory,
):
    me, headers = await user_factory("me")
    host, host_headers = await user_factory("host")
    a, b, c = await create_topics(db_session, 3)
    await UserTopicRepository(db_session).create(
        user_id=me.id, topic_id=a
    )
    await UserTopicRepository(db_session).create(
        user_id=me.id, topic_id=b
    )

    two_common = await create_bonfire(
        async_client, host_headers, topic_ids=[a, b, c]
    )
    one_common = await create_bonfire(
        async_client, host_headers, topic_ids=[b, c]
    )
    no_common = await create_bonfire(
        async_client, host_headers, topic_ids=[c]
    )
    closed = await create_bonfire(
        async_client, host_headers, topic_ids=[a, b], is_open=False
    )
    joined = await create_bonfire(
        async_client, host_headers, topic_ids=[a]
    )
    await add_member(db_session, joined["id"], me.id)

    _, filler_headers = await user_factory("filler")
    full = await create_bonfire(
        async_client, filler_headers, topic_ids=[a, b]
    )
    for i in range(4):
        guest, _ = await user_factory(f"guest{i}")
        await add_member(db_session, full["id"], guest.id)

    response = await async_client.get(
        "/api/v1/bonfires/recommended",
        params={"limit": 50},
        headers=headers,
    )
    assert response.status_code == 200
    test_ids = {
        two_common["id"],
        one_common["id"],
        no_common["id"],
        closed["id"],
        joined["id"],
        full["id"],
    }
    ids = [
        card["id"] for card in response.json() if card["id"] in test_ids
    ]
    assert ids == [two_common["id"], one_common["id"], no_common["id"]]

    response = await async_client.get(
        "/api/v1/bonfires/recommended",
        params={"limit": 1, "offset": 0},
        headers=headers,
    )
    assert len(response.json()) == 1

    response = await async_client.get(
        "/api/v1/bonfires/recommended",
        params={"limit": 0},
        headers=headers,
    )
    assert response.status_code == 422
