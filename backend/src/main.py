from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.common import create_database_if_not_exists, create_tables


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await create_database_if_not_exists()
    await create_tables()
    yield


app = FastAPI(title="Dcampfire API", lifespan=lifespan)
