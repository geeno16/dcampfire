from src.bonfire.model import Bonfire, BonfireTopic
from src.common.repository import UNSET, Repository, Unset


class BonfireRepository(Repository[Bonfire]):
    model = Bonfire

    async def create(
        self,
        *,
        owner_id: int,
        name: str,
        color: str,
        is_open: bool | Unset = UNSET,
        album_url: str | None | Unset = UNSET,
        album_title: str | None | Unset = UNSET,
    ) -> Bonfire:
        return await self._create(
            owner_id=owner_id,
            name=name,
            color=color,
            is_open=is_open,
            album_url=album_url,
            album_title=album_title,
        )

    async def read(
        self,
        *,
        id: int | Unset = UNSET,
        owner_id: int | Unset = UNSET,
        name: str | Unset = UNSET,
        color: str | Unset = UNSET,
        is_open: bool | Unset = UNSET,
        album_url: str | None | Unset = UNSET,
        album_title: str | None | Unset = UNSET,
    ) -> list[Bonfire]:
        return await self._read(
            id=id,
            owner_id=owner_id,
            name=name,
            color=color,
            is_open=is_open,
            album_url=album_url,
            album_title=album_title,
        )

    async def update(
        self,
        id: int,
        *,
        owner_id: int | Unset = UNSET,
        name: str | Unset = UNSET,
        color: str | Unset = UNSET,
        is_open: bool | Unset = UNSET,
        album_url: str | None | Unset = UNSET,
        album_title: str | None | Unset = UNSET,
    ) -> Bonfire | None:
        return await self._update(
            id,
            owner_id=owner_id,
            name=name,
            color=color,
            is_open=is_open,
            album_url=album_url,
            album_title=album_title,
        )

    async def delete(self, id: int) -> bool:
        return await self._delete(id)


class BonfireTopicRepository(Repository[BonfireTopic]):
    model = BonfireTopic

    async def create(
        self, *, bonfire_id: int, topic_id: int
    ) -> BonfireTopic:
        return await self._create(
            bonfire_id=bonfire_id, topic_id=topic_id
        )

    async def read(
        self,
        *,
        bonfire_id: int | Unset = UNSET,
        topic_id: int | Unset = UNSET,
    ) -> list[BonfireTopic]:
        return await self._read(
            bonfire_id=bonfire_id, topic_id=topic_id
        )

    async def delete(self, bonfire_id: int, topic_id: int) -> bool:
        return await self._delete((bonfire_id, topic_id))
