from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from enum import Enum, auto
from typing import ClassVar

from asyncpg.exceptions import (
    ForeignKeyViolationError,
    UniqueViolationError,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.database import Base
from src.common.exception import AppError, ConflictError, NotFoundError


class Unset(Enum):
    UNSET = auto()


UNSET = Unset.UNSET


class Repository[M: Base](ABC):
    error_codes: ClassVar[dict[str, str]] = {}

    @property
    @abstractmethod
    def model(self) -> type[M]: ...

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _create(self, **values) -> M:
        values = {k: v for k, v in values.items() if v is not UNSET}
        instance = self.model(**values)
        async with self._write():
            self.session.add(instance)
        return instance

    async def _read(self, **filters) -> list[M]:
        filters = {k: v for k, v in filters.items() if v is not UNSET}
        result = await self.session.scalars(
            select(self.model).filter_by(**filters)
        )
        return list(result.all())

    async def _lock(self, **filters) -> M | None:
        return await self.session.scalar(
            select(self.model)
            .filter_by(**filters)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def _update(self, ident, **values) -> M | None:
        instance = await self.session.get(self.model, ident)
        if instance is None:
            return None
        async with self._write():
            for key, value in values.items():
                if value is not UNSET:
                    setattr(instance, key, value)
        return instance

    async def _delete(self, ident) -> bool:
        instance = await self.session.get(self.model, ident)
        if instance is None:
            return False
        async with self._write():
            await self.session.delete(instance)
        return True

    @asynccontextmanager
    async def _write(self) -> AsyncGenerator[None]:
        try:
            async with self.session.begin_nested():
                yield
        except IntegrityError as exc:
            error = self._translate(exc)
            if error is None:
                raise
            raise error from exc

    def _translate(self, exc: IntegrityError) -> AppError | None:
        cause = exc.orig.__cause__ if exc.orig is not None else None
        match cause:
            case UniqueViolationError():
                error_class = ConflictError
            case ForeignKeyViolationError():
                error_class = NotFoundError
            case _:
                return None
        return error_class(
            self.error_codes.get(getattr(cause, "constraint_name", ""))
        )
