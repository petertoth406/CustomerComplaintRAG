"""Semantic search API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_semantic_service
from app.schemas.semantic_search import SearchHit, SearchRequest, SearchResponse
from app.services.semantic_search_service import (
    SemanticBackendError,
    SemanticSearchService,
)


router = APIRouter(prefix="/search", tags=["search"])
Service = Annotated[SemanticSearchService, Depends(get_semantic_service)]


@router.post("", response_model=SearchResponse)
def search(request: SearchRequest, service: Service) -> SearchResponse:
    try:
        hits = service.search(request.query)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except SemanticBackendError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error
    return SearchResponse(
        query=request.query,
        results=[SearchHit(**hit) for hit in hits],
    )
