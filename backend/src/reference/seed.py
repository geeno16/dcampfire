from sqlalchemy.ext.asyncio import AsyncSession

from src.reference.repository import TopicRepository

TOPICS = (
    "Истории",
    "Страхи",
    "Дорога",
    "Музыка",
    "Сны",
    "Детство",
    "Город",
    "Природа",
    "Книги",
    "Кино",
    "Еда",
    "Работа",
    "Учёба",
    "Спорт",
)


async def seed_topics(session: AsyncSession) -> None:
    repository = TopicRepository(session)
    existing = {topic.name for topic in await repository.read()}
    for name in TOPICS:
        if name not in existing:
            await repository.create(name=name)
