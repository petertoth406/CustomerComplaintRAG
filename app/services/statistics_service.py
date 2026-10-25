"""Build statistics metadata from the file-based output dataset."""

from datetime import datetime, timezone

from app.repositories.output_statistics_repository import (
    OutputStatisticsRepository,
)
from app.schemas.canonical_document import CanonicalDocumentRecord
from app.schemas.statistics import (
    STATISTICS_SCHEMA_VERSION,
    ContentCounts,
    DatasetDescriptor,
    DatasetSummary,
    DiscoveredPage,
    PageStatistics,
    StatisticsResponse,
)


class StatisticsService:
    def __init__(
        self,
        repository: OutputStatisticsRepository | None = None,
    ) -> None:
        self.repository = repository or OutputStatisticsRepository()

    def get_statistics(self) -> StatisticsResponse:
        source_pages = self.repository.discover_source_pages()
        numeric_page_ids = [
            page.page_id for page in source_pages if page.page_id is not None
        ]
        first_page_id = min(numeric_page_ids, default=None)
        last_page_id = max(numeric_page_ids, default=None)
        discovered_page_ids = set(numeric_page_ids)
        missing_page_ids = (
            [
                page_id
                for page_id in range(first_page_id, last_page_id + 1)
                if page_id not in discovered_page_ids
            ]
            if first_page_id is not None and last_page_id is not None
            else []
        )

        page_statistics: list[PageStatistics] = []
        for page in source_pages:
            source_metadata = self.repository.read_source_metadata(page)
            documents_snapshot = self.repository.read_documents(page)
            content_counts = self._count_content(documents_snapshot.documents)
            if documents_snapshot.status in {"not_processed", "invalid"}:
                content_counts = ContentCounts()

            page_statistics.append(
                PageStatistics(
                    page=page.name,
                    page_id=page.page_id,
                    source_url=source_metadata.source_url,
                    downloaded_at=source_metadata.downloaded_at,
                    download_status=source_metadata.status,
                    processing_status=documents_snapshot.status,
                    content=content_counts,
                )
            )

        output_dir = self.repository.output_dir
        return StatisticsResponse(
            generated_at=datetime.now(timezone.utc),
            statistics_schema_version=STATISTICS_SCHEMA_VERSION,
            dataset=DatasetDescriptor(
                dataset_id=output_dir.name,
                output_directory=str(output_dir),
                exists=self.repository.output_exists(),
                discovered_page_count=len(source_pages),
                discovered_pages=[
                    DiscoveredPage(page=page.name, page_id=page.page_id)
                    for page in source_pages
                ],
                first_page_id=first_page_id,
                last_page_id=last_page_id,
                missing_page_ids_inside_range=missing_page_ids,
            ),
            summary=self._build_summary(page_statistics),
            pages=page_statistics,
        )

    @staticmethod
    def _count_content(
        documents: tuple[CanonicalDocumentRecord, ...],
    ) -> ContentCounts:
        complaint_document_count = 0
        complaint_message_count = 0
        inline_answer_count = 0
        external_answer_reference_count = 0
        answered_document_count = 0

        for document in documents:
            message_types = [message.type for message in document.messages]
            complaint_messages = message_types.count("complaint")
            inline_answers = message_types.count("answer")
            external_answers = message_types.count("answer_reference")

            complaint_document_count += complaint_messages > 0
            complaint_message_count += complaint_messages
            inline_answer_count += inline_answers
            external_answer_reference_count += external_answers
            answered_document_count += inline_answers + external_answers > 0

        return ContentCounts(
            document_count=len(documents),
            complaint_document_count=complaint_document_count,
            complaint_message_count=complaint_message_count,
            inline_answer_count=inline_answer_count,
            external_answer_reference_count=external_answer_reference_count,
            detected_answer_count=(
                inline_answer_count + external_answer_reference_count
            ),
            answered_document_count=answered_document_count,
        )

    @staticmethod
    def _build_summary(pages: list[PageStatistics]) -> DatasetSummary:
        counted_pages = [
            page
            for page in pages
            if page.processing_status in {"processed", "processed_empty"}
        ]

        def content_sum(field_name: str) -> int:
            return sum(
                getattr(page.content, field_name) or 0
                for page in counted_pages
            )

        return DatasetSummary(
            page_directory_count=len(pages),
            downloaded_page_count=sum(
                page.download_status == "available" for page in pages
            ),
            missing_source_metadata_count=sum(
                page.download_status == "missing" for page in pages
            ),
            invalid_source_metadata_count=sum(
                page.download_status == "invalid" for page in pages
            ),
            processed_page_count=sum(
                page.processing_status in {"processed", "processed_empty"}
                for page in pages
            ),
            empty_processed_page_count=sum(
                page.processing_status == "processed_empty" for page in pages
            ),
            not_processed_page_count=sum(
                page.processing_status == "not_processed" for page in pages
            ),
            invalid_documents_file_count=sum(
                page.processing_status == "invalid" for page in pages
            ),
            content=ContentCounts(
                document_count=content_sum("document_count"),
                complaint_document_count=content_sum("complaint_document_count"),
                complaint_message_count=content_sum("complaint_message_count"),
                inline_answer_count=content_sum("inline_answer_count"),
                external_answer_reference_count=content_sum(
                    "external_answer_reference_count"
                ),
                detected_answer_count=content_sum("detected_answer_count"),
                answered_document_count=content_sum("answered_document_count"),
            ),
        )
