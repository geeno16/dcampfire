import os
from datetime import timedelta
from pathlib import Path
from typing import Annotated

from fastapi import Path as PathParam


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


EMAIL_CODE_TTL = timedelta(seconds=_int("EMAIL_CODE_TTL_SECONDS", 600))
EMAIL_CODE_MAX_ATTEMPTS = _int("EMAIL_CODE_MAX_ATTEMPTS", 5)
EMAIL_CODE_RESEND_COOLDOWN = timedelta(
    seconds=_int("EMAIL_CODE_RESEND_COOLDOWN_SECONDS", 60)
)

PASSWORD_MIN_LENGTH = _int("PASSWORD_MIN_LENGTH", 8)
PASSWORD_MAX_LENGTH = 128
NICKNAME_MIN_LENGTH = _int("NICKNAME_MIN_LENGTH", 3)
NICKNAME_MAX_LENGTH = 20

USER_TOPICS_MAX = _int("USER_TOPICS_MAX", 10)
BONFIRE_TOPICS_MAX = _int("BONFIRE_TOPICS_MAX", 5)
BONFIRE_CAPACITY = _int("BONFIRE_CAPACITY", 5)
USER_BONFIRES_MAX = _int("USER_BONFIRES_MAX", 5)
BONFIRE_NAME_MIN_LENGTH = _int("BONFIRE_NAME_MIN_LENGTH", 3)
BONFIRE_NAME_MAX_LENGTH = 40
MESSAGE_MAX_LENGTH = 1000
MESSAGE_PAUSE = timedelta(seconds=_int("MESSAGE_PAUSE_SECONDS", 10))
MESSAGES_PAGE_DEFAULT = 50
MESSAGES_PAGE_MAX = 100

AVATAR_MAX_BYTES = _int("AVATAR_MAX_BYTES", 5 * 1024 * 1024)
MEDIA_ROOT = Path(
    os.getenv(
        "MEDIA_ROOT", str(Path(__file__).resolve().parents[2] / "media")
    )
)

BONFIRE_COLORS = {
    "orange": "#F2873A",
    "red": "#E5534B",
    "yellow": "#F2C94C",
    "green": "#5CC76A",
    "teal": "#3FCFBE",
    "blue": "#4F9DF0",
    "purple": "#B07CF2",
    "pink": "#F06FB5",
}

YANDEX_MUSIC_API_URL = os.getenv(
    "YANDEX_MUSIC_API_URL", "https://api.music.yandex.net"
)
YANDEX_MUSIC_TOKEN = os.getenv("YANDEX_MUSIC_TOKEN")
YANDEX_MUSIC_TIMEOUT_SECONDS = float(
    os.getenv("YANDEX_MUSIC_TIMEOUT_SECONDS", "5")
)
ALBUM_TITLE_MAX_LENGTH = 512
ALBUM_URL_MAX_LENGTH = 2048

ID_MAX = 2**63 - 1
IdPath = Annotated[int, PathParam(ge=1, le=ID_MAX)]
