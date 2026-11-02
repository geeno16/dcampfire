from abc import ABC, abstractmethod
from enum import Enum, auto

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.database import Base


class Unset(Enum):
    UNSET = auto()


UNSET = Unset.UNSET


class Repository[M: Base](ABC):
    @property
    @abstractmethod
    def model(self) -> type[M]: ...

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _create(self, **values) -> M:
        values = {k: v for k, v in values.items() if v is not UNSET}
        instance = self.model(**values)
        async with self.session.begin_nested():
            self.session.add(instance)
        return instance

    async def _read(self, **filters) -> list[M]:
        filters = {k: v for k, v in filters.items() if v is not UNSET}
        result = await self.session.scalars(
            select(self.model).filter_by(**filters)
        )
        return list(result.all())

    async def _update(self, ident, **values) -> M | None:
        instance = await self.session.get(self.model, ident)
        if instance is None:
            return None
        async with self.session.begin_nested():
            for key, value in values.items():
                if value is not UNSET:
                    setattr(instance, key, value)
        return instance

    async def _delete(self, ident) -> bool:
        instance = await self.session.get(self.model, ident)
        if instance is None:
            return False
        async with self.session.begin_nested():
            await self.session.delete(instance)
        return True
