"""Configuration for the current file-based backend."""

import os
from pathlib import Path


BASE_URL = "https://fogyasztovedelem.hu/Varia_x"
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output"
SOURCE_INSECURE = os.getenv("SOURCE_INSECURE", "false").lower() in {"1", "true", "yes"}
