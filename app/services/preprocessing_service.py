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

    def download(self, page: SourcePage, *, output_name: str | None = None) -> str:
        downloaded = self.source_client.download(page)
        self.file_repository.save_raw(page, downloaded, output_name=output_name)
        return output_name or page.name

    def process(self, page: SourcePage, *, output_name: str | None = None, save_blocks: bool = False) -> int:
        downloaded = self.file_repository.load_raw(page, output_name=output_name)
        parsed = parse_html(downloaded.content, downloaded.content_type, page.url)
        self.file_repository.save_processed(page, parsed, output_name=output_name, save_blocks=save_blocks)
        return len(parsed.blocks)

    def run(self, page: SourcePage, *, output_name: str | None = None, save_blocks: bool = False) -> int:
        self.download(page, output_name=output_name)
        return self.process(page, output_name=output_name, save_blocks=save_blocks)
