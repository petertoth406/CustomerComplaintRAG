"""A shared document data structure independent of chunking"""

from dataclasses import dataclass

from app.models.complaint import Block, Message
from app.models.source_page import SourcePage


CANONICAL_DOCUMENT_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class CanonicalDocument:
    schema_version: str
    document_id: str
    source_page: str
    source_page_id: int | None
    source_block_id: int
    source_url: str
    messages: list[Message]
    text: str


def build_canonical_documents(
    page: SourcePage,
    blocks: list[Block],
) -> list[CanonicalDocument]:
    return [
        CanonicalDocument(
            schema_version=CANONICAL_DOCUMENT_SCHEMA_VERSION,
            document_id=f"complaint:{page.name}:{block.block_id:04d}",
            source_page=page.name,
            source_page_id=page.page_id,
            source_block_id=block.block_id,
            source_url=block.source_url,
            messages=block.messages,
            text=block.full_text,
        )
        for block in blocks
        if block.full_text.strip()
    ]
