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


class StatisticsDiscoveryResponse(BaseModel):
    generated_at: datetime
    statistics_schema_version: StatisticsSchemaVersion
    dataset: DatasetDescriptor
