"""Configuration for the current file-based backend."""

import os
from pathlib import Path
from typing import Literal


BASE_URL = "https://fogyasztovedelem.hu/Varia_x"
OUTPUT_DIR = Path(
    os.getenv("OUTPUT_DIR", Path(__file__).resolve().parents[2] / "output")
)
SOURCE_INSECURE = os.getenv("SOURCE_INSECURE", "false").lower() in {"1", "true", "yes"}
DEV_MODE = os.getenv("DEV_MODE", "false").lower() in {"1", "true", "yes"}


CanonicalDocumentSchemaVersion = Literal["1.0"]
CANONICAL_DOCUMENT_SCHEMA_VERSION: CanonicalDocumentSchemaVersion = "1.0"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_EMBEDDING_MODEL = os.getenv(
    "OLLAMA_EMBEDDING_MODEL", "bge-m3"
)

CHROMA_HOST = os.getenv("CHROMA_HOST", "127.0.0.1")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8001"))
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "customer_complaints")
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))
