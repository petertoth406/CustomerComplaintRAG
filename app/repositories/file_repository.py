"""Storage compatible with the existing output/levelek*/ layout."""

import json
import shutil
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from app.core.config import OUTPUT_DIR
from app.models.chunk import Chunk
from app.models.document import CanonicalDocument
from app.models.source_page import DownloadedPage, SourcePage
from app.schemas.canonical_document import CanonicalDocumentRecord
from app.schemas.chunking import ChunkRecord


class FileRepository:
    def __init__(self, output_dir: Path = OUTPUT_DIR) -> None:
        self.output_dir = output_dir

    def page_dir(self, page: SourcePage, *, timestamp: str | None = None) -> Path:
        output_dir = (
            self.output_dir
            if timestamp is None
            else self.output_dir.with_name(f"{self.output_dir.name}_{timestamp}")
        )
        return output_dir / page.name

    def save_source_metadata(self, page: SourcePage, downloaded: DownloadedPage, *, timestamp: str | None = None) -> Path:
        page_dir = self.page_dir(page, timestamp=timestamp)
        page_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = page_dir / "source.json"
        metadata_path.write_text(
            json.dumps(
                {
                    "source_url": page.url,
                    "content_type": downloaded.content_type,
                    "downloaded_at": datetime.now(timezone.utc).isoformat(),
                    "content_sha256": sha256(downloaded.content).hexdigest(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return metadata_path

    def save_raw(self, page: SourcePage, downloaded: DownloadedPage, *, timestamp: str | None = None) -> Path:
        page_dir = self.page_dir(page, timestamp=timestamp)
        page_dir.mkdir(parents=True, exist_ok=True)
        raw_path = page_dir / "raw.html"
        raw_path.write_bytes(downloaded.content)
        self.save_source_metadata(page, downloaded, timestamp=timestamp)
        return raw_path

    def remove_raw(self, page: SourcePage, *, timestamp: str | None = None) -> None:
        (self.page_dir(page, timestamp=timestamp) / "raw.html").unlink(missing_ok=True)

    def remove_legacy_artifacts(self, page: SourcePage, *, timestamp: str | None = None) -> None:
        page_dir = self.page_dir(page, timestamp=timestamp)
        (page_dir / "blocks.json").unlink(missing_ok=True)
        legacy_directory = page_dir / "blocks"
        if legacy_directory.is_dir():
            shutil.rmtree(legacy_directory)

    def load_raw(self, page: SourcePage, *, timestamp: str | None = None) -> DownloadedPage:
        page_dir = self.page_dir(page, timestamp=timestamp)
        content = (page_dir / "raw.html").read_bytes()
        metadata_path = page_dir / "source.json"
        content_type = ""
        if metadata_path.is_file():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            content_type = metadata.get("content_type", "")
        return DownloadedPage(content=content, content_type=content_type)

    def load_documents(self, page: SourcePage) -> list[dict]:
        documents_path = self.page_dir(page) / "documents.jsonl"
        documents: list[dict] = []
        for line_number, line in enumerate(
            documents_path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            document = json.loads(line)
            if not isinstance(document, dict):
                raise ValueError(
                    f"A {documents_path} {line_number}. sora nem JSON objektum."
                )
            validated_document = CanonicalDocumentRecord.model_validate(document)
            documents.append(validated_document.model_dump(mode="json"))
        return documents

    def save_documents(self, page: SourcePage, documents: list[CanonicalDocument], *, timestamp: str | None = None) -> Path:
        page_dir = self.page_dir(page, timestamp=timestamp)
        page_dir.mkdir(parents=True, exist_ok=True)
        documents_path = page_dir / "documents.jsonl"
        serialized_documents = []
        for document in documents:
            validated_document = CanonicalDocumentRecord.model_validate(
                asdict(document)
            )
            serialized_documents.append(
                json.dumps(
                    validated_document.model_dump(mode="json"),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
        content = "\n".join(serialized_documents)
        if content:
            content += "\n"
        documents_path.write_text(content, encoding="utf-8")
        return documents_path

    def save_chunks(self, page: SourcePage, chunk_config_id: str, chunks: list[Chunk]) -> Path:
        chunks_dir = self.page_dir(page) / "chunks"
        chunks_dir.mkdir(parents=True, exist_ok=True)
        chunks_path = chunks_dir / f"{chunk_config_id}.jsonl"
        serialized_chunks = []
        for chunk in chunks:
            validated_chunk = ChunkRecord.model_validate(asdict(chunk))
            serialized_chunks.append(
                json.dumps(
                    validated_chunk.model_dump(mode="json"),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
        content = "\n".join(serialized_chunks)
        if content:
            content += "\n"
        chunks_path.write_text(content, encoding="utf-8")
        return chunks_path
