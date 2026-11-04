from typing import Annotated

from fastapi import Depends

from src.message.service import MessageService

MessageServiceDependency = Annotated[MessageService, Depends()]
