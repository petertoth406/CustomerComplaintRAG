"""Orchestrate download and HTML processing operations."""

from datetime import datetime, timezone

from app.clients.source_client import SourceClient
from app.models.source_page import SourcePage
from app.repositories.file_repository import FileRepository
from app.services.html_parser import parse_html


class PreprocessingService:
    def __init__(
        self,
        source_client: SourceClient | None = None,
        file_repository: FileRepository | None = None,
    ) -> None:
        self.source_client = source_client or SourceClient()
        self.file_repository = file_repository or FileRepository()

    @staticmethod
    def create_timestamp() -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")

    def download(self, page: SourcePage, *, timestamp: str | None = None) -> str:
        downloaded = self.source_client.download(page)
        self.file_repository.save_raw(page, downloaded, timestamp=timestamp)
        return page.name

    def process(self, page: SourcePage, *, timestamp: str | None = None) -> int:
        downloaded = self.file_repository.load_raw(page, timestamp=timestamp)
        documents = parse_html(downloaded.content, downloaded.content_type, page)
        self.file_repository.save_documents(page, documents, timestamp=timestamp)
        self.file_repository.remove_legacy_artifacts(page, timestamp=timestamp)
        return len(documents)

    def run(self, page: SourcePage, *, timestamp: str | None = None) -> int:
        downloaded = self.source_client.download(page)
        documents = parse_html(downloaded.content, downloaded.content_type, page)
        self.file_repository.save_source_metadata(page, downloaded, timestamp=timestamp)
        self.file_repository.save_documents(page, documents, timestamp=timestamp)
        self.file_repository.remove_raw(page, timestamp=timestamp)
        self.file_repository.remove_legacy_artifacts(page, timestamp=timestamp)
        return len(documents)
