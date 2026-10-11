"""Create full-text embeddings and query them in ChromaDB."""

from dataclasses import dataclass
from typing import Any

import chromadb
import ollama

from app.core.config import (
    CHROMA_COLLECTION,
    CHROMA_HOST,
    CHROMA_PORT,
    EMBEDDING_BATCH_SIZE,
    OLLAMA_BASE_URL,
    OLLAMA_EMBEDDING_MODEL,
)
from app.models.source_page import SourcePage
from app.repositories.file_repository import FileRepository


TOP_RESULTS = 5


class SemanticBackendError(Exception):
    """The embedding model or vector database could not complete an operation."""


@dataclass(frozen=True)
class EmbeddingSummary:
    page_id: int | None
    page: str
    embedded_count: int
    skipped_count: int


class SemanticSearchService:
    def __init__(
        self,
        file_repository: FileRepository | None = None,
        ollama_client: Any | None = None,
        collection: Any | None = None,
    ) -> None:
        self.file_repository = file_repository or FileRepository()
        self.ollama_client = ollama_client or ollama.Client(host=OLLAMA_BASE_URL)
        if collection is None:
            try:
                chroma_client = chromadb.HttpClient(
                    host=CHROMA_HOST,
                    port=CHROMA_PORT,
                )
                collection = chroma_client.get_or_create_collection(
                    name=CHROMA_COLLECTION,
                    metadata={"hnsw:space": "cosine"},
                )
            except Exception as error:
                raise SemanticBackendError(
                    f"A ChromaDB kapcsolat nem hozható létre: {error}"
                ) from error
        self.collection = collection

    def _embed(self, texts: list[str]) -> list[list[float]]:
        try:
            response = self.ollama_client.embed(
                model=OLLAMA_EMBEDDING_MODEL,
                input=texts,
            )
        except Exception as error:
            raise SemanticBackendError(
                f"Az embedding modell nem érhető el: {error}"
            ) from error
        embeddings = [list(embedding) for embedding in response.embeddings]
        if len(embeddings) != len(texts):
            raise SemanticBackendError(
                "Az embedding modell nem minden bemenethez adott vissza vektort."
            )
        return embeddings

    def embed_pages(self, pages: list[SourcePage]) -> list[EmbeddingSummary]:
        return [self.embed_page(page) for page in pages]

    def embed_page(self, page: SourcePage) -> EmbeddingSummary:
        blocks = self.file_repository.load_blocks(page)
        records: list[tuple[str, str, dict[str, str | int]]] = []
        skipped_count = 0

        for block in blocks:
            full_text = block.get("full_text")
            block_id = block.get("block_id")
            if (
                not isinstance(full_text, str)
                or not full_text.strip()
                or not isinstance(block_id, int)
            ):
                skipped_count += 1
                continue

            metadata: dict[str, str | int] = {
                "page": page.name,
                "block_id": block_id,
                "source_url": str(block.get("source_url", page.url)),
            }
            if page.page_id is not None:
                metadata["page_id"] = page.page_id
            records.append((f"{page.name}:{block_id}", full_text, metadata))

        current_ids = {record[0] for record in records}
        try:
            for start in range(0, len(records), EMBEDDING_BATCH_SIZE):
                batch = records[start : start + EMBEDDING_BATCH_SIZE]
                documents = [record[1] for record in batch]
                self.collection.upsert(
                    ids=[record[0] for record in batch],
                    embeddings=self._embed(documents),
                    documents=documents,
                    metadatas=[record[2] for record in batch],
                )

            stored = self.collection.get(where={"page": page.name})
            stale_ids = [
                stored_id
                for stored_id in stored.get("ids", [])
                if stored_id not in current_ids
            ]
            if stale_ids:
                self.collection.delete(ids=stale_ids)
        except SemanticBackendError:
            raise
        except Exception as error:
            raise SemanticBackendError(
                f"A ChromaDB írás sikertelen: {error}"
            ) from error

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
        query_embedding = self._embed([query_text])[0]
        try:
            result = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=TOP_RESULTS,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as error:
            raise SemanticBackendError(
                f"A ChromaDB keresés sikertelen: {error}"
            ) from error

        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        hits: list[dict[str, Any]] = []
        for rank, (document, metadata, distance) in enumerate(
            zip(documents, metadatas, distances),
            start=1,
        ):
            metadata = metadata or {}
            hits.append(
                {
                    "rank": rank,
                    "page_id": metadata.get("page_id"),
                    "page": metadata.get("page", ""),
                    "block_id": metadata.get("block_id", 0),
                    "full_text": document or "",
                    "source_url": metadata.get("source_url", ""),
                    "distance": float(distance),
                }
            )
        return hits
