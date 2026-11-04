from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    StringConstraints,
)

from src.common.config import (
    NICKNAME_MAX_LENGTH,
    NICKNAME_MIN_LENGTH,
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    USER_TOPICS_MAX,
)
from src.reference.schema import TopicId, TopicRead, unique_topic_ids

Nickname = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=NICKNAME_MIN_LENGTH,
        max_length=NICKNAME_MAX_LENGTH,
    ),
]
NewPassword = Annotated[
    str,
    Field(
        min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH
    ),
]
Password = Annotated[str, Field(max_length=PASSWORD_MAX_LENGTH)]


class UserBrief(BaseModel):
    id: int
    nickname: str
    avatar_url: str | None


class ProfileRead(BaseModel):
    id: int
    nickname: str
    email: str
    avatar_url: str | None
    topics: list[TopicRead]


class UpdateProfileRequest(BaseModel):
    nickname: Nickname


class ChangePasswordRequest(BaseModel):
    current_password: Password
    new_password: NewPassword


class SetTopicsRequest(BaseModel):
    topic_ids: Annotated[
        list[TopicId],
        Field(max_length=USER_TOPICS_MAX),
        AfterValidator(unique_topic_ids),
    ]


class DeleteAccountRequest(BaseModel):
    password: Password
