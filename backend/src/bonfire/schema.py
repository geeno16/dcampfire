from datetime import datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    StringConstraints,
    field_validator,
)

from src.album.schema import AlbumUrl
from src.common.config import (
    BONFIRE_COLORS,
    BONFIRE_NAME_MAX_LENGTH,
    BONFIRE_NAME_MIN_LENGTH,
    BONFIRE_TOPICS_MAX,
)
from src.reference.schema import TopicId, TopicRead, unique_topic_ids
from src.user.schema import UserBrief


def _check_color(color: str) -> str:
    if color not in BONFIRE_COLORS:
        raise ValueError(
            f"Unknown color, expected one of: {', '.join(BONFIRE_COLORS)}"
        )
    return color


BonfireName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=BONFIRE_NAME_MIN_LENGTH,
        max_length=BONFIRE_NAME_MAX_LENGTH,
    ),
]
Color = Annotated[str, AfterValidator(_check_color)]
BonfireTopicIds = Annotated[
    list[TopicId],
    Field(max_length=BONFIRE_TOPICS_MAX),
    AfterValidator(unique_topic_ids),
]


class BonfireCreateRequest(BaseModel):
    name: BonfireName
    color: Color
    topic_ids: BonfireTopicIds = []
    album_url: AlbumUrl | None = None
    is_open: bool = True


class BonfireUpdateRequest(BaseModel):
    name: BonfireName | None = None
    color: Color | None = None
    topic_ids: BonfireTopicIds | None = None
    album_url: AlbumUrl | None = None
    is_open: bool | None = None

    @field_validator(
        "name", "color", "topic_ids", "is_open", mode="before"
    )
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("Field cannot be null")
        return value


class AlbumRead(BaseModel):
    url: str
    title: str | None


class MemberRead(UserBrief):
    joined_at: datetime


class BonfireCard(BaseModel):
    id: int
    name: str
    color: str
    is_open: bool
    owner_id: int
    members_count: int
    topics: list[TopicRead]


class SentInvitationRead(BaseModel):
    user: UserBrief
    created_at: datetime


class BonfireDetail(BonfireCard):
    album: AlbumRead | None
    members: list[MemberRead]
    invitations: list[SentInvitationRead] | None
    next_message_at: datetime | None
