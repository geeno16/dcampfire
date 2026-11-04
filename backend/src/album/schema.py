import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, StringConstraints

from src.common.config import ALBUM_URL_MAX_LENGTH

ALBUM_URL_PATTERN = re.compile(
    r"^https?://music\.yandex\.(?:ru|com|by|kz|uz)"
    r"/album/(?P<id>\d{1,18})(?:/track/\d+)?/?(?:[?#].*)?$"
)


def _check_album_url(url: str) -> str:
    if not ALBUM_URL_PATTERN.match(url):
        raise ValueError("Expected a Yandex Music album link")
    return url


AlbumUrl = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, max_length=ALBUM_URL_MAX_LENGTH
    ),
    AfterValidator(_check_album_url),
]


class AlbumLookupResponse(BaseModel):
    title: str
