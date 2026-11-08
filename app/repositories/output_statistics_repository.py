"""Read-only discovery of source-page directories in an output dataset."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app.core.config import OUTPUT_DIR
from app.schemas.canonical_document import CanonicalDocumentRecord
from app.schemas.chunking import ChunkRecord


SOURCE_PAGE_DIRECTORY_PATTERN = re.compile(r"^levelek(?P<page_id>[1-9]\d*)?$")


@dataclass(frozen=True)
class DiscoveredSourcePage:
    """Identity of a source-page directory found in an output dataset."""

    name: str
    page_id: int | None


SourceMetadataStatus = Literal["available", "missing", "invalid"]
DocumentsStatus = Literal["processed", "processed_empty", "not_processed", "invalid"]


class SourceMetadataRecord(BaseModel):
    """Fields persisted by FileRepository.save_source_metadata."""

    source_url: str = Field(min_length=1)
    content_type: str
    downloaded_at: datetime
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class SourceMetadataSnapshot:
    status: SourceMetadataStatus
    source_url: str | None = None
    downloaded_at: datetime | None = None


@dataclass(frozen=True)
class DocumentsSnapshot:
    status: DocumentsStatus
    documents: tuple[CanonicalDocumentRecord, ...] = ()
    modified_at: datetime | None = None


ChunkFileStatus = Literal["available", "missing", "invalid"]


@dataclass(frozen=True)
class ChunksSnapshot:
    status: ChunkFileStatus
    chunks: tuple[ChunkRecord, ...] = ()
    modified_at: datetime | None = None
    issues: tuple["ChunkSnapshotIssue", ...] = ()


@dataclass(frozen=True)
class ChunkSnapshotIssue:
    code: str
    message: str
    line_number: int | None = None
    affected_record_count: int = 1


class OutputStatisticsRepository:
    """Inspect the output tree without modifying generated artifacts."""

    def __init__(self, output_dir: Path = OUTPUT_DIR) -> None:
        self.output_dir = output_dir

    def output_exists(self) -> bool:
        return self.output_dir.is_dir()

    def discover_source_pages(self) -> list[DiscoveredSourcePage]:
        if not self.output_exists():
            return []

        pages: list[DiscoveredSourcePage] = []
        for path in self.output_dir.iterdir():
            if not path.is_dir():
                continue

            match = SOURCE_PAGE_DIRECTORY_PATTERN.fullmatch(path.name)
            if match is None:
                continue

            raw_page_id = match.group("page_id")
            pages.append(
                DiscoveredSourcePage(
                    name=path.name,
                    page_id=int(raw_page_id) if raw_page_id is not None else None,
                )
            )

        return sorted(
            pages,
            key=lambda page: (
                page.page_id is not None,
                page.page_id if page.page_id is not None else 0,
            ),
        )

    def read_source_metadata(self, page: DiscoveredSourcePage) -> SourceMetadataSnapshot:
        metadata_path = self.output_dir / page.name / "source.json"
        if not metadata_path.is_file():
            return SourceMetadataSnapshot(status="missing")

        try:
            raw_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata = SourceMetadataRecord.model_validate(raw_metadata)
        except (OSError, UnicodeError, json.JSONDecodeError, ValidationError):
            return SourceMetadataSnapshot(status="invalid")

        return SourceMetadataSnapshot(
            status="available",
            source_url=metadata.source_url,
            downloaded_at=metadata.downloaded_at,
        )

    def read_documents(self, page: DiscoveredSourcePage) -> DocumentsSnapshot:
        documents_path = self.output_dir / page.name / "documents.jsonl"
        if not documents_path.is_file():
            return DocumentsSnapshot(status="not_processed")

        try:
            lines = documents_path.read_text(encoding="utf-8").splitlines()
            documents = tuple(
                CanonicalDocumentRecord.model_validate(json.loads(line))
                for line in lines
                if line.strip()
            )
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            TypeError,
            ValidationError,
        ):
            return DocumentsSnapshot(status="invalid")

        return DocumentsSnapshot(
            status="processed" if documents else "processed_empty",
            documents=documents,
            modified_at=datetime.fromtimestamp(
                documents_path.stat().st_mtime,
                tz=timezone.utc,
            ),
        )

    def read_chunks(self, page: DiscoveredSourcePage, chunk_config_id: str) -> ChunksSnapshot:
        chunks_path = (self.output_dir / page.name / "chunks" / f"{chunk_config_id}.jsonl")
        
        if not chunks_path.is_file():
            return ChunksSnapshot(
                status="missing",
                issues=(
                    ChunkSnapshotIssue(
                        code="missing_file",
                        message="A konfigurációhoz tartozó chunkfájl nem található.",
                    ),
                ),
            )

        try:
            lines = chunks_path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as error:
            return ChunksSnapshot(
                status="invalid",
                issues=(
                    ChunkSnapshotIssue(
                        code="unreadable_file",
                        message=f"A chunkfájl nem olvasható: {error}",
                    ),
                ),
            )

        parsed_chunks: list[ChunkRecord] = []
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                parsed_chunks.append(
                    ChunkRecord.model_validate(json.loads(line))
                )
            except (json.JSONDecodeError, TypeError, ValidationError) as error:
                return ChunksSnapshot(
                    status="invalid",
                    chunks=tuple(parsed_chunks),
                    modified_at=datetime.fromtimestamp(
                        chunks_path.stat().st_mtime,
                        tz=timezone.utc,
                    ),
                    issues=(
                        ChunkSnapshotIssue(
                            code="invalid_record",
                            message=f"A(z) {line_number}. chunkrekord érvénytelen: {error}",
                            line_number=line_number,
                        ),
                    ),
                )

        chunks = tuple(parsed_chunks)
        mismatched_config_count = sum(
            chunk.chunk_config_id != chunk_config_id for chunk in chunks
        )
        if mismatched_config_count:
            return ChunksSnapshot(
                status="invalid",
                chunks=chunks,
                issues=(
                    ChunkSnapshotIssue(
                        code="configuration_mismatch",
                        message="A chunkfájl más konfigurációhoz tartozó rekordot tartalmaz.",
                        affected_record_count=mismatched_config_count,
                    ),
                ),
            )

        mismatched_page_count = sum(
            chunk.source_page != page.name for chunk in chunks
        )
        if mismatched_page_count:
            return ChunksSnapshot(
                status="invalid",
                chunks=chunks,
                issues=(
                    ChunkSnapshotIssue(
                        code="source_page_mismatch",
                        message="A chunkfájl más forrásoldalhoz tartozó rekordot tartalmaz.",
                        affected_record_count=mismatched_page_count,
                    ),
                ),
            )

        duplicate_chunk_count = len(chunks) - len(
            {chunk.chunk_id for chunk in chunks}
        )
        if duplicate_chunk_count:
            return ChunksSnapshot(
                status="invalid",
                chunks=chunks,
                issues=(
                    ChunkSnapshotIssue(
                        code="duplicate_chunk_id",
                        message="A chunkfájl duplikált chunkazonosítót tartalmaz.",
                        affected_record_count=duplicate_chunk_count,
                    ),
                ),
            )

        return ChunksSnapshot(
            status="available",
            chunks=chunks,
            modified_at=datetime.fromtimestamp(
                chunks_path.stat().st_mtime,
                tz=timezone.utc,
            ),
        )
