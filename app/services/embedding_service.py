"""Embedding generation through Ollama."""

from typing import Any

import ollama

from app.core.config import OLLAMA_BASE_URL, OLLAMA_EMBEDDING_MODEL
from app.services.semantic_backend import SemanticBackendError


class EmbeddingService:
    """Create embeddings independently from document and vector storage."""

    def __init__(
        self,
        ollama_client: Any | None = None,
        model: str = OLLAMA_EMBEDDING_MODEL,
    ) -> None:
        self.ollama_client = ollama_client or ollama.Client(host=OLLAMA_BASE_URL)
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        try:
            response = self.ollama_client.embed(
                model=self.model,
                input=texts,
            )
        except Exception as error:
            raise SemanticBackendError(f"Az embedding modell nem érhető el: {error}") from error

        embeddings = [list(embedding) for embedding in response.embeddings]
        if len(embeddings) != len(texts):
            raise SemanticBackendError("Az embedding modell nem minden bemenethez adott vissza vektort." )
        return embeddings
