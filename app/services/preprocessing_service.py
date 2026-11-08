"""Orchestrate download and HTML processing operations."""

from datetime import datetime, timezone

from app.clients.source_client import SourceClient
from app.models.source_page import SourcePage
from app.repositories.file_repository import FileRepository
from app.services.answer_resolution import resolve_answers
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
        with self.file_repository.page_lock(page):
            downloaded = self.source_client.download(page)
            self.file_repository.save_raw(page, downloaded, timestamp=timestamp)
        return page.name

    def process(self, page: SourcePage, *, timestamp: str | None = None) -> int:
        with self.file_repository.page_lock(page):
            downloaded = self.file_repository.load_raw(page, timestamp=timestamp)
            documents = parse_html(downloaded.content, downloaded.content_type, page)
            documents = resolve_answers(documents, self.source_client)
            self.file_repository.save_documents(page, documents, timestamp=timestamp)
            self.file_repository.remove_legacy_artifacts(page, timestamp=timestamp)
        return len(documents)

    def run(self, page: SourcePage, *, timestamp: str | None = None) -> int:
        with self.file_repository.page_lock(page):
            downloaded = self.source_client.download(page)
            documents = parse_html(downloaded.content, downloaded.content_type, page)
            documents = resolve_answers(documents, self.source_client)
            self.file_repository.save_source_metadata(page, downloaded, timestamp=timestamp)
            self.file_repository.save_documents(page, documents, timestamp=timestamp)
            self.file_repository.remove_raw(page, timestamp=timestamp)
            self.file_repository.remove_legacy_artifacts(page, timestamp=timestamp)
        return len(documents)

    def process_answers(self, page: SourcePage, *, timestamp: str | None = None) -> int:
        with self.file_repository.page_lock(page):
            documents = self.file_repository.load_document_models(page)
            documents = resolve_answers(documents, self.source_client)
            if timestamp is not None:
                self.file_repository.copy_source_metadata(page, timestamp=timestamp)
            self.file_repository.save_documents(page, documents, timestamp=timestamp)
        return len(documents)
