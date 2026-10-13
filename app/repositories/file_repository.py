"""Storage compatible with the existing output/levelek*/ layout."""

import json
from dataclasses import asdict
from pathlib import Path

from app.core.config import OUTPUT_DIR
from app.models.complaint import ParsedPage
from app.models.document import CanonicalDocument
from app.models.source_page import DownloadedPage, SourcePage
from app.schemas.canonical_document import CanonicalDocumentRecord


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

    def save_raw(self, page: SourcePage, downloaded: DownloadedPage, *, timestamp: str | None = None) -> Path:
        page_dir = self.page_dir(page, timestamp=timestamp)
        page_dir.mkdir(parents=True, exist_ok=True)
        raw_path = page_dir / "raw.html"
        raw_path.write_bytes(downloaded.content)
        (page_dir / "source.json").write_text(
            json.dumps(
                {"source_url": page.url, "content_type": downloaded.content_type},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return raw_path

    def load_raw(self, page: SourcePage, *, timestamp: str | None = None) -> DownloadedPage:
        page_dir = self.page_dir(page, timestamp=timestamp)
        content = (page_dir / "raw.html").read_bytes()
        metadata_path = page_dir / "source.json"
        content_type = ""
        if metadata_path.is_file():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            content_type = metadata.get("content_type", "")
        return DownloadedPage(content=content, content_type=content_type)

    def load_blocks(self, page: SourcePage) -> list[dict]:
        blocks_path = self.page_dir(page) / "blocks.json"
        blocks = json.loads(blocks_path.read_text(encoding="utf-8"))
        if not isinstance(blocks, list):
            raise ValueError(f"A {blocks_path} tartalma nem lista.")
        return blocks

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

    def save_processed(self, page: SourcePage, parsed: ParsedPage, *, timestamp: str | None = None, save_blocks: bool = False) -> Path:
        page_dir = self.page_dir(page, timestamp=timestamp)
        page_dir.mkdir(parents=True, exist_ok=True)
        json_path = page_dir / "blocks.json"
        json_path.write_text(
            json.dumps(
                [
                    {
                        "block_id": block.block_id,
                        "source_url": block.source_url,
                        "messages": [
                            {key: value for key, value in asdict(message).items() if value is not None}
                            for message in block.messages
                        ],
                        "full_text": block.full_text,
                    }
                    for block in parsed.blocks
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        if save_blocks:
            blocks_dir = page_dir / "blocks"
            blocks_dir.mkdir(exist_ok=True)
            for index, fragment in enumerate(parsed.html_fragments, start=1):
                (blocks_dir / f"block_{index:03d}.html").write_text(
                    '<meta charset="utf-8">\n' + fragment,
                    encoding="utf-8",
                )
        return json_path
