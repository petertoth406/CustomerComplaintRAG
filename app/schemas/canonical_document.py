"""Validation contract for canonical document JSONL records."""

from pydantic import BaseModel, Field, computed_field

from app.core.config import CanonicalDocumentSchemaVersion
from app.models.document import AnswerSource, AnswerStatus, MessageType, ReferenceStatus


class CanonicalMessageRecord(BaseModel):
    type: MessageType
    text: str = Field(min_length=1)
    url: str | None = None
    answer_source: AnswerSource | None = None
    resolution_status: ReferenceStatus | None = None
    resolution_error: str | None = None


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

    @computed_field
    @property
    def answer_status(self) -> AnswerStatus | None:
        if not any(message.type == "complaint" and message.text.strip() for message in self.messages):
            return None
        if any(message.type == "answer" and message.text.strip() for message in self.messages):
            return "answered"
        if any(message.type == "answer_reference" for message in self.messages):
            return "unresolved_reference"
        return "unanswered"
