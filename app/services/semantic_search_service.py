"""Coordinate source loading, embedding generation, and semantic search."""

from dataclasses import dataclass
from typing import Any

from app.core.config import CHROMA_COLLECTION, EMBEDDING_BATCH_SIZE
from app.models.source_page import SourcePage
from app.repositories.chroma_repository import ChromaRepository, VectorRecord
from app.repositories.file_repository import FileRepository
from app.services.embedding_service import EmbeddingService


TOP_RESULTS = 5


@dataclass(frozen=True)
class EmbeddingSummary:
    page_id: int | None
    page: str
    embedded_count: int
    skipped_count: int


class SemanticSearchService:
    """Orchestrate document loading, embedding, and vector persistence."""

    def __init__(
        self,
        file_repository: FileRepository | None = None,
        ollama_client: Any | None = None,
        collection: Any | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_store: ChromaRepository | None = None,
        collection_name: str = CHROMA_COLLECTION,
    ) -> None:
        self.file_repository = file_repository or FileRepository()
        self.embedding_service = embedding_service or EmbeddingService(ollama_client=ollama_client)
        self.vector_store = vector_store or ChromaRepository(
            collection=collection,
            collection_name=collection_name,
        )

    def embed_pages(self, pages: list[SourcePage]) -> list[EmbeddingSummary]:
        return [self.embed_page(page) for page in pages]

    def embed_page(self, page: SourcePage) -> EmbeddingSummary:
        documents = self.file_repository.load_documents(page)
        records: list[VectorRecord] = []
        skipped_count = 0

        for document in documents:
            text = document.get("text")
            document_id = document.get("document_id")
            document_index = document.get("document_index")
            if (
                not isinstance(text, str)
                or not text.strip()
                or not isinstance(document_id, str)
                or not isinstance(document_index, int)
            ):
                skipped_count += 1
                continue

            metadata: dict[str, str | int] = {
                "page": page.name,
                "document_id": document_id,
                "document_index": document_index,
                "source_url": str(document.get("source_url", page.url)),
            }
            if page.page_id is not None:
                metadata["page_id"] = page.page_id
            records.append(
                VectorRecord(
                    record_id=document_id,
                    document=text,
                    metadata=metadata,
                )
            )

        current_ids = {record.record_id for record in records}
        for start in range(0, len(records), EMBEDDING_BATCH_SIZE):
            batch = records[start : start + EMBEDDING_BATCH_SIZE]
            embeddings = self.embedding_service.embed(
                [record.document for record in batch]
            )
            self.vector_store.upsert(batch, embeddings)

        stale_ids = [
            stored_id
            for stored_id in self.vector_store.stored_ids_for_page(page.name)
            if stored_id not in current_ids
        ]
        self.vector_store.delete(stale_ids)

        return EmbeddingSummary(
            page_id=page.page_id,
            page=page.name,
            embedded_count=len(records),
            skipped_count=skipped_count,
        )

    def search(self, query: str) -> list[dict[str, Any]]:
        query_text = query.strip()
        if not query_text:
            raise ValueError("A keresési szöveg nem lehet üres.")

        query_embedding = self.embedding_service.embed([query_text])[0]
        results = self.vector_store.search(
            query_embedding,
            n_results=TOP_RESULTS,
        )
        hits: list[dict[str, Any]] = []
        for rank, result in enumerate(results, start=1):
            metadata = result.metadata
            hits.append(
                {
                    "rank": rank,
                    "page_id": metadata.get("page_id"),
                    "page": metadata.get("page", ""),
                    "document_id": metadata.get("document_id", ""),
                    "document_index": metadata.get("document_index", 0),
                    "text": result.document,
                    "source_url": metadata.get("source_url", ""),
                    "distance": result.distance,
                }
            )
        return hits
