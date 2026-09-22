"""Configuration for the current file-based backend."""

import os
from pathlib import Path


BASE_URL = "https://fogyasztovedelem.hu/Varia_x"
OUTPUT_DIR = Path(
    os.getenv("OUTPUT_DIR", Path(__file__).resolve().parents[2] / "output")
)
SOURCE_INSECURE = os.getenv("SOURCE_INSECURE", "false").lower() in {"1", "true", "yes"}

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_EMBEDDING_MODEL = os.getenv(
    "OLLAMA_EMBEDDING_MODEL", "qwen3-embedding:0.6b"
)

CHROMA_HOST = os.getenv("CHROMA_HOST", "127.0.0.1")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8001"))
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "customer_complaints")
