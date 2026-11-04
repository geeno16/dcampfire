from typing import Annotated

from fastapi import APIRouter, Query, status

from src.auth.dependency import CurrentUserDependency
from src.common.config import (
    ID_MAX,
    MESSAGES_PAGE_DEFAULT,
    MESSAGES_PAGE_MAX,
    IdPath,
)
from src.message.dependency import MessageServiceDependency
from src.message.schema import (
    MessageRead,
    SendMessageRequest,
    SendMessageResponse,
)

CursorQuery = Annotated[int | None, Query(ge=1, le=ID_MAX)]

message_router = APIRouter(prefix="/bonfires", tags=["Message"])


@message_router.get("/{bonfire_id}/messages")
async def list_messages(
    bonfire_id: IdPath,
    user: CurrentUserDependency,
    service: MessageServiceDependency,
    before_id: CursorQuery = None,
    after_id: CursorQuery = None,
    limit: Annotated[
        int, Query(ge=1, le=MESSAGES_PAGE_MAX)
    ] = MESSAGES_PAGE_DEFAULT,
) -> list[MessageRead]:
    return await service.list_messages(
        user, bonfire_id, limit, before_id, after_id
    )


@message_router.post(
    "/{bonfire_id}/messages", status_code=status.HTTP_201_CREATED
)
async def send_message(
    bonfire_id: IdPath,
    data: SendMessageRequest,
    user: CurrentUserDependency,
    service: MessageServiceDependency,
) -> SendMessageResponse:
    return await service.send(user, bonfire_id, data)
