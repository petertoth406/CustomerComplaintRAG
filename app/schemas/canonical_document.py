"""Validation contract for canonical document JSONL records."""

from pydantic import BaseModel, Field

from app.core.config import CanonicalDocumentSchemaVersion
from app.models.document import MessageType


class CanonicalMessageRecord(BaseModel):
    type: MessageType
    text: str = Field(min_length=1)
    url: str | None = None


class CanonicalDocumentRecord(BaseModel):
    schema_version: CanonicalDocumentSchemaVersion
    document_id: str = Field(
        pattern=r"^complaint:levelek(?:\d+)?:\d{4,}$",
    )
    source_page: str = Field(pattern=r"^levelek(?:\d+)?$")
    source_page_id: int | None = Field(default=None, ge=1)
    document_index: int = Field(ge=1)
    source_url: str = Field(min_length=1)
    messages: list[CanonicalMessageRecord]
    text: str = Field(min_length=1)
