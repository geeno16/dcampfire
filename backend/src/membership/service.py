from src.bonfire.repository import BonfireRepository
from src.bonfire.schema import BonfireDetail
from src.bonfire.service import BonfireService
from src.common.config import BONFIRE_CAPACITY, USER_BONFIRES_MAX
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
from src.membership.schema import InvitationRead, InviteRequest
from src.realtime.publisher import RealtimePublisher
from src.user.model import User
from src.user.repository import UserRepository
from src.user.service import user_brief


class MembershipService:
    def __init__(self, session: SessionDependency) -> None:
        self.bonfires = BonfireRepository(session)
        self.members = BonfireMemberRepository(session)
        self.invitations = InvitationRepository(session)
        self.users = UserRepository(session)
        self.bonfire_service = BonfireService(session)
        self.realtime = RealtimePublisher(session)

    async def join(self, user: User, bonfire_id: int) -> BonfireDetail:
        await self.users.lock(user.id)
        bonfire = await self.bonfires.lock(bonfire_id)
        if bonfire is None:
            raise NotFoundError("BONFIRE_NOT_FOUND")

        if await self.members.read(
            bonfire_id=bonfire_id, user_id=user.id
        ):
            raise ConflictError("ALREADY_MEMBER")
        invited = bool(
            await self.invitations.read(
                bonfire_id=bonfire_id, user_id=user.id
            )
        )
        if not bonfire.is_open and not invited:
            raise NotFoundError("BONFIRE_NOT_FOUND")
        if await self._members_count(bonfire_id) >= BONFIRE_CAPACITY:
            raise ConflictError("BONFIRE_FULL")
        if (
            await self.members.count_by_user(user.id)
            >= USER_BONFIRES_MAX
        ):
            raise ConflictError("BONFIRE_LIMIT_REACHED")

        await self.members.create(
            bonfire_id=bonfire_id, user_id=user.id
        )
        if invited:
            await self.invitations.delete(bonfire_id, user.id)
        self.realtime.bonfire_updated(
            await self.bonfire_service.member_ids(bonfire_id),
            bonfire_id,
        )
        return await self.bonfire_service.detail(bonfire, user)

    async def remove_member(
        self, user: User, bonfire_id: int, member_id: int
    ) -> None:
        bonfire = await self.bonfire_service.get_for_member(
            user, bonfire_id
        )

        if member_id == user.id:
            if bonfire.owner_id == user.id:
                raise ConflictError("OWNER_CANNOT_LEAVE")
        elif bonfire.owner_id != user.id:
            raise PermissionDeniedError()

        if not await self.members.delete(bonfire_id, member_id):
            raise NotFoundError("MEMBER_NOT_FOUND")

        self.realtime.bonfire_removed(
            [member_id],
            bonfire_id,
            "left" if member_id == user.id else "kicked",
        )
        self.realtime.bonfire_updated(
            await self.bonfire_service.member_ids(bonfire_id),
            bonfire_id,
        )

    async def invite(
        self, user: User, bonfire_id: int, data: InviteRequest
    ) -> None:
        await self.bonfire_service.get_for_owner(user, bonfire_id)

        targets = await self.users.read(
            nickname=data.nickname, email_verified=True
        )
        if not targets:
            raise NotFoundError("USER_NOT_FOUND")
        target = targets[0]

        if await self.members.read(
            bonfire_id=bonfire_id, user_id=target.id
        ):
            raise ConflictError("ALREADY_MEMBER")
        if await self.invitations.read(
            bonfire_id=bonfire_id, user_id=target.id
        ):
            raise ConflictError("ALREADY_INVITED")
        if await self._members_count(bonfire_id) >= BONFIRE_CAPACITY:
            raise ConflictError("BONFIRE_FULL")

        await self.invitations.create(
            bonfire_id=bonfire_id, user_id=target.id
        )
        self.realtime.invitation_created(target.id, bonfire_id)

    async def list_invitations(
        self, user: User
    ) -> list[InvitationRead]:
        rows = await self.invitations.read_with_bonfires(user.id)
        cards = await self.bonfire_service.cards(
            [bonfire for _, bonfire, _ in rows]
        )
        return [
            InvitationRead(
                bonfire=card,
                owner=user_brief(owner),
                created_at=invitation.created_at,
            )
            for (invitation, _, owner), card in zip(
                rows, cards, strict=True
            )
        ]

    async def decline_invitation(
        self, user: User, bonfire_id: int
    ) -> None:
        if not await self.invitations.delete(bonfire_id, user.id):
            raise NotFoundError("INVITATION_NOT_FOUND")
        bonfires = await self.bonfires.read(id=bonfire_id)
        if bonfires:
            self.realtime.bonfire_updated(
                [bonfires[0].owner_id], bonfire_id
            )

    async def cancel_invitation(
        self, user: User, bonfire_id: int, invitee_id: int
    ) -> None:
        await self.bonfire_service.get_for_owner(user, bonfire_id)
        if not await self.invitations.delete(bonfire_id, invitee_id):
            raise NotFoundError("INVITATION_NOT_FOUND")
        self.realtime.invitation_removed(invitee_id, bonfire_id)

    async def _members_count(self, bonfire_id: int) -> int:
        counts = await self.members.count_by_bonfires([bonfire_id])
        return counts.get(bonfire_id, 0)
