from typing import Any, ClassVar

import httpx

from src.album.schema import ALBUM_URL_PATTERN
from src.common.config import (
    ALBUM_TITLE_MAX_LENGTH,
    YANDEX_MUSIC_API_URL,
    YANDEX_MUSIC_TIMEOUT_SECONDS,
    YANDEX_MUSIC_TOKEN,
)
from src.common.exception import NotFoundError, ServiceUnavailableError


def _lookup_failed() -> ServiceUnavailableError:
    return ServiceUnavailableError("ALBUM_LOOKUP_FAILED")


def _format_title(album: dict[str, Any]) -> str:
    title = album.get("title")
    if not isinstance(title, str) or not title.strip():
        raise _lookup_failed()

    version = album.get("version")
    if isinstance(version, str) and version.strip():
        title = f"{title} ({version.strip()})"

    artists = [
        artist["name"]
        for artist in album.get("artists") or []
        if isinstance(artist, dict)
        and isinstance(artist.get("name"), str)
    ]
    if artists:
        title = f"{title} — {', '.join(artists)}"
    return title[:ALBUM_TITLE_MAX_LENGTH]


class AlbumResolver:
    transport: ClassVar[httpx.AsyncBaseTransport | None] = None

    async def resolve(self, url: str) -> str:
        match = ALBUM_URL_PATTERN.match(url)
        if match is None:
            raise NotFoundError("ALBUM_NOT_FOUND")

        headers = (
            {"Authorization": f"OAuth {YANDEX_MUSIC_TOKEN}"}
            if YANDEX_MUSIC_TOKEN
            else {}
        )
        try:
            async with httpx.AsyncClient(
                base_url=YANDEX_MUSIC_API_URL,
                timeout=YANDEX_MUSIC_TIMEOUT_SECONDS,
                headers=headers,
                transport=self.transport,
            ) as client:
                response = await client.get(f"/albums/{match['id']}")
        except httpx.HTTPError as exc:
            raise _lookup_failed() from exc

        if response.status_code in (400, 404):
            raise NotFoundError("ALBUM_NOT_FOUND")
        if response.status_code != 200:
            raise _lookup_failed()

        try:
            album = response.json()["result"]
        except (ValueError, KeyError, TypeError) as exc:
            raise _lookup_failed() from exc
        if not isinstance(album, dict):
            raise _lookup_failed()
        if "error" in album:
            raise NotFoundError("ALBUM_NOT_FOUND")
        return _format_title(album)
