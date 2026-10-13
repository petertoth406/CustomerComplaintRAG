"""Canonical document structures independent of chunking."""

from dataclasses import dataclass
from typing import Literal

from app.core.config import CanonicalDocumentSchemaVersion


MessageType = Literal["complaint", "answer", "answer_reference"]


@dataclass(frozen=True)
class Message:
    type: MessageType
    text: str
    url: str | None = None


@dataclass(frozen=True)
class CanonicalDocument:
    schema_version: CanonicalDocumentSchemaVersion
    document_id: str
    source_page: str
    source_page_id: int | None
    document_index: int
    source_url: str
    messages: list[Message]
    text: str
