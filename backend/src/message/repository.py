from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from src.common.repository import UNSET, Repository, Unset
from src.message.model import Message
from src.user.model import User


class MessageRepository(Repository[Message]):
    model = Message
    error_codes = {
        "messages_bonfire_id_fkey": "BONFIRE_NOT_FOUND",
        "messages_author_id_fkey": "USER_NOT_FOUND",
    }

    async def create(
        self,
        *,
        bonfire_id: int,
        author_id: int | None,
        body: str,
        created_at: datetime | Unset = UNSET,
    ) -> Message:
        return await self._create(
            bonfire_id=bonfire_id,
            author_id=author_id,
            body=body,
            created_at=created_at,
        )

    async def read(
        self,
        *,
        id: int | Unset = UNSET,
        bonfire_id: int | Unset = UNSET,
        author_id: int | None | Unset = UNSET,
    ) -> list[Message]:
        return await self._read(
            id=id,
            bonfire_id=bonfire_id,
            author_id=author_id,
        )

    async def update(
        self,
        id: int,
        *,
        body: str | Unset = UNSET,
    ) -> Message | None:
        return await self._update(id, body=body)

    async def delete(self, id: int) -> bool:
        return await self._delete(id)

    async def read_page(
        self,
        bonfire_id: int,
        limit: int,
        before_id: int | None = None,
        after_id: int | None = None,
    ) -> list[tuple[Message, User | None]]:
        query = (
            select(Message, User)
            .outerjoin(User, User.id == Message.author_id)
            .where(Message.bonfire_id == bonfire_id)
            .limit(limit)
        )
        if after_id is not None:
            query = query.where(Message.id > after_id).order_by(
                Message.id
            )
            rows = (await self.session.execute(query)).all()
        else:
            if before_id is not None:
                query = query.where(Message.id < before_id)
            query = query.order_by(Message.id.desc())
            rows = list(
                reversed((await self.session.execute(query)).all())
            )
        return [(message, user) for message, user in rows]

    async def read_last_by_author(
        self, author_id: int
    ) -> Message | None:
        return await self.session.scalar(
            select(Message)
            .where(Message.author_id == author_id)
            .order_by(Message.id.desc())
            .limit(1)
        )

    async def next_message_at(
        self, author_id: int, pause: timedelta
    ) -> datetime | None:
        last = await self.read_last_by_author(author_id)
        if last is None:
            return None
        available_at = last.created_at + pause
        return (
            available_at if available_at > datetime.now(UTC) else None
        )
