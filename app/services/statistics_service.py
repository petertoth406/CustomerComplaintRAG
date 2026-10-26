"""Build statistics metadata from the file-based output dataset."""

from datetime import datetime, timezone
from math import ceil
import re
from statistics import fmean, median

from app.core.chunk_config import ChunkConfigRegistry
from app.core.config import DEFAULT_CHUNK_CONFIG_ID
from app.repositories.output_statistics_repository import (
    ChunksSnapshot,
    DocumentsSnapshot,
    OutputStatisticsRepository,
)
from app.schemas.canonical_document import CanonicalDocumentRecord
from app.schemas.chunking import ChunkConfig, ChunkRecord
from app.schemas.statistics import (
    STATISTICS_SCHEMA_VERSION,
    ChunkConfigurationDescriptor,
    ContentCounts,
    ContentLengthStatistics,
    DatasetChunkStatistics,
    DatasetDescriptor,
    DatasetSummary,
    DiscoveredPage,
    LengthDistribution,
    PageChunkStatistics,
    PageStatistics,
    StatisticsResponse,
    TextLengthStatistics,
    TokenizerDescriptor,
)
from app.services.tokenizer_service import TokenizerService


class StatisticsService:
    _CONFIG_VERSION_PATTERN = re.compile(r"_v(?P<version>[1-9]\d*)$")

    def __init__(
        self,
        repository: OutputStatisticsRepository | None = None,
        chunk_config_registry: ChunkConfigRegistry | None = None,
        tokenizer_service: TokenizerService | None = None,
    ) -> None:
        self.repository = repository or OutputStatisticsRepository()
        self.chunk_config_registry = chunk_config_registry or ChunkConfigRegistry()
        self.tokenizer_service = tokenizer_service

    def get_statistics(self, *, include_tokens: bool = False) -> StatisticsResponse:
        tokenizer = self._get_tokenizer() if include_tokens else None
        token_count_cache: dict[str, int] | None = {} if tokenizer else None
        chunk_configs = self.chunk_config_registry.all()
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
        all_documents: list[CanonicalDocumentRecord] = []
        all_chunks_by_config: dict[str, list[ChunkRecord]] = {
            config.id: [] for config in chunk_configs
        }
        for page in source_pages:
            source_metadata = self.repository.read_source_metadata(page)
            documents_snapshot = self.repository.read_documents(page)
            content_counts = self._count_content(documents_snapshot.documents)
            length_statistics = self._calculate_content_lengths(
                documents_snapshot.documents,
                tokenizer,
                token_count_cache,
            )
            if documents_snapshot.status in {"not_processed", "invalid"}:
                content_counts = ContentCounts()
                length_statistics = None
            else:
                all_documents.extend(documents_snapshot.documents)

            page_chunk_statistics: list[PageChunkStatistics] = []
            for config in chunk_configs:
                chunks_snapshot = self.repository.read_chunks(page, config.id)
                if chunks_snapshot.status == "available":
                    all_chunks_by_config[config.id].extend(chunks_snapshot.chunks)
                page_chunk_statistics.append(
                    self._build_page_chunk_statistics(
                        documents_snapshot,
                        chunks_snapshot,
                        config,
                    )
                )

            page_statistics.append(
                PageStatistics(
                    page=page.name,
                    page_id=page.page_id,
                    source_url=source_metadata.source_url,
                    downloaded_at=source_metadata.downloaded_at,
                    download_status=source_metadata.status,
                    processing_status=documents_snapshot.status,
                    content=content_counts,
                    lengths=length_statistics,
                    chunk_statistics=page_chunk_statistics,
                )
            )

        output_dir = self.repository.output_dir
        return StatisticsResponse(
            generated_at=datetime.now(timezone.utc),
            statistics_schema_version=STATISTICS_SCHEMA_VERSION,
            tokens_included=include_tokens,
            tokenizer=(
                TokenizerDescriptor(
                    model=tokenizer.model,
                    revision=tokenizer.revision,
                )
                if tokenizer is not None
                else None
            ),
            chunk_configurations=[
                self._describe_chunk_configuration(config)
                for config in chunk_configs
            ],
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
            summary=self._build_summary(
                page_statistics,
                tuple(all_documents),
                tokenizer,
                token_count_cache,
                chunk_configs,
                all_chunks_by_config,
            ),
            pages=page_statistics,
        )

    @classmethod
    def _describe_chunk_configuration(cls, config: ChunkConfig ) -> ChunkConfigurationDescriptor:
        version_match = cls._CONFIG_VERSION_PATTERN.search(config.id)
        return ChunkConfigurationDescriptor(
            chunk_config_id=config.id,
            version=(
                int(version_match.group("version"))
                if version_match is not None
                else None
            ),
            strategy=config.strategy,
            collection_name=config.collection_name,
            tokenizer_model=config.tokenizer_model,
            tokenizer_revision=config.tokenizer_revision,
            max_tokens=config.max_tokens,
            overlap_tokens=config.overlap_tokens,
        )

    @classmethod
    def _build_page_chunk_statistics(cls, documents_snapshot: DocumentsSnapshot, chunks_snapshot: ChunksSnapshot, config: ChunkConfig) -> PageChunkStatistics:
        chunks = chunks_snapshot.chunks
        covered_document_ids = {chunk.document_id for chunk in chunks}
        expected_document_ids = (
            {document.document_id for document in documents_snapshot.documents}
            if documents_snapshot.status in {"processed", "processed_empty"}
            else None
        )
        missing_document_count = (
            len(expected_document_ids - covered_document_ids)
            if expected_document_ids is not None
            else None
        )
        if chunks_snapshot.status in {"missing", "invalid"}:
            status = chunks_snapshot.status
        elif expected_document_ids is None:
            status = "unverifiable"
        elif missing_document_count:
            status = "partial"
        else:
            status = "complete"

        return PageChunkStatistics(
            chunk_config_id=config.id,
            status=status,
            document_count=len(covered_document_ids),
            chunk_count=len(chunks),
            missing_document_count=missing_document_count,
            token_lengths=cls._calculate_distribution(
                [chunk.token_count for chunk in chunks]
            ),
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

    @classmethod
    def _calculate_content_lengths(
        cls,
        documents: tuple[CanonicalDocumentRecord, ...],
        tokenizer: TokenizerService | None,
        token_count_cache: dict[str, int] | None,
    ) -> ContentLengthStatistics:
        document_texts = [document.text for document in documents]
        complaint_texts = [
            message.text
            for document in documents
            for message in document.messages
            if message.type == "complaint"
        ]
        inline_answer_texts = [
            message.text
            for document in documents
            for message in document.messages
            if message.type == "answer"
        ]
        return ContentLengthStatistics(
            documents=cls._calculate_text_lengths(
                document_texts,
                tokenizer,
                token_count_cache,
            ),
            complaints=cls._calculate_text_lengths(
                complaint_texts,
                tokenizer,
                token_count_cache,
            ),
            inline_answers=cls._calculate_text_lengths(
                inline_answer_texts,
                tokenizer,
                token_count_cache,
            ),
        )

    @classmethod
    def _calculate_text_lengths(
        cls,
        texts: list[str],
        tokenizer: TokenizerService | None,
        token_count_cache: dict[str, int] | None,
    ) -> TextLengthStatistics:
        return TextLengthStatistics(
            characters=cls._calculate_distribution([len(text) for text in texts]),
            words=cls._calculate_distribution(
                [len(text.split()) for text in texts]
            ),
            tokens=(
                cls._calculate_distribution(
                    [
                        cls._token_count(text, tokenizer, token_count_cache)
                        for text in texts
                    ]
                )
                if tokenizer is not None
                else None
            ),
        )

    @staticmethod
    def _token_count(
        text: str,
        tokenizer: TokenizerService,
        cache: dict[str, int] | None,
    ) -> int:
        if cache is None:
            return len(tokenizer.encode(text).token_ids)
        if text not in cache:
            cache[text] = len(tokenizer.encode(text).token_ids)
        return cache[text]

    @staticmethod
    def _calculate_distribution(values: list[int]) -> LengthDistribution:
        if not values:
            return LengthDistribution(count=0, total=0)

        sorted_values = sorted(values)

        def nearest_rank(percentile: float) -> int:
            index = max(ceil(percentile * len(sorted_values)) - 1, 0)
            return sorted_values[index]

        return LengthDistribution(
            count=len(sorted_values),
            total=sum(sorted_values),
            minimum=sorted_values[0],
            maximum=sorted_values[-1],
            average=round(fmean(sorted_values), 2),
            median=median(sorted_values),
            percentile_90=nearest_rank(0.90),
            percentile_95=nearest_rank(0.95),
        )

    @classmethod
    def _build_summary(
        cls,
        pages: list[PageStatistics],
        documents: tuple[CanonicalDocumentRecord, ...],
        tokenizer: TokenizerService | None,
        token_count_cache: dict[str, int] | None,
        chunk_configs: list[ChunkConfig],
        all_chunks_by_config: dict[str, list[ChunkRecord]],
    ) -> DatasetSummary:
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
            lengths=cls._calculate_content_lengths(
                documents,
                tokenizer,
                token_count_cache,
            ),
            chunk_statistics=[
                cls._build_dataset_chunk_statistics(
                    pages,
                    config,
                    all_chunks_by_config[config.id],
                )
                for config in chunk_configs
            ],
        )

    @classmethod
    def _build_dataset_chunk_statistics(cls, pages: list[PageStatistics], config: ChunkConfig, chunks: list[ChunkRecord]) -> DatasetChunkStatistics:
        page_statistics = [
            next(
                item
                for item in page.chunk_statistics
                if item.chunk_config_id == config.id
            )
            for page in pages
        ]
        complete_page_count = sum(
            item.status == "complete" for item in page_statistics
        )
        partial_page_count = sum(
            item.status == "partial" for item in page_statistics
        )
        missing_page_count = sum(
            item.status == "missing" for item in page_statistics
        )
        invalid_page_count = sum(
            item.status == "invalid" for item in page_statistics
        )
        unverifiable_page_count = sum(
            item.status == "unverifiable" for item in page_statistics
        )
        missing_document_count = sum(
            item.missing_document_count or 0 for item in page_statistics
        )

        if invalid_page_count:
            status = "invalid"
        elif missing_page_count == len(page_statistics):
            status = "missing"
        elif complete_page_count == len(page_statistics):
            status = "complete"
        else:
            status = "partial"

        return DatasetChunkStatistics(
            chunk_config_id=config.id,
            status=status,
            page_count=len(page_statistics),
            complete_page_count=complete_page_count,
            partial_page_count=partial_page_count,
            missing_page_count=missing_page_count,
            invalid_page_count=invalid_page_count,
            unverifiable_page_count=unverifiable_page_count,
            document_count=sum(
                item.document_count for item in page_statistics
            ),
            chunk_count=len(chunks),
            missing_document_count=missing_document_count,
            token_lengths=cls._calculate_distribution(
                [chunk.token_count for chunk in chunks]
            ),
        )

    def _get_tokenizer(self) -> TokenizerService:
        if self.tokenizer_service is None:
            config = self.chunk_config_registry.get(DEFAULT_CHUNK_CONFIG_ID)
            self.tokenizer_service = TokenizerService(
                config.tokenizer_model,
                config.tokenizer_revision,
            )
        return self.tokenizer_service
