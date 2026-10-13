"""Validation contract for canonical document JSONL records."""

from typing import Literal

from pydantic import BaseModel, Field

from app.models.complaint import MessageType


class CanonicalMessageRecord(BaseModel):
    type: MessageType
    text: str = Field(min_length=1)
    url: str | None = None


class CanonicalDocumentRecord(BaseModel):
    schema_version: Literal["1.0"]
    document_id: str = Field(
        pattern=r"^complaint:levelek(?:\d+)?:\d{4,}$",
    )
    source_page: str = Field(pattern=r"^levelek(?:\d+)?$")
    source_page_id: int | None = Field(default=None, ge=1)
    source_block_id: int = Field(ge=1)
    source_url: str = Field(min_length=1)
    messages: list[CanonicalMessageRecord]
    text: str = Field(min_length=1)
