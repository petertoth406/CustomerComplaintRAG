"""Request and response contracts for embedding and semantic search."""

from pydantic import BaseModel, Field

from app.core.config import DEFAULT_CHUNK_CONFIG_ID
from app.schemas.preprocessing import PageSelection


class EmbeddingRequest(PageSelection):
    chunk_config_ids: list[str] = Field(
        default_factory=lambda: [DEFAULT_CHUNK_CONFIG_ID],
        min_length=1,
    )


class EmbeddingResult(BaseModel):
    page_id: int | None
    page: str
    chunk_config_id: str
    collection_name: str
    chunks_jsonl: str
    embedded_count: int
    skipped_count: int


class EmbeddingResponse(BaseModel):
    results: list[EmbeddingResult]
    embedded_count: int
    skipped_count: int


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    chunk_config_id: str = DEFAULT_CHUNK_CONFIG_ID


class SearchHit(BaseModel):
    rank: int
    page_id: int | None
    page: str
    document_id: str
    document_index: int
    chunk_id: str
    chunk_config_id: str
    chunk_index: int
    token_count: int
    text: str
    source_url: str
    distance: float


class SearchResponse(BaseModel):
    query: str
    chunk_config_id: str
    results: list[SearchHit]
