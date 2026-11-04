from src.common import config
from src.common.database import SessionDependency
from src.reference.repository import TopicRepository
from src.reference.schema import (
    ColorRead,
    ConfigResponse,
    LimitsRead,
    TopicRead,
)


class ReferenceService:
    def __init__(self, session: SessionDependency) -> None:
        self.topics = TopicRepository(session)

    async def list_topics(self) -> list[TopicRead]:
        topics = sorted(await self.topics.read(), key=lambda t: t.id)
        return [TopicRead.model_validate(topic) for topic in topics]

    def get_config(self) -> ConfigResponse:
        return ConfigResponse(
            limits=LimitsRead(
                nickname_min_length=config.NICKNAME_MIN_LENGTH,
                nickname_max_length=config.NICKNAME_MAX_LENGTH,
                password_min_length=config.PASSWORD_MIN_LENGTH,
                user_topics_max=config.USER_TOPICS_MAX,
                bonfire_topics_max=config.BONFIRE_TOPICS_MAX,
                bonfire_capacity=config.BONFIRE_CAPACITY,
                user_bonfires_max=config.USER_BONFIRES_MAX,
                bonfire_name_min_length=config.BONFIRE_NAME_MIN_LENGTH,
                bonfire_name_max_length=config.BONFIRE_NAME_MAX_LENGTH,
                message_max_length=config.MESSAGE_MAX_LENGTH,
                message_pause_seconds=int(
                    config.MESSAGE_PAUSE.total_seconds()
                ),
                email_code_ttl_seconds=int(
                    config.EMAIL_CODE_TTL.total_seconds()
                ),
                email_code_max_attempts=config.EMAIL_CODE_MAX_ATTEMPTS,
                email_code_resend_cooldown_seconds=int(
                    config.EMAIL_CODE_RESEND_COOLDOWN.total_seconds()
                ),
                avatar_max_bytes=config.AVATAR_MAX_BYTES,
            ),
            colors=[
                ColorRead(key=key, hex=hex)
                for key, hex in config.BONFIRE_COLORS.items()
            ],
        )
