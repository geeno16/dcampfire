import httpx
import pytest
from httpx import AsyncClient

from src.album.resolver import AlbumResolver
from src.album.schema import ALBUM_URL_PATTERN
from src.common.exception import NotFoundError, ServiceUnavailableError

URL = "https://music.yandex.ru/album/3389005"


def mock_api(
    monkeypatch: pytest.MonkeyPatch, handler
) -> list[httpx.Request]:
    requests: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    monkeypatch.setattr(
        AlbumResolver, "transport", httpx.MockTransport(record)
    )
    return requests


def album_response(**album) -> httpx.Response:
    return httpx.Response(200, json={"result": album})


@pytest.mark.parametrize(
    "url",
    [
        "https://music.yandex.ru/album/3389005",
        "https://music.yandex.com/album/3389005/",
        "https://music.yandex.by/album/3389005/track/12345",
        "https://music.yandex.kz/album/3389005?utm_source=share",
        "http://music.yandex.ru/album/3389005#top",
    ],
)
def test_album_url_accepted(url: str):
    match = ALBUM_URL_PATTERN.match(url)
    assert match is not None
    assert match["id"] == "3389005"


@pytest.mark.parametrize(
    "url",
    [
        "https://music.yandex.ru/playlists/123",
        "https://music.yandex.ru/artist/13002",
        "https://evil.com/music.yandex.ru/album/3389005",
        "https://music.yandex.ru.evil.com/album/3389005",
        "music.yandex.ru/album/3389005",
        "https://music.yandex.ru/album/abc",
    ],
)
def test_album_url_rejected(url: str):
    assert ALBUM_URL_PATTERN.match(url) is None


@pytest.mark.asyncio
async def test_resolve_formats_title(monkeypatch: pytest.MonkeyPatch):
    requests = mock_api(
        monkeypatch,
        lambda _: album_response(
            id=3389005,
            title="Pablo Honey",
            artists=[{"name": "Radiohead"}],
        ),
    )

    assert (
        await AlbumResolver().resolve(URL) == "Pablo Honey — Radiohead"
    )
    assert requests[0].url.path == "/albums/3389005"


@pytest.mark.asyncio
async def test_resolve_with_version_and_artists(
    monkeypatch: pytest.MonkeyPatch,
):
    mock_api(
        monkeypatch,
        lambda _: album_response(
            title="Тише",
            version="Remastered",
            artists=[{"name": "A"}, {"name": "B"}],
        ),
    )

    assert (
        await AlbumResolver().resolve(URL) == "Тише (Remastered) — A, B"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"result": {"error": "not-found"}}),
        httpx.Response(400, json={}),
        httpx.Response(404, json={}),
    ],
)
async def test_resolve_not_found(
    monkeypatch: pytest.MonkeyPatch, response: httpx.Response
):
    mock_api(monkeypatch, lambda _: response)

    with pytest.raises(NotFoundError) as exc_info:
        await AlbumResolver().resolve(URL)
    assert exc_info.value.code == "ALBUM_NOT_FOUND"


def raise_timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("timeout", request=request)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "handler",
    [
        raise_timeout,
        lambda _: httpx.Response(503, text="down"),
        lambda _: httpx.Response(200, text="<html>captcha</html>"),
        lambda _: httpx.Response(200, json={"result": {"id": 1}}),
    ],
)
async def test_resolve_lookup_failed(
    monkeypatch: pytest.MonkeyPatch, handler
):
    mock_api(monkeypatch, handler)

    with pytest.raises(ServiceUnavailableError) as exc_info:
        await AlbumResolver().resolve(URL)
    assert exc_info.value.code == "ALBUM_LOOKUP_FAILED"


@pytest.mark.asyncio
async def test_lookup_endpoint(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
):
    mock_api(
        monkeypatch,
        lambda _: album_response(
            title="Pablo Honey", artists=[{"name": "Radiohead"}]
        ),
    )

    response = await async_client.get(
        "/api/v1/albums/lookup",
        params={"url": URL},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json() == {"title": "Pablo Honey — Radiohead"}

    response = await async_client.get(
        "/api/v1/albums/lookup",
        params={"url": "https://example.com"},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_FAILED"

    response = await async_client.get(
        "/api/v1/albums/lookup", params={"url": URL}
    )
    assert response.status_code == 401
