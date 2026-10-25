"""Semantic search API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_semantic_service
from app.schemas.semantic_search import SearchHit, SearchRequest, SearchResponse
from app.services.semantic_backend import SemanticBackendError
from app.services.semantic_search_service import SemanticSearchService


router = APIRouter(prefix="/search", tags=["search"])
Service = Annotated[SemanticSearchService, Depends(get_semantic_service)]


@router.post("", response_model=SearchResponse)
def search(request: SearchRequest, service: Service) -> SearchResponse:
    try:
        hits = service.search(request.query, request.chunk_config_id)
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
        chunk_config_id=request.chunk_config_id,
        results=[SearchHit(**hit) for hit in hits],
    )
