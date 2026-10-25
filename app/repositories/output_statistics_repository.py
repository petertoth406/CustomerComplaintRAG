"""Read-only discovery of source-page directories in an output dataset."""

from dataclasses import dataclass
from pathlib import Path
import re

from app.core.config import OUTPUT_DIR


SOURCE_PAGE_DIRECTORY_PATTERN = re.compile(
    r"^levelek(?P<page_id>[1-9]\d*)?$"
)


@dataclass(frozen=True)
class DiscoveredSourcePage:
    """Identity of a source-page directory found in an output dataset."""

    name: str
    page_id: int | None


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
