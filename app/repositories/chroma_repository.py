"""ChromaDB persistence for embedded text records."""

from dataclasses import dataclass
from typing import Any

import chromadb

from app.core.config import CHROMA_HOST, CHROMA_PORT
from app.services.semantic_backend import SemanticBackendError


MetadataValue = str | int | float | bool


@dataclass(frozen=True)
class VectorRecord:
    record_id: str
    document: str
    metadata: dict[str, MetadataValue]


@dataclass(frozen=True)
class VectorSearchResult:
    document: str
    metadata: dict[str, Any]
    distance: float


class ChromaRepository:
    def __init__(
        self,
        collection_name: str,
        collection: Any | None = None,
        chroma_client: Any | None = None,
    ) -> None:
        if collection is None:
            try:
                client = chroma_client or chromadb.HttpClient(
                    host=CHROMA_HOST,
                    port=CHROMA_PORT,
                )
                collection = client.get_or_create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
            except Exception as error:
                raise SemanticBackendError(f"A ChromaDB kapcsolat nem hozható létre: {error}") from error
        self.collection = collection

    def upsert(self, records: list[VectorRecord], embeddings: list[list[float]]) -> None:
        if not records:
            return
        if len(records) != len(embeddings):
            raise ValueError("A rekordok és embeddingek száma nem egyezik.")

        try:
            self.collection.upsert(
                ids=[record.record_id for record in records],
                embeddings=embeddings,
                documents=[record.document for record in records],
                metadatas=[record.metadata for record in records],
            )
        except Exception as error:
            raise SemanticBackendError(f"A ChromaDB írás sikertelen: {error}") from error

    def stored_ids_for_page(self, page: str) -> list[str]:
        try:
            stored = self.collection.get(where={"page": page})
        except Exception as error:
            raise SemanticBackendError(f"A ChromaDB olvasás sikertelen: {error}") from error
        return list(stored.get("ids", []))

    def delete(self, record_ids: list[str]) -> None:
        if not record_ids:
            return
        try:
            self.collection.delete(ids=record_ids)
        except Exception as error:
            raise SemanticBackendError(
                f"A ChromaDB törlés sikertelen: {error}"
            ) from error

    def search(self, query_embedding: list[float], *, n_results: int) -> list[VectorSearchResult]:
        try:
            result = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as error:
            raise SemanticBackendError(f"A ChromaDB keresés sikertelen: {error}") from error

        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        return [
            VectorSearchResult(
                document=document or "",
                metadata=metadata or {},
                distance=float(distance),
            )
            for document, metadata, distance in zip(
                documents,
                metadatas,
                distances,
            )
        ]
