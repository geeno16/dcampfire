from sqlalchemy import func, select

from src.bonfire.model import Bonfire
from src.common.repository import UNSET, Repository, Unset
from src.membership.model import BonfireMember, Invitation
from src.user.model import User


class BonfireMemberRepository(Repository[BonfireMember]):
    model = BonfireMember
    error_codes = {
        "bonfire_members_pkey": "ALREADY_MEMBER",
        "bonfire_members_bonfire_id_fkey": "BONFIRE_NOT_FOUND",
        "bonfire_members_user_id_fkey": "USER_NOT_FOUND",
    }

    async def create(
        self, *, bonfire_id: int, user_id: int
    ) -> BonfireMember:
        return await self._create(
            bonfire_id=bonfire_id, user_id=user_id
        )

    async def read(
        self,
        *,
        bonfire_id: int | Unset = UNSET,
        user_id: int | Unset = UNSET,
    ) -> list[BonfireMember]:
        return await self._read(bonfire_id=bonfire_id, user_id=user_id)

    async def delete(self, bonfire_id: int, user_id: int) -> bool:
        return await self._delete((bonfire_id, user_id))

    async def count_by_user(self, user_id: int) -> int:
        count = await self.session.scalar(
            select(func.count()).where(BonfireMember.user_id == user_id)
        )
        return count or 0

    async def count_by_bonfires(
        self, bonfire_ids: list[int]
    ) -> dict[int, int]:
        result = await self.session.execute(
            select(BonfireMember.bonfire_id, func.count())
            .where(BonfireMember.bonfire_id.in_(bonfire_ids))
            .group_by(BonfireMember.bonfire_id)
        )
        return {bonfire_id: count for bonfire_id, count in result.all()}

    async def read_with_users(
        self, bonfire_id: int
    ) -> list[tuple[BonfireMember, User]]:
        result = await self.session.execute(
            select(BonfireMember, User)
            .join(User, User.id == BonfireMember.user_id)
            .where(BonfireMember.bonfire_id == bonfire_id)
            .order_by(BonfireMember.joined_at, BonfireMember.user_id)
        )
        return [(member, user) for member, user in result.all()]


class InvitationRepository(Repository[Invitation]):
    model = Invitation
    error_codes = {
        "invitations_pkey": "ALREADY_INVITED",
        "invitations_bonfire_id_fkey": "BONFIRE_NOT_FOUND",
        "invitations_user_id_fkey": "USER_NOT_FOUND",
    }

    async def create(
        self, *, bonfire_id: int, user_id: int
    ) -> Invitation:
        return await self._create(
            bonfire_id=bonfire_id, user_id=user_id
        )

    async def read(
        self,
        *,
        bonfire_id: int | Unset = UNSET,
        user_id: int | Unset = UNSET,
    ) -> list[Invitation]:
        return await self._read(bonfire_id=bonfire_id, user_id=user_id)

    async def delete(self, bonfire_id: int, user_id: int) -> bool:
        return await self._delete((bonfire_id, user_id))

    async def read_with_bonfires(
        self, user_id: int
    ) -> list[tuple[Invitation, Bonfire, User]]:
        result = await self.session.execute(
            select(Invitation, Bonfire, User)
            .join(Bonfire, Bonfire.id == Invitation.bonfire_id)
            .join(User, User.id == Bonfire.owner_id)
            .where(Invitation.user_id == user_id)
            .order_by(Invitation.created_at.desc(), Bonfire.id.desc())
        )
        return [
            (invitation, bonfire, owner)
            for invitation, bonfire, owner in result.all()
        ]

    async def read_with_users(
        self, bonfire_id: int
    ) -> list[tuple[Invitation, User]]:
        result = await self.session.execute(
            select(Invitation, User)
            .join(User, User.id == Invitation.user_id)
            .where(Invitation.bonfire_id == bonfire_id)
            .order_by(Invitation.created_at, Invitation.user_id)
        )
        return [(invitation, user) for invitation, user in result.all()]
