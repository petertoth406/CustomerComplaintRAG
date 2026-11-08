"""Controller for statistics derived from generated datasets."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.schemas.statistics import StatisticsResponse
from app.services.semantic_backend import SemanticBackendError
from app.services.statistics_service import StatisticsService


router = APIRouter(prefix="/statistics", tags=["statistics"])


def get_service() -> StatisticsService:
    return StatisticsService()


Service = Annotated[StatisticsService, Depends(get_service)]


@router.get("", response_model=StatisticsResponse)
def get_statistics(
    service: Service,
    include_tokens: Annotated[
        bool,
        Query(description="Tokenhossz-statisztikák számítása a konfigurált tokenizerrel."),
    ] = False,
) -> StatisticsResponse:
    try:
        return service.get_statistics(include_tokens=include_tokens)
    except SemanticBackendError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error
