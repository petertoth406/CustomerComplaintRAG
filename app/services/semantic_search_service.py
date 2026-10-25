"""Coordinate chunking, embedding generation, and semantic search."""

from dataclasses import dataclass
from typing import Any

from app.core.chunk_config import ChunkConfigRegistry
from app.core.config import EMBEDDING_BATCH_SIZE
from app.models.source_page import SourcePage
from app.repositories.chroma_repository import ChromaRepository, VectorRecord
from app.repositories.file_repository import FileRepository
from app.schemas.chunking import ChunkConfig
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService


TOP_RESULTS = 5


@dataclass(frozen=True)
class EmbeddingSummary:
    page_id: int | None
    page: str
    chunk_config_id: str
    collection_name: str
    chunks_jsonl: str
    embedded_count: int
    skipped_count: int


class SemanticSearchService:
    def __init__(
        self,
        file_repository: FileRepository | None = None,
        ollama_client: Any | None = None,
        embedding_service: EmbeddingService | None = None,
        chunking_service: ChunkingService | None = None,
        chunk_config_registry: ChunkConfigRegistry | None = None,
    ) -> None:
        self.file_repository = file_repository or FileRepository()
        self.embedding_service = embedding_service or EmbeddingService(
            ollama_client=ollama_client
        )
        self.chunking_service = chunking_service or ChunkingService()
        self.chunk_config_registry = chunk_config_registry or ChunkConfigRegistry()
        self.vector_stores: dict[str, ChromaRepository] = {}

    def embed_pages(
        self,
        pages: list[SourcePage],
        chunk_config_ids: list[str] | None = None,
    ) -> list[EmbeddingSummary]:
        configs = self.chunk_config_registry.resolve(chunk_config_ids)
        return [
            self.embed_page(page, config)
            for page in pages
            for config in configs
        ]

    def embed_page(
        self,
        page: SourcePage,
        config: ChunkConfig,
    ) -> EmbeddingSummary:
        documents = self.file_repository.load_documents(page)
        chunks = self.chunking_service.chunk_documents(documents, config)
        self.file_repository.save_chunks(page, config.id, chunks)
        vector_store = self._get_vector_store(config)

        records: list[VectorRecord] = []
        for chunk in chunks:
            metadata: dict[str, str | int] = {
                "page": chunk.source_page,
                "document_id": chunk.document_id,
                "document_index": chunk.document_index,
                "chunk_id": chunk.chunk_id,
                "chunk_config_id": chunk.chunk_config_id,
                "chunk_index": chunk.chunk_index,
                "strategy": chunk.strategy,
                "token_start": chunk.token_start,
                "token_end": chunk.token_end,
                "token_count": chunk.token_count,
                "source_url": chunk.source_url,
            }
            if chunk.source_page_id is not None:
                metadata["page_id"] = chunk.source_page_id
            records.append(
                VectorRecord(
                    record_id=chunk.chunk_id,
                    document=chunk.text,
                    metadata=metadata,
                )
            )

        current_ids = {record.record_id for record in records}
        for start in range(0, len(records), EMBEDDING_BATCH_SIZE):
            batch = records[start : start + EMBEDDING_BATCH_SIZE]
            embeddings = self.embedding_service.embed(
                [record.document for record in batch]
            )
            vector_store.upsert(batch, embeddings)

        stale_ids = [
            stored_id
            for stored_id in vector_store.stored_ids_for_page(page.name)
            if stored_id not in current_ids
        ]
        vector_store.delete(stale_ids)

        chunked_document_ids = {chunk.document_id for chunk in chunks}
        return EmbeddingSummary(
            page_id=page.page_id,
            page=page.name,
            chunk_config_id=config.id,
            collection_name=config.collection_name,
            chunks_jsonl=f"output/{page.name}/chunks/{config.id}.jsonl",
            embedded_count=len(records),
            skipped_count=sum(
                str(document["document_id"]) not in chunked_document_ids
                for document in documents
            ),
        )

    def search(
        self,
        query: str,
        chunk_config_id: str,
    ) -> list[dict[str, Any]]:
        query_text = query.strip()
        if not query_text:
            raise ValueError("A keresési szöveg nem lehet üres.")

        config = self.chunk_config_registry.get(chunk_config_id)
        query_embedding = self.embedding_service.embed([query_text])[0]
        results = self._get_vector_store(config).search(
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
                    "chunk_id": metadata.get("chunk_id", ""),
                    "chunk_config_id": metadata.get("chunk_config_id", config.id),
                    "chunk_index": metadata.get("chunk_index", 0),
                    "token_count": metadata.get("token_count", 0),
                    "text": result.document,
                    "source_url": metadata.get("source_url", ""),
                    "distance": result.distance,
                }
            )
        return hits

    def _get_vector_store(self, config: ChunkConfig) -> ChromaRepository:
        if config.id not in self.vector_stores:
            self.vector_stores[config.id] = ChromaRepository(
                collection_name=config.collection_name
            )
        return self.vector_stores[config.id]
