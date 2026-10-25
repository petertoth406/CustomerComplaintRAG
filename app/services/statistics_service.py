"""Build statistics metadata from the file-based output dataset."""

from datetime import datetime, timezone

from app.repositories.output_statistics_repository import (
    OutputStatisticsRepository,
)
from app.schemas.statistics import (
    STATISTICS_SCHEMA_VERSION,
    DatasetDescriptor,
    DiscoveredPage,
    StatisticsDiscoveryResponse,
)


class StatisticsService:
    def __init__(
        self,
        repository: OutputStatisticsRepository | None = None,
    ) -> None:
        self.repository = repository or OutputStatisticsRepository()

    def discover_dataset(self) -> StatisticsDiscoveryResponse:
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

        output_dir = self.repository.output_dir
        return StatisticsDiscoveryResponse(
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
        )
