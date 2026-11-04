from fastapi import APIRouter, UploadFile, status
from fastapi.responses import FileResponse

from src.auth.dependency import CurrentUserDependency
from src.user.dependency import ProfileServiceDependency
from src.user.schema import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    ProfileRead,
    SetTopicsRequest,
    UpdateProfileRequest,
)

profile_router = APIRouter(prefix="/me", tags=["Profile"])
media_router = APIRouter(prefix="/media", tags=["Media"])


@profile_router.get("")
async def get_profile(
    user: CurrentUserDependency, service: ProfileServiceDependency
) -> ProfileRead:
    return await service.build(user)


@profile_router.patch("")
async def update_profile(
    data: UpdateProfileRequest,
    user: CurrentUserDependency,
    service: ProfileServiceDependency,
) -> ProfileRead:
    return await service.update_profile(user, data)


@profile_router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    data: ChangePasswordRequest,
    user: CurrentUserDependency,
    service: ProfileServiceDependency,
) -> None:
    await service.change_password(user, data)


@profile_router.put("/avatar")
async def upload_avatar(
    file: UploadFile,
    user: CurrentUserDependency,
    service: ProfileServiceDependency,
) -> ProfileRead:
    return await service.upload_avatar(user, file)


@profile_router.delete(
    "/avatar", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_avatar(
    user: CurrentUserDependency, service: ProfileServiceDependency
) -> None:
    await service.delete_avatar(user)


@profile_router.put("/topics")
async def set_topics(
    data: SetTopicsRequest,
    user: CurrentUserDependency,
    service: ProfileServiceDependency,
) -> ProfileRead:
    return await service.set_topics(user, data)


@profile_router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    data: DeleteAccountRequest,
    user: CurrentUserDependency,
    service: ProfileServiceDependency,
) -> None:
    await service.delete_account(user, data)


@media_router.get("/avatars/{name}")
async def get_avatar(
    name: str,
    _: CurrentUserDependency,
    service: ProfileServiceDependency,
) -> FileResponse:
    return FileResponse(service.avatar_file(name))
