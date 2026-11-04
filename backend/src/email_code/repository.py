from datetime import datetime

from src.common.repository import UNSET, Repository, Unset
from src.email_code.model import EmailCode


class EmailCodeRepository(Repository[EmailCode]):
    model = EmailCode
    error_codes = {
        "email_codes_user_id_fkey": "USER_NOT_FOUND",
    }

    async def create(
        self,
        *,
        user_id: int,
        code_hash: str,
        expires_at: datetime,
        attempts: int | Unset = UNSET,
        sent_at: datetime | Unset = UNSET,
    ) -> EmailCode:
        return await self._create(
            user_id=user_id,
            code_hash=code_hash,
            expires_at=expires_at,
            attempts=attempts,
            sent_at=sent_at,
        )

    async def read(
        self,
        *,
        id: int | Unset = UNSET,
        user_id: int | Unset = UNSET,
    ) -> list[EmailCode]:
        return await self._read(id=id, user_id=user_id)

    async def update(
        self,
        id: int,
        *,
        code_hash: str | Unset = UNSET,
        attempts: int | Unset = UNSET,
        sent_at: datetime | Unset = UNSET,
        expires_at: datetime | Unset = UNSET,
    ) -> EmailCode | None:
        return await self._update(
            id,
            code_hash=code_hash,
            attempts=attempts,
            sent_at=sent_at,
            expires_at=expires_at,
        )

    async def delete(self, id: int) -> bool:
        return await self._delete(id)
