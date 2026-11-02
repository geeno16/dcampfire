from src.common.repository import UNSET, Repository, Unset
from src.membership.model import BonfireMember, Invitation


class BonfireMemberRepository(Repository[BonfireMember]):
    model = BonfireMember

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


class InvitationRepository(Repository[Invitation]):
    model = Invitation

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
