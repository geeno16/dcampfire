from src.common.repository import UNSET, Repository, Unset
from src.reference.model import Topic


class TopicRepository(Repository[Topic]):
    model = Topic

    async def create(self, *, name: str) -> Topic:
        return await self._create(name=name)

    async def read(
        self,
        *,
        id: int | Unset = UNSET,
        name: str | Unset = UNSET,
    ) -> list[Topic]:
        return await self._read(id=id, name=name)

    async def update(
        self,
        id: int,
        *,
        name: str | Unset = UNSET,
    ) -> Topic | None:
        return await self._update(id, name=name)

    async def delete(self, id: int) -> bool:
        return await self._delete(id)
