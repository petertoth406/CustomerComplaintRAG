"""Build statistics metadata from the file-based output dataset."""

from collections import Counter
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
    ChunkDocumentOutlier,
    ChunkQualityStatistics,
    ChunkValidationIssue,
    ContentCounts,
    ContentLengthStatistics,
    DatasetChunkStatistics,
    DatasetDescriptor,
    DatasetSummary,
    DiscoveredPage,
    HistogramBucket,
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
                statistics, accepted_chunks = self._build_page_chunk_statistics(
                    documents_snapshot,
                    chunks_snapshot,
                    config,
                )
                page_chunk_statistics.append(statistics)
                all_chunks_by_config[config.id].extend(accepted_chunks)

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
    def _build_page_chunk_statistics(
        cls,
        documents_snapshot: DocumentsSnapshot,
        chunks_snapshot: ChunksSnapshot,
        config: ChunkConfig,
    ) -> tuple[PageChunkStatistics, tuple[ChunkRecord, ...]]:
        expected_document_ids = (
            {document.document_id for document in documents_snapshot.documents}
            if documents_snapshot.status in {"processed", "processed_empty"}
            else None
        )
        validation_issues = [
            ChunkValidationIssue(
                code=issue.code,
                severity=(
                    "error" if chunks_snapshot.status == "invalid" else "warning"
                ),
                message=issue.message,
                line_number=issue.line_number,
                affected_record_count=issue.affected_record_count,
            )
            for issue in chunks_snapshot.issues
        ]
        if chunks_snapshot.status == "available":
            validation_issues.extend(
                cls._validate_chunk_semantics(
                    chunks_snapshot.chunks,
                    expected_document_ids,
                    config,
                )
            )

        freshness_status = cls._chunk_freshness_status(
            documents_snapshot,
            chunks_snapshot,
        )
        if freshness_status == "stale":
            validation_issues.append(
                ChunkValidationIssue(
                    code="stale_chunk_file",
                    severity="warning",
                    message="A chunkfájl régebbi a dokumentumállománynál; újragenerálás javasolt.",
                )
            )

        is_invalid = chunks_snapshot.status == "invalid" or any(
            issue.severity == "error" for issue in validation_issues
        )
        chunks = (
            chunks_snapshot.chunks
            if chunks_snapshot.status == "available" and not is_invalid
            else ()
        )
        chunks_by_document = Counter(chunk.document_id for chunk in chunks)
        missing_document_count = (
            len(expected_document_ids - chunks_by_document.keys())
            if expected_document_ids is not None
            else None
        )
        if chunks_snapshot.status == "missing":
            status = "missing"
        elif is_invalid:
            status = "invalid"
        elif expected_document_ids is None:
            status = "unverifiable"
        elif missing_document_count:
            status = "partial"
        else:
            status = "complete"

        statistics = PageChunkStatistics(
            chunk_config_id=config.id,
            status=status,
            document_count=len(chunks_by_document),
            chunk_count=len(chunks),
            missing_document_count=missing_document_count,
            chunks_per_document=(
                cls._calculate_distribution(
                    list(chunks_by_document.values())
                )
                if expected_document_ids is not None
                else None
            ),
            chunks_per_document_histogram=cls._calculate_discrete_histogram(
                list(chunks_by_document.values())
            ),
            token_lengths=cls._calculate_distribution(
                [chunk.token_count for chunk in chunks]
            ),
            token_length_histogram=cls._calculate_histogram(
                [chunk.token_count for chunk in chunks]
            ),
            quality=cls._calculate_chunk_quality(chunks, config),
            freshness_status=freshness_status,
            validation_issues=validation_issues,
        )
        return statistics, chunks

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
            inline_answers = sum(
                message.type == "answer" and message.answer_source != "linked"
                for message in document.messages
            )
            external_answers = message_types.count("answer_reference")

            complaint_document_count += complaint_messages > 0
            complaint_message_count += complaint_messages
            inline_answer_count += inline_answers
            external_answer_reference_count += external_answers
            answered_document_count += document.answer_status == "answered"

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
            if message.type == "answer" and message.answer_source != "linked"
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

    @staticmethod
    def _calculate_histogram(
        values: list[int],
        bucket_count: int = 10,
    ) -> list[HistogramBucket]:
        if not values:
            return []
        maximum = max(values)
        lower_origin = 0 if min(values) == 0 else 1
        bucket_width = max(ceil((maximum - lower_origin + 1) / bucket_count), 1)
        buckets: list[HistogramBucket] = []
        lower = lower_origin
        while lower <= maximum:
            upper = min(lower + bucket_width - 1, maximum)
            count = sum(lower <= value <= upper for value in values)
            buckets.append(
                HistogramBucket(
                    label=str(lower) if lower == upper else f"{lower}–{upper}",
                    minimum=lower,
                    maximum=upper,
                    count=count,
                )
            )
            lower = upper + 1
        return buckets

    @staticmethod
    def _calculate_discrete_histogram(values: list[int]) -> list[HistogramBucket]:
        counts = Counter(values)
        return [
            HistogramBucket(
                label=str(value),
                minimum=value,
                maximum=value,
                count=count,
            )
            for value, count in sorted(counts.items())
        ]

    @staticmethod
    def _chunk_freshness_status(
        documents_snapshot: DocumentsSnapshot,
        chunks_snapshot: ChunksSnapshot,
    ) -> str:
        if (
            documents_snapshot.modified_at is None
            or chunks_snapshot.modified_at is None
        ):
            return "unverifiable"
        return (
            "stale"
            if chunks_snapshot.modified_at < documents_snapshot.modified_at
            else "current"
        )

    @classmethod
    def _validate_chunk_semantics(
        cls,
        chunks: tuple[ChunkRecord, ...],
        expected_document_ids: set[str] | None,
        config: ChunkConfig,
    ) -> list[ChunkValidationIssue]:
        issues: list[ChunkValidationIssue] = []
        chunks_by_document: dict[str, list[ChunkRecord]] = {}
        for chunk in chunks:
            chunks_by_document.setdefault(chunk.document_id, []).append(chunk)

        if expected_document_ids is not None:
            orphan_document_ids = set(chunks_by_document) - expected_document_ids
            if orphan_document_ids:
                issues.append(
                    ChunkValidationIssue(
                        code="orphan_document",
                        severity="error",
                        message="A chunkfájl a dokumentumállományban nem szereplő dokumentumra hivatkozik.",
                        affected_record_count=len(orphan_document_ids),
                    )
                )

        strategy_mismatch_count = sum(
            chunk.strategy != config.strategy for chunk in chunks
        )
        if strategy_mismatch_count:
            issues.append(
                ChunkValidationIssue(
                    code="strategy_mismatch",
                    severity="error",
                    message="A chunkrekord stratégiája nem egyezik a konfigurációval.",
                    affected_record_count=strategy_mismatch_count,
                )
            )

        non_contiguous_document_count = 0
        invalid_span_document_count = 0
        for document_chunks in chunks_by_document.values():
            ordered_chunks = sorted(
                document_chunks,
                key=lambda chunk: chunk.chunk_index,
            )
            if [chunk.chunk_index for chunk in ordered_chunks] != list(
                range(1, len(ordered_chunks) + 1)
            ):
                non_contiguous_document_count += 1

            if not ordered_chunks or ordered_chunks[0].token_start != 0:
                invalid_span_document_count += 1
                continue
            if config.strategy == "structural":
                if len(ordered_chunks) != 1:
                    invalid_span_document_count += 1
                continue
            if any(
                current.token_start
                != previous.token_end - config.overlap_tokens
                for previous, current in zip(
                    ordered_chunks,
                    ordered_chunks[1:],
                )
            ):
                invalid_span_document_count += 1

        if non_contiguous_document_count:
            issues.append(
                ChunkValidationIssue(
                    code="non_contiguous_chunk_index",
                    severity="error",
                    message="Egy vagy több dokumentumnál a chunk_index sorozat nem folytonos.",
                    affected_record_count=non_contiguous_document_count,
                )
            )
        if invalid_span_document_count:
            issues.append(
                ChunkValidationIssue(
                    code="invalid_token_span_sequence",
                    severity="error",
                    message="Egy vagy több dokumentumnál a tokentartományok kezdete vagy átfedése nem felel meg a konfigurációnak.",
                    affected_record_count=invalid_span_document_count,
                )
            )

        if config.max_tokens is not None:
            oversized_chunk_count = sum(
                chunk.token_count > config.max_tokens for chunk in chunks
            )
            if oversized_chunk_count:
                issues.append(
                    ChunkValidationIssue(
                        code="token_limit_exceeded",
                        severity="error",
                        message="Egy vagy több chunk meghaladja a konfigurált tokenlimitet.",
                        affected_record_count=oversized_chunk_count,
                    )
                )
        return issues

    @staticmethod
    def _calculate_chunk_quality(
        chunks: tuple[ChunkRecord, ...] | list[ChunkRecord],
        config: ChunkConfig,
    ) -> ChunkQualityStatistics:
        stored_token_count = sum(chunk.token_count for chunk in chunks)
        chunks_by_document: dict[str, list[ChunkRecord]] = {}
        for chunk in chunks:
            chunks_by_document.setdefault(chunk.document_id, []).append(chunk)

        unique_token_count = 0
        for document_chunks in chunks_by_document.values():
            intervals = sorted(
                (chunk.token_start, chunk.token_end)
                for chunk in document_chunks
            )
            if not intervals:
                continue
            current_start, current_end = intervals[0]
            for start, end in intervals[1:]:
                if start <= current_end:
                    current_end = max(current_end, end)
                else:
                    unique_token_count += current_end - current_start
                    current_start, current_end = start, end
            unique_token_count += current_end - current_start

        overlap_token_count = max(stored_token_count - unique_token_count, 0)
        if config.max_tokens is None:
            average_fill_percent = None
            full_chunk_count = None
            full_chunk_percent = None
            short_chunk_count = None
            short_chunk_percent = None
        else:
            chunk_count = len(chunks)
            average_fill_percent = (
                round(
                    fmean(
                        chunk.token_count / config.max_tokens * 100
                        for chunk in chunks
                    ),
                    2,
                )
                if chunks
                else None
            )
            full_chunk_count = sum(
                chunk.token_count == config.max_tokens for chunk in chunks
            )
            full_chunk_percent = (
                round(full_chunk_count / chunk_count * 100, 2)
                if chunk_count
                else 0
            )
            short_chunk_count = sum(
                chunk.token_count < config.max_tokens * 0.25 for chunk in chunks
            )
            short_chunk_percent = (
                round(short_chunk_count / chunk_count * 100, 2)
                if chunk_count
                else 0
            )

        return ChunkQualityStatistics(
            average_fill_percent=average_fill_percent,
            full_chunk_count=full_chunk_count,
            full_chunk_percent=full_chunk_percent,
            short_chunk_count=short_chunk_count,
            short_chunk_percent=short_chunk_percent,
            unique_token_count=unique_token_count,
            stored_token_count=stored_token_count,
            overlap_token_count=overlap_token_count,
            overlap_overhead_percent=(
                round(overlap_token_count / unique_token_count * 100, 2)
                if unique_token_count
                else 0
            ),
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
    def _build_dataset_chunk_statistics(
        cls,
        pages: list[PageStatistics],
        config: ChunkConfig,
        chunks: list[ChunkRecord],
    ) -> DatasetChunkStatistics:
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
        chunks_by_document = Counter(chunk.document_id for chunk in chunks)
        chunks_grouped_by_document: dict[str, list[ChunkRecord]] = {}
        for chunk in chunks:
            chunks_grouped_by_document.setdefault(chunk.document_id, []).append(chunk)

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
            chunks_per_document=cls._calculate_distribution(
                list(chunks_by_document.values())
            ),
            single_chunk_document_count=sum(
                chunk_count == 1 for chunk_count in chunks_by_document.values()
            ),
            multi_chunk_document_count=sum(
                chunk_count > 1 for chunk_count in chunks_by_document.values()
            ),
            outlier_documents=cls._build_chunk_document_outliers(
                chunks_grouped_by_document
            ),
            token_lengths=cls._calculate_distribution(
                [chunk.token_count for chunk in chunks]
            ),
            chunks_per_document_histogram=cls._calculate_discrete_histogram(
                list(chunks_by_document.values())
            ),
            token_length_histogram=cls._calculate_histogram(
                [chunk.token_count for chunk in chunks]
            ),
            quality=cls._calculate_chunk_quality(chunks, config),
            validation_error_count=sum(
                issue.severity == "error"
                for item in page_statistics
                for issue in item.validation_issues
            ),
            validation_warning_count=sum(
                issue.severity == "warning"
                for item in page_statistics
                for issue in item.validation_issues
            ),
            stale_page_count=sum(
                item.freshness_status == "stale" for item in page_statistics
            ),
        )

    @staticmethod
    def _build_chunk_document_outliers(
        chunks_by_document: dict[str, list[ChunkRecord]],
        limit: int = 10,
    ) -> list[ChunkDocumentOutlier]:
        ranked_documents = sorted(
            (
                document_chunks
                for document_chunks in chunks_by_document.values()
                if len(document_chunks) > 1
            ),
            key=lambda document_chunks: (
                -len(document_chunks),
                -sum(chunk.token_count for chunk in document_chunks),
                document_chunks[0].document_id,
            ),
        )[:limit]
        return [
            ChunkDocumentOutlier(
                document_id=document_chunks[0].document_id,
                source_page=document_chunks[0].source_page,
                source_page_id=document_chunks[0].source_page_id,
                document_index=document_chunks[0].document_index,
                source_url=document_chunks[0].source_url,
                chunk_count=len(document_chunks),
                total_token_count=sum(
                    chunk.token_count for chunk in document_chunks
                ),
            )
            for document_chunks in ranked_documents
        ]

    def _get_tokenizer(self) -> TokenizerService:
        if self.tokenizer_service is None:
            config = self.chunk_config_registry.get(DEFAULT_CHUNK_CONFIG_ID)
            self.tokenizer_service = TokenizerService(
                config.tokenizer_model,
                config.tokenizer_revision,
            )
        return self.tokenizer_service
