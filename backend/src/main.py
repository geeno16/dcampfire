from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.album.route import album_router
from src.auth import auth_router
from src.bonfire.route import bonfire_router, my_bonfires_router
from src.common import (
    create_tables,
    engine,
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
    # PostgreSQL/Compose creates the database before this process starts.
    await create_tables()
    async with session_factory() as session, session.begin():
        await seed_topics(session)
    yield
    await engine.dispose()


app = FastAPI(
    title="Dcampfire API",
    lifespan=lifespan,
    generate_unique_id_function=lambda route: route.name,
)
register_exception_handlers(app)


@app.get("/health", include_in_schema=False)
async def health():
    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        return JSONResponse(
            status_code=503, content={"status": "unavailable"}
        )


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
