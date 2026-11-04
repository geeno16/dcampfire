from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.album.route import album_router
from src.auth import auth_router
from src.bonfire.route import bonfire_router, my_bonfires_router
from src.common import (
    create_database_if_not_exists,
    create_tables,
    register_exception_handlers,
    session_factory,
)
from src.membership.route import (
    membership_router,
    my_invitations_router,
)
from src.message.route import message_router
from src.realtime.route import realtime_router
from src.reference.route import reference_router
from src.reference.seed import seed_topics
from src.user.route import media_router, profile_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await create_database_if_not_exists()
    await create_tables()
    async with session_factory() as session, session.begin():
        await seed_topics(session)
    yield


app = FastAPI(title="Dcampfire API", lifespan=lifespan)
register_exception_handlers(app)

for router in (
    auth_router,
    reference_router,
    profile_router,
    media_router,
    my_bonfires_router,
    bonfire_router,
    album_router,
    membership_router,
    my_invitations_router,
    message_router,
    realtime_router,
):
    app.include_router(router, prefix="/api/v1")
