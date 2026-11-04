from src.album.resolver import AlbumResolver
from src.bonfire.model import Bonfire
from src.bonfire.repository import (
    BonfireRepository,
    BonfireTopicRepository,
)
from src.bonfire.schema import (
    AlbumRead,
    BonfireCard,
    BonfireCreateRequest,
    BonfireDetail,
    BonfireUpdateRequest,
    MemberRead,
    SentInvitationRead,
)
from src.common.config import (
    BONFIRE_CAPACITY,
    MESSAGE_PAUSE,
    USER_BONFIRES_MAX,
)
from src.common.database import SessionDependency
from src.common.exception import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)
from src.membership.repository import (
    BonfireMemberRepository,
    InvitationRepository,
)
from src.message.repository import MessageRepository
from src.realtime.publisher import RealtimePublisher
from src.reference.repository import TopicRepository
from src.reference.schema import TopicRead
from src.user.model import User
from src.user.repository import UserRepository
from src.user.service import avatar_url, user_brief


class BonfireService:
    def __init__(self, session: SessionDependency) -> None:
        self.bonfires = BonfireRepository(session)
        self.bonfire_topics = BonfireTopicRepository(session)
        self.members = BonfireMemberRepository(session)
        self.invitations = InvitationRepository(session)
        self.topics = TopicRepository(session)
        self.users = UserRepository(session)
        self.messages = MessageRepository(session)
        self.albums = AlbumResolver()
        self.realtime = RealtimePublisher(session)

    async def list_mine(self, user: User) -> list[BonfireCard]:
        return await self.cards(
            await self.bonfires.read_by_member(user.id)
        )

    async def recommended(
        self, user: User, limit: int, offset: int
    ) -> list[BonfireCard]:
        bonfires = await self.bonfires.read_recommended(
            user.id, BONFIRE_CAPACITY, limit, offset
        )
        return await self.cards(bonfires)

    async def create(
        self, user: User, data: BonfireCreateRequest
    ) -> BonfireDetail:
        album_title = (
            await self.albums.resolve(data.album_url)
            if data.album_url
            else None
        )

        await self.users.lock(user.id)
        if (
            await self.members.count_by_user(user.id)
            >= USER_BONFIRES_MAX
        ):
            raise ConflictError("BONFIRE_LIMIT_REACHED")

        bonfire = await self.bonfires.create(
            owner_id=user.id,
            name=data.name,
            color=data.color,
            is_open=data.is_open,
            album_url=data.album_url,
            album_title=album_title,
        )
        await self.members.create(
            bonfire_id=bonfire.id, user_id=user.id
        )
        await self._set_topics(bonfire, data.topic_ids)
        return await self.detail(bonfire, user)

    async def get(self, user: User, bonfire_id: int) -> BonfireDetail:
        return await self.detail(
            await self.get_for_member(user, bonfire_id), user
        )

    async def update(
        self, user: User, bonfire_id: int, data: BonfireUpdateRequest
    ) -> BonfireDetail:
        bonfire = await self.get_for_owner(user, bonfire_id)
        fields = data.model_fields_set

        changes: dict = {
            field: getattr(data, field)
            for field in ("name", "color", "is_open")
            if field in fields
        }
        if (
            "album_url" in fields
            and data.album_url != bonfire.album_url
        ):
            changes["album_url"] = data.album_url
            changes["album_title"] = (
                await self.albums.resolve(data.album_url)
                if data.album_url
                else None
            )

        if changes:
            await self.bonfires.update(bonfire.id, **changes)
        if "topic_ids" in fields and data.topic_ids is not None:
            await self._set_topics(bonfire, data.topic_ids)
        self.realtime.bonfire_updated(
            await self.member_ids(bonfire.id), bonfire.id
        )
        return await self.detail(bonfire, user)

    async def delete(self, user: User, bonfire_id: int) -> None:
        bonfire = await self.get_for_owner(user, bonfire_id)
        member_ids = await self.member_ids(bonfire.id)
        await self.bonfires.delete(bonfire.id)
        self.realtime.bonfire_removed(member_ids, bonfire.id, "deleted")

    async def member_ids(self, bonfire_id: int) -> list[int]:
        return [
            member.user_id
            for member in await self.members.read(bonfire_id=bonfire_id)
        ]

    async def get_for_member(
        self, user: User, bonfire_id: int
    ) -> Bonfire:
        bonfires = await self.bonfires.read(id=bonfire_id)
        is_member = bonfires and await self.members.read(
            bonfire_id=bonfire_id, user_id=user.id
        )
        if not is_member:
            raise NotFoundError("BONFIRE_NOT_FOUND")
        return bonfires[0]

    async def get_for_owner(
        self, user: User, bonfire_id: int
    ) -> Bonfire:
        bonfire = await self.get_for_member(user, bonfire_id)
        if bonfire.owner_id != user.id:
            raise PermissionDeniedError()
        return bonfire

    async def _set_topics(
        self, bonfire: Bonfire, topic_ids: list[int]
    ) -> None:
        wanted = set(topic_ids)
        current = {
            link.topic_id
            for link in await self.bonfire_topics.read(
                bonfire_id=bonfire.id
            )
        }
        for topic_id in current - wanted:
            await self.bonfire_topics.delete(bonfire.id, topic_id)
        for topic_id in topic_ids:
            if topic_id not in current:
                await self.bonfire_topics.create(
                    bonfire_id=bonfire.id, topic_id=topic_id
                )

    async def cards(self, bonfires: list[Bonfire]) -> list[BonfireCard]:
        ids = [bonfire.id for bonfire in bonfires]
        counts = await self.members.count_by_bonfires(ids)
        topics = await self.topics.read_by_bonfires(ids)
        return [
            BonfireCard(
                id=bonfire.id,
                name=bonfire.name,
                color=bonfire.color,
                is_open=bonfire.is_open,
                owner_id=bonfire.owner_id,
                members_count=counts.get(bonfire.id, 0),
                topics=[
                    TopicRead.model_validate(topic)
                    for topic in topics[bonfire.id]
                ],
            )
            for bonfire in bonfires
        ]

    async def detail(
        self, bonfire: Bonfire, user: User
    ) -> BonfireDetail:
        [card] = await self.cards([bonfire])
        members = [
            MemberRead(
                id=member_user.id,
                nickname=member_user.nickname,
                avatar_url=avatar_url(member_user.avatar_path),
                joined_at=member.joined_at,
            )
            for member, member_user in await self.members.read_with_users(
                bonfire.id
            )
        ]
        return BonfireDetail(
            **card.model_dump(),
            album=(
                AlbumRead(
                    url=bonfire.album_url, title=bonfire.album_title
                )
                if bonfire.album_url
                else None
            ),
            members=members,
            invitations=(
                [
                    SentInvitationRead(
                        user=user_brief(invitee),
                        created_at=invitation.created_at,
                    )
                    for invitation, invitee in (
                        await self.invitations.read_with_users(
                            bonfire.id
                        )
                    )
                ]
                if bonfire.owner_id == user.id
                else None
            ),
            next_message_at=await self.messages.next_message_at(
                user.id, MESSAGE_PAUSE
            ),
        )
