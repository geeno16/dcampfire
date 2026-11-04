import asyncio
import sys

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.common.database import engine
from src.user.repository import UserRepository


async def _delete(email: str) -> None:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        users = await UserRepository(session).read(email=email.lower())
        if not users:
            print(f"Аккаунт {email} не найден")
        else:
            await UserRepository(session).delete(users[0].id)
            print(
                f"Удалён аккаунт {email} (id={users[0].id}) и его коды"
            )
    await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python -m src.common.delete_user_vstask <email>")
        sys.exit(1)
    asyncio.run(_delete(sys.argv[1]))
