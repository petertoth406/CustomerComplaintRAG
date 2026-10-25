FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY app ./app
COPY config ./config

RUN python -c "from tokenizers import Tokenizer; from app.core.chunk_config import ChunkConfigRegistry; configs=ChunkConfigRegistry().all(); keys={(config.tokenizer_model, config.tokenizer_revision) for config in configs}; [Tokenizer.from_pretrained(model, revision=revision) for model, revision in keys]"

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/output \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/openapi.json', timeout=3)" || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
