from fastapi import APIRouter

from src.album.dependency import AlbumResolverDependency
from src.album.schema import AlbumLookupResponse, AlbumUrl
from src.auth.dependency import CurrentUserDependency

album_router = APIRouter(prefix="/albums", tags=["Album"])


@album_router.get("/lookup")
async def lookup_album(
    url: AlbumUrl,
    resolver: AlbumResolverDependency,
    _: CurrentUserDependency,
) -> AlbumLookupResponse:
    return AlbumLookupResponse(title=await resolver.resolve(url))
