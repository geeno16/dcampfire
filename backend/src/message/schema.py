from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from src.common.config import MESSAGE_MAX_LENGTH
from src.user.schema import UserBrief


class SendMessageRequest(BaseModel):
    body: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=MESSAGE_MAX_LENGTH,
        ),
    ]


class MessageRead(BaseModel):
    id: int
    bonfire_id: int
    author: UserBrief | None
    body: str
    created_at: datetime


class SendMessageResponse(BaseModel):
    message: MessageRead
    next_message_at: datetime
