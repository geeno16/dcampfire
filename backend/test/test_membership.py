from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.membership.repository import BonfireMemberRepository
from src.user.repository import UserRepository
from test.conftest import UserFactory


async def create_bonfire(
    client: AsyncClient, headers: dict[str, str], **fields
) -> int:
    payload = {"name": "Ночные байки", "color": "orange", **fields}
    response = await client.post(
        "/api/v1/bonfires", json=payload, headers=headers
    )
    assert response.status_code == 201, response.json()
    return response.json()["id"]


async def add_member(
    session: AsyncSession, bonfire_id: int, user_id: int
):
    await BonfireMemberRepository(session).create(
        bonfire_id=bonfire_id, user_id=user_id
    )


async def join(client: AsyncClient, bonfire_id: int, headers: dict):
    return await client.post(
        f"/api/v1/bonfires/{bonfire_id}/members", headers=headers
    )


async def invite(
    client: AsyncClient, bonfire_id: int, nickname: str, headers: dict
):
    return await client.post(
        f"/api/v1/bonfires/{bonfire_id}/invitations",
        json={"nickname": nickname},
        headers=headers,
    )


async def remove(
    client: AsyncClient, bonfire_id: int, user_id: int, headers: dict
):
    return await client.delete(
        f"/api/v1/bonfires/{bonfire_id}/members/{user_id}",
        headers=headers,
    )


@pytest.mark.asyncio
async def test_join_open_bonfire(
    async_client: AsyncClient, user_factory: UserFactory
):
    owner, owner_headers = await user_factory("owner")
    guest, guest_headers = await user_factory("guest")
    bonfire_id = await create_bonfire(async_client, owner_headers)

    response = await join(async_client, bonfire_id, guest_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["members_count"] == 2
    assert [m["id"] for m in body["members"]] == [owner.id, guest.id]

    response = await join(async_client, bonfire_id, guest_headers)
    assert response.status_code == 409
    assert response.json()["code"] == "ALREADY_MEMBER"


@pytest.mark.asyncio
async def test_join_closed_bonfire_needs_invitation(
    async_client: AsyncClient, user_factory: UserFactory
):
    _, owner_headers = await user_factory("owner")
    _, guest_headers = await user_factory("guest")
    bonfire_id = await create_bonfire(
        async_client, owner_headers, is_open=False
    )

    response = await join(async_client, bonfire_id, guest_headers)
    assert response.status_code == 404
    assert response.json()["code"] == "BONFIRE_NOT_FOUND"

    await invite(async_client, bonfire_id, "guest", owner_headers)
    response = await join(async_client, bonfire_id, guest_headers)
    assert response.status_code == 201

    response = await async_client.get(
        "/api/v1/me/invitations", headers=guest_headers
    )
    assert response.json() == []


@pytest.mark.asyncio
async def test_join_missing_bonfire(
    async_client: AsyncClient, user_factory: UserFactory
):
    _, headers = await user_factory("guest")

    response = await join(async_client, 999_999_999, headers)
    assert response.status_code == 404
    assert response.json()["code"] == "BONFIRE_NOT_FOUND"


@pytest.mark.asyncio
async def test_join_full_bonfire(
    async_client: AsyncClient,
    db_session: AsyncSession,
    user_factory: UserFactory,
):
    _, owner_headers = await user_factory("owner")
    _, late_headers = await user_factory("late")
    bonfire_id = await create_bonfire(async_client, owner_headers)
    for i in range(4):
        guest, _ = await user_factory(f"guest{i}")
        await add_member(db_session, bonfire_id, guest.id)

    response = await join(async_client, bonfire_id, late_headers)
    assert response.status_code == 409
    assert response.json()["code"] == "BONFIRE_FULL"


@pytest.mark.asyncio
async def test_join_user_limit(
    async_client: AsyncClient,
    db_session: AsyncSession,
    user_factory: UserFactory,
):
    _, busy_headers = await user_factory("busy")
    _, host_headers = await user_factory("host")
    for _ in range(5):
        await create_bonfire(async_client, busy_headers)
    bonfire_id = await create_bonfire(async_client, host_headers)

    response = await join(async_client, bonfire_id, busy_headers)
    assert response.status_code == 409
    assert response.json()["code"] == "BONFIRE_LIMIT_REACHED"


@pytest.mark.asyncio
async def test_leave_bonfire(
    async_client: AsyncClient,
    db_session: AsyncSession,
    user_factory: UserFactory,
):
    owner, owner_headers = await user_factory("owner")
    guest, guest_headers = await user_factory("guest")
    bonfire_id = await create_bonfire(async_client, owner_headers)
    await add_member(db_session, bonfire_id, guest.id)

    response = await remove(
        async_client, bonfire_id, owner.id, owner_headers
    )
    assert response.status_code == 409
    assert response.json()["code"] == "OWNER_CANNOT_LEAVE"

    response = await remove(
        async_client, bonfire_id, guest.id, guest_headers
    )
    assert response.status_code == 204

    response = await async_client.get(
        f"/api/v1/bonfires/{bonfire_id}", headers=guest_headers
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_kick_member(
    async_client: AsyncClient,
    db_session: AsyncSession,
    user_factory: UserFactory,
):
    owner, owner_headers = await user_factory("owner")
    first, first_headers = await user_factory("first")
    second, _ = await user_factory("second")
    outsider, outsider_headers = await user_factory("outsider")
    bonfire_id = await create_bonfire(async_client, owner_headers)
    await add_member(db_session, bonfire_id, first.id)
    await add_member(db_session, bonfire_id, second.id)

    response = await remove(
        async_client, bonfire_id, second.id, first_headers
    )
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"

    response = await remove(
        async_client, bonfire_id, second.id, outsider_headers
    )
    assert response.status_code == 404
    assert response.json()["code"] == "BONFIRE_NOT_FOUND"

    response = await remove(
        async_client, bonfire_id, outsider.id, owner_headers
    )
    assert response.status_code == 404
    assert response.json()["code"] == "MEMBER_NOT_FOUND"

    response = await remove(
        async_client, bonfire_id, second.id, owner_headers
    )
    assert response.status_code == 204

    detail = await async_client.get(
        f"/api/v1/bonfires/{bonfire_id}", headers=owner_headers
    )
    assert [m["id"] for m in detail.json()["members"]] == [
        owner.id,
        first.id,
    ]


@pytest.mark.asyncio
async def test_invite_and_list(
    async_client: AsyncClient,
    db_session: AsyncSession,
    user_factory: UserFactory,
):
    owner, owner_headers = await user_factory("owner")
    _, guest_headers = await user_factory("guest")
    bonfire_id = await create_bonfire(
        async_client, owner_headers, name="Тихий двор", is_open=False
    )

    response = await invite(
        async_client, bonfire_id, "guest", owner_headers
    )
    assert response.status_code == 204

    response = await async_client.get(
        "/api/v1/me/invitations", headers=guest_headers
    )
    assert response.status_code == 200
    [invitation] = response.json()
    assert invitation["bonfire"]["id"] == bonfire_id
    assert invitation["bonfire"]["name"] == "Тихий двор"
    assert invitation["bonfire"]["owner_id"] == owner.id
    assert invitation["bonfire"]["members_count"] == 1
    assert invitation["owner"] == {
        "id": owner.id,
        "nickname": "owner",
        "avatar_url": None,
    }
    assert invitation["created_at"]

    response = await invite(
        async_client, bonfire_id, "guest", owner_headers
    )
    assert response.status_code == 409
    assert response.json()["code"] == "ALREADY_INVITED"

    response = await invite(
        async_client, bonfire_id, "owner", owner_headers
    )
    assert response.status_code == 409
    assert response.json()["code"] == "ALREADY_MEMBER"


@pytest.mark.asyncio
async def test_invite_errors(
    async_client: AsyncClient,
    db_session: AsyncSession,
    user_factory: UserFactory,
):
    _, owner_headers = await user_factory("owner")
    member, member_headers = await user_factory("member")
    await user_factory("target")
    await UserRepository(db_session).create(
        email="ghost@test.com",
        password_hash="unused",
        nickname="ghost",
        pd_consent_at=datetime.now(UTC),
    )
    bonfire_id = await create_bonfire(async_client, owner_headers)
    await add_member(db_session, bonfire_id, member.id)

    response = await invite(
        async_client, bonfire_id, "target", member_headers
    )
    assert response.status_code == 403

    for nickname in ("nobody", "ghost"):
        response = await invite(
            async_client, bonfire_id, nickname, owner_headers
        )
        assert response.status_code == 404
        assert response.json()["code"] == "USER_NOT_FOUND"

    for i in range(3):
        guest, _ = await user_factory(f"guest{i}")
        await add_member(db_session, bonfire_id, guest.id)
    response = await invite(
        async_client, bonfire_id, "target", owner_headers
    )
    assert response.status_code == 409
    assert response.json()["code"] == "BONFIRE_FULL"


@pytest.mark.asyncio
async def test_decline_invitation(
    async_client: AsyncClient, user_factory: UserFactory
):
    _, owner_headers = await user_factory("owner")
    _, guest_headers = await user_factory("guest")
    bonfire_id = await create_bonfire(async_client, owner_headers)
    await invite(async_client, bonfire_id, "guest", owner_headers)

    url = f"/api/v1/me/invitations/{bonfire_id}"
    response = await async_client.delete(url, headers=guest_headers)
    assert response.status_code == 204

    response = await async_client.get(
        "/api/v1/me/invitations", headers=guest_headers
    )
    assert response.json() == []

    response = await async_client.delete(url, headers=guest_headers)
    assert response.status_code == 404
    assert response.json()["code"] == "INVITATION_NOT_FOUND"


@pytest.mark.asyncio
async def test_owner_sees_sent_invitations(
    async_client: AsyncClient,
    db_session: AsyncSession,
    user_factory: UserFactory,
):
    _, owner_headers = await user_factory("owner")
    member, member_headers = await user_factory("member")
    invitee, invitee_headers = await user_factory("invitee")
    bonfire_id = await create_bonfire(async_client, owner_headers)
    await add_member(db_session, bonfire_id, member.id)
    await invite(async_client, bonfire_id, "invitee", owner_headers)
    url = f"/api/v1/bonfires/{bonfire_id}"

    response = await async_client.get(url, headers=owner_headers)
    [sent] = response.json()["invitations"]
    assert sent["user"] == {
        "id": invitee.id,
        "nickname": "invitee",
        "avatar_url": None,
    }
    assert sent["created_at"]

    response = await async_client.get(url, headers=member_headers)
    assert response.json()["invitations"] is None

    await join(async_client, bonfire_id, invitee_headers)
    response = await async_client.get(url, headers=owner_headers)
    assert response.json()["invitations"] == []


@pytest.mark.asyncio
async def test_cancel_invitation(
    async_client: AsyncClient,
    db_session: AsyncSession,
    user_factory: UserFactory,
):
    _, owner_headers = await user_factory("owner")
    member, member_headers = await user_factory("member")
    invitee, invitee_headers = await user_factory("invitee")
    bonfire_id = await create_bonfire(async_client, owner_headers)
    await add_member(db_session, bonfire_id, member.id)
    await invite(async_client, bonfire_id, "invitee", owner_headers)
    url = f"/api/v1/bonfires/{bonfire_id}/invitations/{invitee.id}"

    response = await async_client.delete(url, headers=member_headers)
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"

    response = await async_client.delete(url, headers=owner_headers)
    assert response.status_code == 204

    response = await async_client.get(
        "/api/v1/me/invitations", headers=invitee_headers
    )
    assert response.json() == []

    response = await async_client.delete(url, headers=owner_headers)
    assert response.status_code == 404
    assert response.json()["code"] == "INVITATION_NOT_FOUND"
