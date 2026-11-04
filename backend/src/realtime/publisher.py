from collections.abc import Iterable
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from src.common.database import on_commit
from src.realtime.hub import hub

EventType = Literal[
    "message.created",
    "bonfire.updated",
    "bonfire.removed",
    "invitation.created",
    "invitation.removed",
]
RemovalReason = Literal["deleted", "kicked", "left"]


class RealtimePublisher:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def publish(
        self,
        user_ids: Iterable[int],
        type: EventType,
        data: dict[str, Any],
    ) -> None:
        recipients = list(user_ids)
        event = {"type": type, "data": data}

        async def send() -> None:
            await hub.send(recipients, event)

        on_commit(self.session, send)

    def bonfire_updated(
        self, user_ids: Iterable[int], bonfire_id: int
    ) -> None:
        self.publish(
            user_ids, "bonfire.updated", {"bonfire_id": bonfire_id}
        )

    def bonfire_removed(
        self,
        user_ids: Iterable[int],
        bonfire_id: int,
        reason: RemovalReason,
    ) -> None:
        self.publish(
            user_ids,
            "bonfire.removed",
            {"bonfire_id": bonfire_id, "reason": reason},
        )

    def invitation_created(self, user_id: int, bonfire_id: int) -> None:
        self.publish(
            [user_id], "invitation.created", {"bonfire_id": bonfire_id}
        )

    def invitation_removed(self, user_id: int, bonfire_id: int) -> None:
        self.publish(
            [user_id], "invitation.removed", {"bonfire_id": bonfire_id}
        )

    def message_created(
        self,
        user_ids: Iterable[int],
        bonfire_id: int,
        message: dict[str, Any],
    ) -> None:
        self.publish(
            user_ids,
            "message.created",
            {"bonfire_id": bonfire_id, "message": message},
        )

    def disconnect_user(self, user_id: int) -> None:
        async def close() -> None:
            await hub.close_user(user_id)

        on_commit(self.session, close)
