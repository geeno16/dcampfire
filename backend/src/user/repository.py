from datetime import datetime

from src.common.repository import UNSET, Repository, Unset
from src.user.model import User, UserTopic


class UserRepository(Repository[User]):
    model = User
    error_codes = {
        "ix_users_email": "EMAIL_TAKEN",
        "ix_users_nickname": "NICKNAME_TAKEN",
    }

    async def create(
        self,
        *,
        email: str,
        password_hash: str,
        nickname: str,
        pd_consent_at: datetime,
        avatar_path: str | None | Unset = UNSET,
        email_verified: bool | Unset = UNSET,
    ) -> User:
        return await self._create(
            email=email,
            password_hash=password_hash,
            nickname=nickname,
            pd_consent_at=pd_consent_at,
            avatar_path=avatar_path,
            email_verified=email_verified,
        )

    async def read(
        self,
        *,
        id: int | Unset = UNSET,
        email: str | Unset = UNSET,
        nickname: str | Unset = UNSET,
        avatar_path: str | None | Unset = UNSET,
        email_verified: bool | Unset = UNSET,
    ) -> list[User]:
        return await self._read(
            id=id,
            email=email,
            nickname=nickname,
            avatar_path=avatar_path,
            email_verified=email_verified,
        )

    async def update(
        self,
        id: int,
        *,
        email: str | Unset = UNSET,
        password_hash: str | Unset = UNSET,
        nickname: str | Unset = UNSET,
        avatar_path: str | None | Unset = UNSET,
        pd_consent_at: datetime | Unset = UNSET,
        email_verified: bool | Unset = UNSET,
    ) -> User | None:
        return await self._update(
            id,
            email=email,
            password_hash=password_hash,
            nickname=nickname,
            avatar_path=avatar_path,
            pd_consent_at=pd_consent_at,
            email_verified=email_verified,
        )

    async def delete(self, id: int) -> bool:
        return await self._delete(id)

    async def lock(self, id: int) -> User | None:
        return await self._lock(id=id)


class UserTopicRepository(Repository[UserTopic]):
    model = UserTopic
    error_codes = {
        "user_topics_pkey": "TOPIC_ALREADY_SELECTED",
        "user_topics_user_id_fkey": "USER_NOT_FOUND",
        "user_topics_topic_id_fkey": "TOPIC_NOT_FOUND",
    }

    async def create(self, *, user_id: int, topic_id: int) -> UserTopic:
        return await self._create(user_id=user_id, topic_id=topic_id)

    async def read(
        self,
        *,
        user_id: int | Unset = UNSET,
        topic_id: int | Unset = UNSET,
    ) -> list[UserTopic]:
        return await self._read(user_id=user_id, topic_id=topic_id)

    async def delete(self, user_id: int, topic_id: int) -> bool:
        return await self._delete((user_id, topic_id))
