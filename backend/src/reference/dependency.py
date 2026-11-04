from typing import Annotated

from fastapi import Depends

from src.reference.service import ReferenceService

ReferenceServiceDependency = Annotated[ReferenceService, Depends()]
