import os
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

_DATABASE_URL: str | None = os.getenv("DATABASE_URL")
if _DATABASE_URL is None:
    raise RuntimeError("Environment variable DATABASE_URL is not set")

engine = create_async_engine(_DATABASE_URL)

_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, expire_on_commit=False
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with _session_factory() as session:
        yield session


SessionDependency = Annotated[AsyncSession, Depends(get_session)]


class Base(DeclarativeBase):
    pass


async def create_database_if_not_exists() -> None:
    if _DATABASE_URL is None:
        raise RuntimeError(
            "Environment variable DATABASE_URL is not set"
        )
    url = make_url(_DATABASE_URL)
    database_name = url.database

    if not database_name:
        raise RuntimeError("Database name is missing in DATABASE_URL")

    default_db_url = url.set(database="postgres")
    temp_engine = create_async_engine(default_db_url)

    async with temp_engine.connect() as conn:
        conn = await conn.execution_options(
            isolation_level="AUTOCOMMIT"
        )
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
            {"dbname": database_name},
        )
        if not exists:
            await conn.execute(
                text(f'CREATE DATABASE "{database_name}"')
            )

    await temp_engine.dispose()


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_database() -> None:
    if _DATABASE_URL is None:
        raise RuntimeError(
            "Environment variable DATABASE_URL is not set"
        )
    url = make_url(_DATABASE_URL)
    database_name = url.database

    if not database_name:
        raise RuntimeError("Database name is missing in DATABASE_URL")

    await engine.dispose()

    default_db_url = url.set(database="postgres")
    temp_engine = create_async_engine(default_db_url)

    async with temp_engine.connect() as conn:
        conn = await conn.execution_options(
            isolation_level="AUTOCOMMIT"
        )
        await conn.execute(
            text(f'DROP DATABASE IF EXISTS "{database_name}"')
        )

    await temp_engine.dispose()
