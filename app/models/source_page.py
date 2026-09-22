"""Source page identity and downloaded content."""

from dataclasses import dataclass

from app.core.config import BASE_URL


@dataclass(frozen=True)
class SourcePage:
    page_id: int | None = None

    @property
    def name(self) -> str:
        return "levelek" if self.page_id is None else f"levelek{self.page_id}"

    @property
    def url(self) -> str:
        return f"{BASE_URL}/{self.name}.htm"

    def output_name(self, timestamp: str | None = None) -> str:
        return self.name if timestamp is None else f"{self.name}_{timestamp}"


@dataclass(frozen=True)
class DownloadedPage:
    content: bytes
    content_type: str
