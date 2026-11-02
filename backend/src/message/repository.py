from src.common.repository import UNSET, Repository, Unset
from src.message.model import Message


class MessageRepository(Repository[Message]):
    model = Message

    async def create(
        self,
        *,
        bonfire_id: int,
        author_id: int | None,
        body: str,
    ) -> Message:
        return await self._create(
            bonfire_id=bonfire_id,
            author_id=author_id,
            body=body,
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
