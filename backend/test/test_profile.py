from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.hashing import hash_secret
from src.reference.repository import TopicRepository
from src.user import service as profile_service
from src.user.repository import UserRepository
from test.conftest import USER_EMAIL, USER_PASSWORD

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16


@pytest.fixture(autouse=True)
def avatar_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(profile_service, "AVATAR_DIR", tmp_path)
    return tmp_path


async def create_topics(session: AsyncSession, count: int) -> list[int]:
    repository = TopicRepository(session)
    return [
        (await repository.create(name=f"test-topic-{i}")).id
        for i in range(count)
    ]


@pytest.mark.asyncio
async def test_profile_requires_auth(async_client: AsyncClient):
    response = await async_client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_get_profile(
    async_client: AsyncClient, auth_headers: dict[str, str]
):
    response = await async_client.get(
        "/api/v1/me", headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["nickname"] == "me_user"
    assert body["email"] == USER_EMAIL
    assert body["avatar_url"] is None
    assert body["topics"] == []


@pytest.mark.asyncio
async def test_update_nickname(
    async_client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: dict[str, str],
):
    response = await async_client.patch(
        "/api/v1/me",
        json={"nickname": "new_name"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["nickname"] == "new_name"

    await UserRepository(db_session).create(
        email="other@test.com",
        password_hash=hash_secret("password123"),
        nickname="taken",
        pd_consent_at=datetime.now(UTC),
    )
    response = await async_client.patch(
        "/api/v1/me", json={"nickname": "taken"}, headers=auth_headers
    )
    assert response.status_code == 409
    assert response.json()["code"] == "NICKNAME_TAKEN"

    response = await async_client.patch(
        "/api/v1/me", json={"nickname": "ab"}, headers=auth_headers
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_change_password(
    async_client: AsyncClient, auth_headers: dict[str, str]
):
    response = await async_client.put(
        "/api/v1/me/password",
        json={
            "current_password": "wrong-pass",
            "new_password": "newpass123",
        },
        headers=auth_headers,
    )
    assert response.status_code == 403
    assert response.json()["code"] == "WRONG_PASSWORD"

    response = await async_client.put(
        "/api/v1/me/password",
        json={
            "current_password": USER_PASSWORD,
            "new_password": "newpass123",
        },
        headers=auth_headers,
    )
    assert response.status_code == 204

    for password, status in ((USER_PASSWORD, 401), ("newpass123", 200)):
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"email": USER_EMAIL, "password": password},
        )
        assert response.status_code == status


@pytest.mark.asyncio
async def test_set_topics_replaces_list(
    async_client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: dict[str, str],
):
    first, second, third = await create_topics(db_session, 3)

    response = await async_client.put(
        "/api/v1/me/topics",
        json={"topic_ids": [first, second]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert [t["id"] for t in response.json()["topics"]] == [
        first,
        second,
    ]

    response = await async_client.put(
        "/api/v1/me/topics",
        json={"topic_ids": [second, third]},
        headers=auth_headers,
    )
    assert [t["id"] for t in response.json()["topics"]] == [
        second,
        third,
    ]

    response = await async_client.put(
        "/api/v1/me/topics",
        json={"topic_ids": []},
        headers=auth_headers,
    )
    assert response.json()["topics"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "topic_ids", [list(range(1, 12)), [1, 1], [0], [40000]]
)
async def test_set_topics_validation(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    topic_ids: list[int],
):
    response = await async_client.put(
        "/api/v1/me/topics",
        json={"topic_ids": topic_ids},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_set_topics_unknown_topic(
    async_client: AsyncClient, auth_headers: dict[str, str]
):
    response = await async_client.put(
        "/api/v1/me/topics",
        json={"topic_ids": [32767]},
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert response.json()["code"] == "TOPIC_NOT_FOUND"


@pytest.mark.asyncio
async def test_avatar_upload_replace_and_delete(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    avatar_dir: Path,
):
    response = await async_client.put(
        "/api/v1/me/avatar",
        files={"file": ("a.png", PNG, "image/png")},
        headers=auth_headers,
    )
    assert response.status_code == 200
    first_url = response.json()["avatar_url"]
    assert first_url.startswith("/api/v1/media/avatars/")
    assert first_url.endswith(".png")

    response = await async_client.get(first_url, headers=auth_headers)
    assert response.status_code == 200
    assert response.content == PNG

    response = await async_client.put(
        "/api/v1/me/avatar",
        files={"file": ("b.jpg", JPEG, "image/jpeg")},
        headers=auth_headers,
    )
    second_url = response.json()["avatar_url"]
    assert second_url.endswith(".jpg")
    assert [p.name for p in avatar_dir.iterdir()] == [
        second_url.rsplit("/", 1)[1]
    ]
    assert (
        await async_client.get(first_url, headers=auth_headers)
    ).status_code == 404

    response = await async_client.delete(
        "/api/v1/me/avatar", headers=auth_headers
    )
    assert response.status_code == 204
    assert list(avatar_dir.iterdir()) == []
    profile = (
        await async_client.get("/api/v1/me", headers=auth_headers)
    ).json()
    assert profile["avatar_url"] is None


@pytest.mark.asyncio
async def test_avatar_rejects_non_image(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    avatar_dir: Path,
):
    response = await async_client.put(
        "/api/v1/me/avatar",
        files={"file": ("a.png", b"not an image", "image/png")},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "file"
    assert list(avatar_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_avatar_rejects_large_file(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(profile_service, "AVATAR_MAX_BYTES", 10)
    response = await async_client.put(
        "/api/v1/me/avatar",
        files={"file": ("a.png", PNG, "image/png")},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_FAILED"


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["missing.png", "..%2Fsecret.png"])
async def test_avatar_not_found(
    async_client: AsyncClient, auth_headers: dict[str, str], name: str
):
    response = await async_client.get(
        f"/api/v1/media/avatars/{name}", headers=auth_headers
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_account(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    avatar_dir: Path,
):
    await async_client.put(
        "/api/v1/me/avatar",
        files={"file": ("a.png", PNG, "image/png")},
        headers=auth_headers,
    )

    response = await async_client.request(
        "DELETE",
        "/api/v1/me",
        json={"password": "wrong-pass"},
        headers=auth_headers,
    )
    assert response.status_code == 403
    assert response.json()["code"] == "WRONG_PASSWORD"

    response = await async_client.request(
        "DELETE",
        "/api/v1/me",
        json={"password": USER_PASSWORD},
        headers=auth_headers,
    )
    assert response.status_code == 204
    assert list(avatar_dir.iterdir()) == []

    response = await async_client.get(
        "/api/v1/me", headers=auth_headers
    )
    assert response.status_code == 401

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": USER_EMAIL, "password": USER_PASSWORD},
    )
    assert response.status_code == 401
