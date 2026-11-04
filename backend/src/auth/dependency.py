from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.auth.service import AuthService
from src.auth.token import decode_access_token
from src.common.database import SessionDependency
from src.common.exception import UnauthorizedError
from src.user.model import User
from src.user.repository import UserRepository

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    session: SessionDependency,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer)
    ],
) -> User:
    if credentials is None:
        raise UnauthorizedError()

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise UnauthorizedError()

    users = await UserRepository(session).read(id=user_id)
    if not users or not users[0].email_verified:
        raise UnauthorizedError()
    return users[0]


AuthServiceDependency = Annotated[AuthService, Depends()]
CurrentUserDependency = Annotated[User, Depends(get_current_user)]
