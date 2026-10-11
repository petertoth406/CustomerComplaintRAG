"""Request and response contracts for embedding and semantic search."""

from pydantic import BaseModel, Field

from app.schemas.preprocessing import PageSelection


class EmbeddingRequest(PageSelection):
    pass


class EmbeddingResult(BaseModel):
    page_id: int | None
    page: str
    embedded_count: int
    skipped_count: int


class EmbeddingResponse(BaseModel):
    results: list[EmbeddingResult]
    embedded_count: int
    skipped_count: int


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)


class SearchHit(BaseModel):
    rank: int
    page_id: int | None
    page: str
    block_id: int
    full_text: str
    source_url: str
    distance: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchHit]
