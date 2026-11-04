from typing import Annotated

from fastapi import APIRouter, Query, status

from src.auth.dependency import CurrentUserDependency
from src.bonfire.dependency import BonfireServiceDependency
from src.bonfire.schema import (
    BonfireCard,
    BonfireCreateRequest,
    BonfireDetail,
    BonfireUpdateRequest,
)
from src.common.config import IdPath

bonfire_router = APIRouter(prefix="/bonfires", tags=["Bonfire"])
my_bonfires_router = APIRouter(prefix="/me", tags=["Bonfire"])


@my_bonfires_router.get("/bonfires")
async def list_my_bonfires(
    user: CurrentUserDependency, service: BonfireServiceDependency
) -> list[BonfireCard]:
    return await service.list_mine(user)


@bonfire_router.get("/recommended")
async def list_recommended(
    user: CurrentUserDependency,
    service: BonfireServiceDependency,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[BonfireCard]:
    return await service.recommended(user, limit, offset)


@bonfire_router.post("", status_code=status.HTTP_201_CREATED)
async def create_bonfire(
    data: BonfireCreateRequest,
    user: CurrentUserDependency,
    service: BonfireServiceDependency,
) -> BonfireDetail:
    return await service.create(user, data)


@bonfire_router.get("/{bonfire_id}")
async def get_bonfire(
    bonfire_id: IdPath,
    user: CurrentUserDependency,
    service: BonfireServiceDependency,
) -> BonfireDetail:
    return await service.get(user, bonfire_id)


@bonfire_router.patch("/{bonfire_id}")
async def update_bonfire(
    bonfire_id: IdPath,
    data: BonfireUpdateRequest,
    user: CurrentUserDependency,
    service: BonfireServiceDependency,
) -> BonfireDetail:
    return await service.update(user, bonfire_id, data)


@bonfire_router.delete(
    "/{bonfire_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_bonfire(
    bonfire_id: IdPath,
    user: CurrentUserDependency,
    service: BonfireServiceDependency,
) -> None:
    await service.delete(user, bonfire_id)
