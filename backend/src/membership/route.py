from fastapi import APIRouter, status

from src.auth.dependency import CurrentUserDependency
from src.bonfire.schema import BonfireDetail
from src.common.config import IdPath
from src.membership.dependency import MembershipServiceDependency
from src.membership.schema import InvitationRead, InviteRequest

membership_router = APIRouter(prefix="/bonfires", tags=["Membership"])
my_invitations_router = APIRouter(prefix="/me", tags=["Membership"])


@membership_router.post(
    "/{bonfire_id}/members", status_code=status.HTTP_201_CREATED
)
async def join_bonfire(
    bonfire_id: IdPath,
    user: CurrentUserDependency,
    service: MembershipServiceDependency,
) -> BonfireDetail:
    return await service.join(user, bonfire_id)


@membership_router.delete(
    "/{bonfire_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    bonfire_id: IdPath,
    user_id: IdPath,
    user: CurrentUserDependency,
    service: MembershipServiceDependency,
) -> None:
    await service.remove_member(user, bonfire_id, user_id)


@membership_router.post(
    "/{bonfire_id}/invitations", status_code=status.HTTP_204_NO_CONTENT
)
async def invite(
    bonfire_id: IdPath,
    data: InviteRequest,
    user: CurrentUserDependency,
    service: MembershipServiceDependency,
) -> None:
    await service.invite(user, bonfire_id, data)


@membership_router.delete(
    "/{bonfire_id}/invitations/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def cancel_invitation(
    bonfire_id: IdPath,
    user_id: IdPath,
    user: CurrentUserDependency,
    service: MembershipServiceDependency,
) -> None:
    await service.cancel_invitation(user, bonfire_id, user_id)


@my_invitations_router.get("/invitations")
async def list_invitations(
    user: CurrentUserDependency, service: MembershipServiceDependency
) -> list[InvitationRead]:
    return await service.list_invitations(user)


@my_invitations_router.delete(
    "/invitations/{bonfire_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def decline_invitation(
    bonfire_id: IdPath,
    user: CurrentUserDependency,
    service: MembershipServiceDependency,
) -> None:
    await service.decline_invitation(user, bonfire_id)
