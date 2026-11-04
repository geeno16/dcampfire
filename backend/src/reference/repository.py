from sqlalchemy import select

from src.bonfire.model import BonfireTopic
from src.common.repository import UNSET, Repository, Unset
from src.reference.model import Topic
from src.user.model import UserTopic


class TopicRepository(Repository[Topic]):
    model = Topic
    error_codes = {
        "topics_name_key": "TOPIC_NAME_TAKEN",
    }

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

    async def read_by_user(self, user_id: int) -> list[Topic]:
        result = await self.session.scalars(
            select(Topic)
            .join(UserTopic, UserTopic.topic_id == Topic.id)
            .where(UserTopic.user_id == user_id)
            .order_by(Topic.id)
        )
        return list(result.all())

    async def read_by_bonfires(
        self, bonfire_ids: list[int]
    ) -> dict[int, list[Topic]]:
        result = await self.session.execute(
            select(BonfireTopic.bonfire_id, Topic)
            .join(BonfireTopic, BonfireTopic.topic_id == Topic.id)
            .where(BonfireTopic.bonfire_id.in_(bonfire_ids))
            .order_by(Topic.id)
        )
        topics: dict[int, list[Topic]] = {id: [] for id in bonfire_ids}
        for bonfire_id, topic in result.all():
            topics[bonfire_id].append(topic)
        return topics
