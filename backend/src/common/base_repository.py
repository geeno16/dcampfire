from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.database import Base


class BaseRepository[ModelT: Base, WriteT: BaseModel]:
    model: type[ModelT]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, id: int) -> ModelT | None:
        return await self.session.get(self.model, id)

    async def create(self, data: WriteT) -> ModelT:
        instance = self.model(**data.model_dump())
        self.session.add(instance)
        await self.session.commit()
        await self.session.refresh(instance)
        return instance

    async def update_by_id(
        self, id: int, data: WriteT
    ) -> ModelT | None:
        instance = await self.get_by_id(id)
        if not instance:
            return None
        for key, value in data.model_dump().items():
            setattr(instance, key, value)
        await self.session.commit()
        await self.session.refresh(instance)
        return instance

    async def delete_by_id(self, id: int) -> bool:
        instance = await self.get_by_id(id)
        if not instance:
            return False
        await self.session.delete(instance)
        await self.session.commit()
        return True
