"""Controller for statistics derived from generated datasets."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.schemas.statistics import StatisticsDiscoveryResponse
from app.services.statistics_service import StatisticsService


router = APIRouter(prefix="/statistics", tags=["statistics"])


def get_service() -> StatisticsService:
    return StatisticsService()


Service = Annotated[StatisticsService, Depends(get_service)]


@router.get("", response_model=StatisticsDiscoveryResponse)
def get_statistics(service: Service) -> StatisticsDiscoveryResponse:
    return service.discover_dataset()
