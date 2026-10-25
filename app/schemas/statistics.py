"""API contracts for statistics derived from generated datasets."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


StatisticsSchemaVersion = Literal["1.0"]
STATISTICS_SCHEMA_VERSION: StatisticsSchemaVersion = "1.0"


class DiscoveredPage(BaseModel):
    page: str = Field(pattern=r"^levelek(?:[1-9]\d*)?$")
    page_id: int | None = Field(default=None, ge=1)


class DatasetDescriptor(BaseModel):
    dataset_id: str = Field(min_length=1)
    output_directory: str = Field(min_length=1)
    exists: bool
    discovered_page_count: int = Field(ge=0)
    discovered_pages: list[DiscoveredPage]
    first_page_id: int | None = Field(default=None, ge=1)
    last_page_id: int | None = Field(default=None, ge=1)
    missing_page_ids_inside_range: list[int]


class ContentCounts(BaseModel):
    document_count: int | None = Field(default=None, ge=0)
    complaint_document_count: int | None = Field(default=None, ge=0)
    complaint_message_count: int | None = Field(default=None, ge=0)
    inline_answer_count: int | None = Field(default=None, ge=0)
    external_answer_reference_count: int | None = Field(default=None, ge=0)
    detected_answer_count: int | None = Field(default=None, ge=0)
    answered_document_count: int | None = Field(default=None, ge=0)


class PageStatistics(BaseModel):
    page: str = Field(pattern=r"^levelek(?:[1-9]\d*)?$")
    page_id: int | None = Field(default=None, ge=1)
    source_url: str | None = None
    downloaded_at: datetime | None = None
    download_status: Literal["available", "missing", "invalid"]
    processing_status: Literal[
        "processed",
        "processed_empty",
        "not_processed",
        "invalid",
    ]
    content: ContentCounts


class DatasetSummary(BaseModel):
    page_directory_count: int = Field(ge=0)
    downloaded_page_count: int = Field(ge=0)
    missing_source_metadata_count: int = Field(ge=0)
    invalid_source_metadata_count: int = Field(ge=0)
    processed_page_count: int = Field(ge=0)
    empty_processed_page_count: int = Field(ge=0)
    not_processed_page_count: int = Field(ge=0)
    invalid_documents_file_count: int = Field(ge=0)
    content: ContentCounts


class StatisticsResponse(BaseModel):
    generated_at: datetime
    statistics_schema_version: StatisticsSchemaVersion
    dataset: DatasetDescriptor
    summary: DatasetSummary
    pages: list[PageStatistics]
