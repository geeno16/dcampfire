from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, WebSocketDisconnect
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.token import create_access_token
from src.common import on_commit, run_after_commit
from src.membership.repository import BonfireMemberRepository
from src.realtime import route as realtime_route
from src.realtime.hub import (
    ACCOUNT_DELETED_CLOSE_CODE,
    RealtimeHub,
    hub,
)
from src.user.repository import UserRepository
from test.conftest import RecordedEvents, UserFactory


class FakeSocket:
    def __init__(self, broken: bool = False) -> None:
        self.broken = broken
        self.received: list[dict] = []
        self.closed_with: int | None = None

    async def send_json(self, data: dict, mode: str = "text") -> None:
        if self.broken:
            raise RuntimeError("connection lost")
        self.received.append(data)

    async def close(
        self, code: int = 1000, reason: str | None = None
    ) -> None:
        self.closed_with = code


@pytest.mark.asyncio
async def test_hub_sends_to_every_connection_of_recipients():
    realtime = RealtimeHub()
    phone, laptop, other, broken = (
        FakeSocket(),
        FakeSocket(),
        FakeSocket(),
        FakeSocket(broken=True),
    )
    realtime.connect(1, phone)
    realtime.connect(1, laptop)
    realtime.connect(2, other)
    realtime.connect(3, broken)

    await realtime.send([1, 3, 99], {"type": "ping"})

    assert phone.received == laptop.received == [{"type": "ping"}]
    assert other.received == []
    assert realtime.connections(3) == 0


@pytest.mark.asyncio
async def test_hub_close_user():
    realtime = RealtimeHub()
    socket = FakeSocket()
    realtime.connect(1, socket)

    await realtime.close_user(1)

    assert socket.closed_with == ACCOUNT_DELETED_CLOSE_CODE
    assert realtime.connections(1) == 0


@pytest.mark.asyncio
async def test_after_commit_callbacks_survive_failures(
    db_session: AsyncSession,
):
    calls: list[str] = []

    async def broken() -> None:
        raise RuntimeError("boom")

    async def working() -> None:
        calls.append("ok")

    on_commit(db_session, broken)
    on_commit(db_session, working)
    await run_after_commit(db_session)
    await run_after_commit(db_session)

    assert calls == ["ok"]


async def create_bonfire(client: AsyncClient, headers: dict) -> int:
    response = await client.post(
        "/api/v1/bonfires",
        json={"name": "Ночные байки", "color": "orange"},
        headers=headers,
    )
    assert response.status_code == 201, response.json()
    return response.json()["id"]


async def add_member(
    session: AsyncSession, bonfire_id: int, user_id: int
):
    await BonfireMemberRepository(session).create(
        bonfire_id=bonfire_id, user_id=user_id
    )


@pytest.mark.asyncio
async def test_message_created_event(
    async_client: AsyncClient,
    db_session: AsyncSession,
    user_factory: UserFactory,
    events: RecordedEvents,
):
    owner, owner_headers = await user_factory("owner")
    guest, _ = await user_factory("guest")
    bonfire_id = await create_bonfire(async_client, owner_headers)
    await add_member(db_session, bonfire_id, guest.id)

    response = await async_client.post(
        f"/api/v1/bonfires/{bonfire_id}/messages",
        json={"body": "Привет"},
        headers=owner_headers,
    )

    [(recipients, data)] = events.of_type("message.created")
    assert recipients == {owner.id, guest.id}
    assert data["bonfire_id"] == bonfire_id
    assert data["message"] == response.json()["message"]


@pytest.mark.asyncio
async def test_failed_request_sends_nothing(
    async_client: AsyncClient,
    db_session: AsyncSession,
    user_factory: UserFactory,
    events: RecordedEvents,
):
    _, owner_headers = await user_factory("owner")
    guest, guest_headers = await user_factory("guest")
    bonfire_id = await create_bonfire(async_client, owner_headers)
    await add_member(db_session, bonfire_id, guest.id)

    await async_client.post(
        f"/api/v1/bonfires/{bonfire_id}/messages",
        json={"body": "раз"},
        headers=guest_headers,
    )
    response = await async_client.post(
        f"/api/v1/bonfires/{bonfire_id}/messages",
        json={"body": "два"},
        headers=guest_headers,
    )
    assert response.status_code == 429
    response = await async_client.patch(
        f"/api/v1/bonfires/{bonfire_id}",
        json={"name": "Захват"},
        headers=guest_headers,
    )
    assert response.status_code == 403

    assert [event["type"] for _, event in events.sent] == [
        "message.created"
    ]


@pytest.mark.asyncio
async def test_bonfire_update_and_delete_events(
    async_client: AsyncClient,
    db_session: AsyncSession,
    user_factory: UserFactory,
    events: RecordedEvents,
):
    owner, headers = await user_factory("owner")
    guest, _ = await user_factory("guest")
    bonfire_id = await create_bonfire(async_client, headers)
    await add_member(db_session, bonfire_id, guest.id)
    url = f"/api/v1/bonfires/{bonfire_id}"

    await async_client.patch(
        url, json={"name": "Новое"}, headers=headers
    )
    await async_client.delete(url, headers=headers)

    assert events.of_type("bonfire.updated") == [
        ({owner.id, guest.id}, {"bonfire_id": bonfire_id})
    ]
    assert events.of_type("bonfire.removed") == [
        (
            {owner.id, guest.id},
            {"bonfire_id": bonfire_id, "reason": "deleted"},
        )
    ]


@pytest.mark.asyncio
async def test_membership_events(
    async_client: AsyncClient,
    db_session: AsyncSession,
    user_factory: UserFactory,
    events: RecordedEvents,
):
    owner, owner_headers = await user_factory("owner")
    guest, guest_headers = await user_factory("guest")
    invitee, _ = await user_factory("invitee")
    bonfire_id = await create_bonfire(async_client, owner_headers)
    members_url = f"/api/v1/bonfires/{bonfire_id}/members"

    await async_client.post(members_url, headers=guest_headers)
    assert events.of_type("bonfire.updated")[-1] == (
        {owner.id, guest.id},
        {"bonfire_id": bonfire_id},
    )

    await async_client.post(
        f"/api/v1/bonfires/{bonfire_id}/invitations",
        json={"nickname": "invitee"},
        headers=owner_headers,
    )
    assert events.of_type("invitation.created") == [
        ({invitee.id}, {"bonfire_id": bonfire_id})
    ]

    await async_client.delete(
        f"{members_url}/{guest.id}", headers=guest_headers
    )
    assert events.of_type("bonfire.removed")[-1] == (
        {guest.id},
        {"bonfire_id": bonfire_id, "reason": "left"},
    )
    assert events.of_type("bonfire.updated")[-1] == (
        {owner.id},
        {"bonfire_id": bonfire_id},
    )

    await add_member(db_session, bonfire_id, guest.id)
    await async_client.delete(
        f"{members_url}/{guest.id}", headers=owner_headers
    )
    assert events.of_type("bonfire.removed")[-1] == (
        {guest.id},
        {"bonfire_id": bonfire_id, "reason": "kicked"},
    )


@pytest.mark.asyncio
async def test_invitation_cancel_and_decline_events(
    async_client: AsyncClient,
    user_factory: UserFactory,
    events: RecordedEvents,
):
    owner, owner_headers = await user_factory("owner")
    first, _ = await user_factory("first")
    _, second_headers = await user_factory("second")
    bonfire_id = await create_bonfire(async_client, owner_headers)
    for nickname in ("first", "second"):
        await async_client.post(
            f"/api/v1/bonfires/{bonfire_id}/invitations",
            json={"nickname": nickname},
            headers=owner_headers,
        )

    await async_client.delete(
        f"/api/v1/bonfires/{bonfire_id}/invitations/{first.id}",
        headers=owner_headers,
    )
    assert events.of_type("invitation.removed") == [
        ({first.id}, {"bonfire_id": bonfire_id})
    ]

    await async_client.delete(
        f"/api/v1/me/invitations/{bonfire_id}", headers=second_headers
    )
    assert events.of_type("bonfire.updated") == [
        ({owner.id}, {"bonfire_id": bonfire_id})
    ]


@pytest.mark.asyncio
async def test_account_deletion_events(
    async_client: AsyncClient,
    db_session: AsyncSession,
    user_factory: UserFactory,
    auth_headers: dict[str, str],
    events: RecordedEvents,
):
    [me] = await UserRepository(db_session).read(nickname="me_user")
    friend, friend_headers = await user_factory("friend")
    owned = await create_bonfire(async_client, auth_headers)
    joined = await create_bonfire(async_client, friend_headers)
    await add_member(db_session, owned, friend.id)
    await add_member(db_session, joined, me.id)

    response = await async_client.request(
        "DELETE",
        "/api/v1/me",
        json={"password": "password123"},
        headers=auth_headers,
    )
    assert response.status_code == 204

    assert events.of_type("bonfire.removed") == [
        ({friend.id}, {"bonfire_id": owned, "reason": "deleted"})
    ]
    assert events.of_type("bonfire.updated") == [
        ({friend.id}, {"bonfire_id": joined})
    ]
    assert events.closed == [me.id]


@pytest.mark.asyncio
async def test_authenticate_websocket(
    db_session: AsyncSession, user_factory: UserFactory
):
    user, headers = await user_factory("socket")

    @asynccontextmanager
    async def factory():
        yield db_session

    async def check(headers: dict[str, str]) -> int | None:
        websocket = SimpleNamespace(headers=headers)
        return await realtime_route.authenticate(websocket, factory)  # ty: ignore[invalid-argument-type]

    assert (
        await check({"authorization": headers["Authorization"]})
        == user.id
    )
    assert await check({}) is None
    assert await check({"authorization": "Bearer garbage"}) is None
    assert (
        await check(
            {"authorization": "Token " + headers["Authorization"]}
        )
        is None
    )
    assert (
        await check(
            {
                "authorization": f"Bearer {create_access_token(999_999_999)}"
            }
        )
        is None
    )


def test_websocket_lifecycle(monkeypatch: pytest.MonkeyPatch):
    async def fake_authenticate(websocket, factory) -> int | None:
        return (
            7
            if websocket.headers.get("authorization") == "Bearer ok"
            else None
        )

    monkeypatch.setattr(
        realtime_route, "authenticate", fake_authenticate
    )
    app = FastAPI()
    app.include_router(realtime_route.realtime_router, prefix="/api/v1")

    with TestClient(app) as client:
        portal = client.portal
        assert portal is not None
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/api/v1/ws"):
                pass
        assert exc_info.value.code == 1008

        with client.websocket_connect(
            "/api/v1/ws", headers={"Authorization": "Bearer ok"}
        ) as websocket:
            portal.call(
                hub.send, [7], {"type": "bonfire.updated", "data": {}}
            )
            assert websocket.receive_json() == {
                "type": "bonfire.updated",
                "data": {},
            }

            portal.call(hub.close_user, 7)
            with pytest.raises(WebSocketDisconnect) as exc_info:
                websocket.receive_json()
            assert exc_info.value.code == ACCOUNT_DELETED_CLOSE_CODE

    assert hub.connections(7) == 0
