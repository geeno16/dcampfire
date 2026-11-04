from fastapi import APIRouter

from src.auth.dependency import CurrentUserDependency
from src.reference.dependency import ReferenceServiceDependency
from src.reference.schema import ConfigResponse, TopicRead

reference_router = APIRouter(tags=["Reference"])


@reference_router.get("/config")
async def get_config(
    service: ReferenceServiceDependency,
) -> ConfigResponse:
    return service.get_config()


@reference_router.get("/topics")
async def list_topics(
    service: ReferenceServiceDependency, _: CurrentUserDependency
) -> list[TopicRead]:
    return await service.list_topics()
