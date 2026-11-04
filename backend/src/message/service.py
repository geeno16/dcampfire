import math
from datetime import UTC, datetime

from src.bonfire.service import BonfireService
from src.common.config import MESSAGE_PAUSE
from src.common.database import SessionDependency
from src.common.exception import (
    TooManyRequestsError,
    UnprocessableError,
)
from src.message.model import Message
from src.message.repository import MessageRepository
from src.message.schema import (
    MessageRead,
    SendMessageRequest,
    SendMessageResponse,
)
from src.realtime.publisher import RealtimePublisher
from src.user.model import User
from src.user.repository import UserRepository
from src.user.service import user_brief


def _message_read(message: Message, author: User | None) -> MessageRead:
    return MessageRead(
        id=message.id,
        bonfire_id=message.bonfire_id,
        author=(user_brief(author) if author is not None else None),
        body=message.body,
        created_at=message.created_at,
    )


class MessageService:
    def __init__(self, session: SessionDependency) -> None:
        self.messages = MessageRepository(session)
        self.users = UserRepository(session)
        self.bonfire_service = BonfireService(session)
        self.realtime = RealtimePublisher(session)

    async def list_messages(
        self,
        user: User,
        bonfire_id: int,
        limit: int,
        before_id: int | None,
        after_id: int | None,
    ) -> list[MessageRead]:
        if before_id is not None and after_id is not None:
            raise UnprocessableError(
                "VALIDATION_FAILED",
                errors=[
                    {
                        "field": "after_id",
                        "message": "Use either before_id or after_id",
                    }
                ],
            )
        await self.bonfire_service.get_for_member(user, bonfire_id)
        rows = await self.messages.read_page(
            bonfire_id, limit, before_id=before_id, after_id=after_id
        )
        return [
            _message_read(message, author) for message, author in rows
        ]

    async def send(
        self, user: User, bonfire_id: int, data: SendMessageRequest
    ) -> SendMessageResponse:
        await self.users.lock(user.id)
        await self.bonfire_service.get_for_member(user, bonfire_id)

        now = datetime.now(UTC)
        last = await self.messages.read_last_by_author(user.id)
        if last is not None:
            wait = last.created_at + MESSAGE_PAUSE - now
            if wait.total_seconds() > 0:
                raise TooManyRequestsError(
                    "PAUSE_ACTIVE",
                    retry_after=math.ceil(wait.total_seconds()),
                    next_message_at=(now + wait).isoformat(),
                )

        message = await self.messages.create(
            bonfire_id=bonfire_id,
            author_id=user.id,
            body=data.body,
            created_at=now,
        )
        message_read = _message_read(message, user)
        self.realtime.message_created(
            await self.bonfire_service.member_ids(bonfire_id),
            bonfire_id,
            message_read.model_dump(mode="json"),
        )
        return SendMessageResponse(
            message=message_read,
            next_message_at=now + MESSAGE_PAUSE,
        )
