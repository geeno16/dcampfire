from typing import Annotated

from fastapi import Depends

from src.membership.service import MembershipService

MembershipServiceDependency = Annotated[MembershipService, Depends()]
