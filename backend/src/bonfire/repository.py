from sqlalchemy import func, select

from src.bonfire.model import Bonfire, BonfireTopic
from src.common.repository import UNSET, Repository, Unset
from src.membership.model import BonfireMember
from src.user.model import UserTopic


class BonfireRepository(Repository[Bonfire]):
    model = Bonfire
    error_codes = {
        "bonfires_owner_id_fkey": "USER_NOT_FOUND",
    }

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

    async def lock(self, id: int) -> Bonfire | None:
        return await self._lock(id=id)

    async def read_by_member(self, user_id: int) -> list[Bonfire]:
        result = await self.session.scalars(
            select(Bonfire)
            .join(BonfireMember, BonfireMember.bonfire_id == Bonfire.id)
            .where(BonfireMember.user_id == user_id)
            .order_by(Bonfire.created_at.desc(), Bonfire.id.desc())
        )
        return list(result.all())

    async def read_recommended(
        self, user_id: int, capacity: int, limit: int, offset: int
    ) -> list[Bonfire]:
        user_topics = select(UserTopic.topic_id).where(
            UserTopic.user_id == user_id
        )
        user_bonfires = select(BonfireMember.bonfire_id).where(
            BonfireMember.user_id == user_id
        )
        members_count = (
            select(func.count())
            .where(BonfireMember.bonfire_id == Bonfire.id)
            .correlate(Bonfire)
            .scalar_subquery()
        )
        common_topics = func.count(BonfireTopic.topic_id)
        result = await self.session.scalars(
            select(Bonfire)
            .outerjoin(
                BonfireTopic,
                (BonfireTopic.bonfire_id == Bonfire.id)
                & BonfireTopic.topic_id.in_(user_topics),
            )
            .where(
                Bonfire.is_open.is_(True),
                Bonfire.id.not_in(user_bonfires),
                members_count < capacity,
            )
            .group_by(Bonfire.id)
            .order_by(
                common_topics.desc(),
                Bonfire.created_at.desc(),
                Bonfire.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(result.all())


class BonfireTopicRepository(Repository[BonfireTopic]):
    model = BonfireTopic
    error_codes = {
        "bonfire_topics_pkey": "TOPIC_ALREADY_ADDED",
        "bonfire_topics_bonfire_id_fkey": "BONFIRE_NOT_FOUND",
        "bonfire_topics_topic_id_fkey": "TOPIC_NOT_FOUND",
    }

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
