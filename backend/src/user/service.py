import re
import uuid
from pathlib import Path

import anyio
from fastapi import UploadFile

from src.bonfire.repository import BonfireRepository
from src.common.config import AVATAR_MAX_BYTES, MEDIA_ROOT
from src.common.database import SessionDependency
from src.common.exception import (
    NotFoundError,
    PermissionDeniedError,
    UnprocessableError,
)
from src.common.hashing import hash_secret, verify_secret
from src.membership.repository import BonfireMemberRepository
from src.realtime.publisher import RealtimePublisher
from src.reference.repository import TopicRepository
from src.reference.schema import TopicRead
from src.user.model import User
from src.user.repository import UserRepository, UserTopicRepository
from src.user.schema import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    ProfileRead,
    SetTopicsRequest,
    UpdateProfileRequest,
    UserBrief,
)

AVATAR_URL_PREFIX = "/api/v1/media/avatars"
AVATAR_DIR = MEDIA_ROOT / "avatars"

_IMAGE_SIGNATURES = {
    b"\xff\xd8\xff": ".jpg",
    b"\x89PNG\r\n\x1a\n": ".png",
}
_AVATAR_NAME = re.compile(r"^[0-9a-f]{32}\.(jpg|png)$")


def avatar_url(path: str | None) -> str | None:
    return f"{AVATAR_URL_PREFIX}/{path}" if path else None


def user_brief(user: User) -> UserBrief:
    return UserBrief(
        id=user.id,
        nickname=user.nickname,
        avatar_url=avatar_url(user.avatar_path),
    )


def _invalid_avatar(message: str) -> UnprocessableError:
    return UnprocessableError(
        "VALIDATION_FAILED",
        errors=[{"field": "file", "message": message}],
    )


class ProfileService:
    def __init__(self, session: SessionDependency) -> None:
        self.users = UserRepository(session)
        self.user_topics = UserTopicRepository(session)
        self.topics = TopicRepository(session)
        self.bonfires = BonfireRepository(session)
        self.members = BonfireMemberRepository(session)
        self.realtime = RealtimePublisher(session)

    async def build(self, user: User) -> ProfileRead:
        topics = await self.topics.read_by_user(user.id)
        return ProfileRead(
            id=user.id,
            nickname=user.nickname,
            email=user.email,
            avatar_url=avatar_url(user.avatar_path),
            topics=[
                TopicRead.model_validate(topic) for topic in topics
            ],
        )

    async def update_profile(
        self, user: User, data: UpdateProfileRequest
    ) -> ProfileRead:
        await self.users.update(user.id, nickname=data.nickname)
        return await self.build(user)

    async def change_password(
        self, user: User, data: ChangePasswordRequest
    ) -> None:
        self._check_password(user, data.current_password)
        await self.users.update(
            user.id, password_hash=hash_secret(data.new_password)
        )

    async def set_topics(
        self, user: User, data: SetTopicsRequest
    ) -> ProfileRead:
        wanted = set(data.topic_ids)
        current = {
            link.topic_id
            for link in await self.user_topics.read(user_id=user.id)
        }
        for topic_id in current - wanted:
            await self.user_topics.delete(user.id, topic_id)
        for topic_id in data.topic_ids:
            if topic_id not in current:
                await self.user_topics.create(
                    user_id=user.id, topic_id=topic_id
                )
        return await self.build(user)

    async def upload_avatar(
        self, user: User, file: UploadFile
    ) -> ProfileRead:
        data = await file.read(AVATAR_MAX_BYTES + 1)
        if len(data) > AVATAR_MAX_BYTES:
            raise _invalid_avatar("File is too large")

        extension = next(
            (
                ext
                for signature, ext in _IMAGE_SIGNATURES.items()
                if data.startswith(signature)
            ),
            None,
        )
        if extension is None:
            raise _invalid_avatar(
                "Only JPEG and PNG images are allowed"
            )

        name = f"{uuid.uuid4().hex}{extension}"
        await anyio.Path(AVATAR_DIR).mkdir(parents=True, exist_ok=True)
        await anyio.Path(AVATAR_DIR / name).write_bytes(data)

        previous = user.avatar_path
        await self.users.update(user.id, avatar_path=name)
        await self._remove_avatar_file(previous)
        return await self.build(user)

    async def delete_avatar(self, user: User) -> None:
        previous = user.avatar_path
        await self.users.update(user.id, avatar_path=None)
        await self._remove_avatar_file(previous)

    async def delete_account(
        self, user: User, data: DeleteAccountRequest
    ) -> None:
        self._check_password(user, data.password)
        avatar = user.avatar_path

        for bonfire in await self.bonfires.read_by_member(user.id):
            others = [
                member.user_id
                for member in await self.members.read(
                    bonfire_id=bonfire.id
                )
                if member.user_id != user.id
            ]
            if bonfire.owner_id == user.id:
                self.realtime.bonfire_removed(
                    others, bonfire.id, "deleted"
                )
            else:
                self.realtime.bonfire_updated(others, bonfire.id)

        await self.users.delete(user.id)
        self.realtime.disconnect_user(user.id)
        await self._remove_avatar_file(avatar)

    def avatar_file(self, name: str) -> Path:
        path = AVATAR_DIR / name
        if not _AVATAR_NAME.match(name) or not path.is_file():
            raise NotFoundError("AVATAR_NOT_FOUND")
        return path

    def _check_password(self, user: User, password: str) -> None:
        if not verify_secret(password, user.password_hash):
            raise PermissionDeniedError("WRONG_PASSWORD")

    async def _remove_avatar_file(self, name: str | None) -> None:
        if name:
            await anyio.Path(AVATAR_DIR / name).unlink(missing_ok=True)
