"""API contracts for statistics derived from generated datasets."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


StatisticsSchemaVersion = Literal["1.1"]
STATISTICS_SCHEMA_VERSION: StatisticsSchemaVersion = "1.1"


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


class LengthDistribution(BaseModel):
    count: int = Field(ge=0)
    total: int = Field(ge=0)
    minimum: int | None = Field(default=None, ge=0)
    maximum: int | None = Field(default=None, ge=0)
    average: float | None = Field(default=None, ge=0)
    median: float | None = Field(default=None, ge=0)
    percentile_90: int | None = Field(default=None, ge=0)
    percentile_95: int | None = Field(default=None, ge=0)


class TextLengthStatistics(BaseModel):
    characters: LengthDistribution
    words: LengthDistribution
    tokens: LengthDistribution | None = None


class ContentLengthStatistics(BaseModel):
    documents: TextLengthStatistics
    complaints: TextLengthStatistics
    inline_answers: TextLengthStatistics


class ChunkConfigurationDescriptor(BaseModel):
    chunk_config_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    version: int | None = Field(default=None, ge=1)
    strategy: Literal["structural", "fixed_token"]
    collection_name: str = Field(min_length=1)
    tokenizer_model: str = Field(min_length=1)
    tokenizer_revision: str = Field(min_length=1)
    max_tokens: int | None = Field(default=None, ge=1)
    overlap_tokens: int = Field(ge=0)


class PageChunkStatistics(BaseModel):
    chunk_config_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    status: Literal[
        "complete",
        "partial",
        "missing",
        "invalid",
        "unverifiable",
    ]
    document_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)
    missing_document_count: int | None = Field(default=None, ge=0)
    token_lengths: LengthDistribution


class DatasetChunkStatistics(BaseModel):
    chunk_config_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    status: Literal["complete", "partial", "missing", "invalid"]
    page_count: int = Field(ge=0)
    complete_page_count: int = Field(ge=0)
    partial_page_count: int = Field(ge=0)
    missing_page_count: int = Field(ge=0)
    invalid_page_count: int = Field(ge=0)
    unverifiable_page_count: int = Field(ge=0)
    document_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)
    missing_document_count: int = Field(ge=0)
    token_lengths: LengthDistribution


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
    lengths: ContentLengthStatistics | None = None
    chunk_statistics: list[PageChunkStatistics]


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
    lengths: ContentLengthStatistics
    chunk_statistics: list[DatasetChunkStatistics]


class TokenizerDescriptor(BaseModel):
    model: str = Field(min_length=1)
    revision: str = Field(min_length=1)


class StatisticsResponse(BaseModel):
    generated_at: datetime
    statistics_schema_version: StatisticsSchemaVersion
    tokens_included: bool
    tokenizer: TokenizerDescriptor | None = None
    chunk_configurations: list[ChunkConfigurationDescriptor]
    dataset: DatasetDescriptor
    summary: DatasetSummary
    pages: list[PageStatistics]
