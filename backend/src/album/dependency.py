from typing import Annotated

from fastapi import Depends

from src.album.resolver import AlbumResolver

AlbumResolverDependency = Annotated[AlbumResolver, Depends()]
