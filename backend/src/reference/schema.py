from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

TopicId = Annotated[int, Field(ge=1, le=32767)]


def unique_topic_ids(values: list[int]) -> list[int]:
    if len(values) != len(set(values)):
        raise ValueError("Topic ids must be unique")
    return values


class TopicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class ColorRead(BaseModel):
    key: str
    hex: str


class LimitsRead(BaseModel):
    nickname_min_length: int
    nickname_max_length: int
    password_min_length: int
    user_topics_max: int
    bonfire_topics_max: int
    bonfire_capacity: int
    user_bonfires_max: int
    bonfire_name_min_length: int
    bonfire_name_max_length: int
    message_max_length: int
    message_pause_seconds: int
    email_code_ttl_seconds: int
    email_code_max_attempts: int
    email_code_resend_cooldown_seconds: int
    avatar_max_bytes: int


class ConfigResponse(BaseModel):
    limits: LimitsRead
    colors: list[ColorRead]
