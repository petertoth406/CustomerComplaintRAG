"""Canonical document structures independent of chunking."""

from dataclasses import dataclass
from typing import Literal

from app.core.config import CanonicalDocumentSchemaVersion


MessageType = Literal["complaint", "answer", "answer_reference"]
AnswerSource = Literal["inline", "linked"]
AnswerStatus = Literal["answered", "unanswered", "unresolved_reference"]
ReferenceStatus = Literal["resolved", "unresolved"]


@dataclass(frozen=True)
class Message:
    type: MessageType
    text: str
    url: str | None = None
    answer_source: AnswerSource | None = None
    resolution_status: ReferenceStatus | None = None
    resolution_error: str | None = None


def join_message_text(messages: list[Message]) -> str:
    return "\n\n".join(message.text for message in messages if message.type != "answer_reference")


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
