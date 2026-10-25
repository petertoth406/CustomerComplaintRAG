"""Chunk structures produced from canonical complaint documents."""

from dataclasses import dataclass
from typing import Literal


ChunkStrategy = Literal["structural", "fixed_token"]


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    chunk_config_id: str
    strategy: ChunkStrategy
    chunk_index: int
    token_start: int
    token_end: int
    token_count: int
    source_page: str
    source_page_id: int | None
    document_index: int
    source_url: str
    text: str
