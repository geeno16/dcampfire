from typing import Annotated

from fastapi import Depends

from src.bonfire.service import BonfireService

BonfireServiceDependency = Annotated[BonfireService, Depends()]
