from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.auth.token import decode_access_token
from src.common.database import get_session_factory
from src.realtime.hub import hub
from src.user.repository import UserRepository

realtime_router = APIRouter(tags=["Realtime"])


async def authenticate(
    websocket: WebSocket, factory: async_sessionmaker[AsyncSession]
) -> int | None:
    scheme, _, token = websocket.headers.get(
        "authorization", ""
    ).partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    user_id = decode_access_token(token)
    if user_id is None:
        return None
    async with factory() as session:
        users = await UserRepository(session).read(
            id=user_id, email_verified=True
        )
    return user_id if users else None


@realtime_router.websocket("/ws")
async def realtime(
    websocket: WebSocket,
    factory: Annotated[
        async_sessionmaker[AsyncSession], Depends(get_session_factory)
    ],
) -> None:
    user_id = await authenticate(websocket, factory)
    if user_id is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    hub.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(user_id, websocket)
