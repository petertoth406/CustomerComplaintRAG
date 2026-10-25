"""Create structural and fixed-token chunks from canonical documents."""

from dataclasses import dataclass

from app.models.chunk import Chunk
from app.schemas.chunking import ChunkConfig
from app.services.tokenizer_service import TokenizedText, TokenizerService


@dataclass(frozen=True)
class TokenSpan:
    token_start: int
    token_end: int
    text: str


class StructuralChunker:
    def split(self, text: str, tokenized: TokenizedText) -> list[TokenSpan]:
        if not text.strip():
            return []
        return [
            TokenSpan(
                token_start=0,
                token_end=len(tokenized.token_ids),
                text=text,
            )
        ]


class FixedTokenChunker:
    def split(self, text: str, tokenized: TokenizedText, *, max_tokens: int, overlap_tokens: int) -> list[TokenSpan]:
        token_count = len(tokenized.token_ids)
        if token_count == 0:
            return []

        spans: list[TokenSpan] = []
        step = max_tokens - overlap_tokens
        token_start = 0
        while token_start < token_count:
            token_end = min(token_start + max_tokens, token_count)
            char_start = tokenized.offsets[token_start][0]
            char_end = tokenized.offsets[token_end - 1][1]
            chunk_text = text[char_start:char_end].strip()
            if chunk_text:
                spans.append(
                    TokenSpan(
                        token_start=token_start,
                        token_end=token_end,
                        text=chunk_text,
                    )
                )
            if token_end == token_count:
                break
            token_start += step
        return spans


class ChunkingService:
    def __init__(self) -> None:
        self.structural_chunker = StructuralChunker()
        self.fixed_token_chunker = FixedTokenChunker()
        self._tokenizers: dict[tuple[str, str], TokenizerService] = {}

    def chunk_documents(self, documents: list[dict], config: ChunkConfig) -> list[Chunk]:
        tokenizer = self._get_tokenizer(config)
        chunks: list[Chunk] = []

        for document in documents:
            text = str(document["text"])
            tokenized = tokenizer.encode(text)
            if config.strategy == "structural":
                spans = self.structural_chunker.split(text, tokenized)
            else:
                if config.max_tokens is None:
                    raise ValueError(f"Hiányzó max_tokens a konfigurációban: {config.id}")
                spans = self.fixed_token_chunker.split(
                    text,
                    tokenized,
                    max_tokens=config.max_tokens,
                    overlap_tokens=config.overlap_tokens,
                )

            document_id = str(document["document_id"])
            for chunk_index, span in enumerate(spans, start=1):
                chunks.append(
                    Chunk(
                        chunk_id=f"{document_id}:{config.id}:{chunk_index:04d}",
                        document_id=document_id,
                        chunk_config_id=config.id,
                        strategy=config.strategy,
                        chunk_index=chunk_index,
                        token_start=span.token_start,
                        token_end=span.token_end,
                        token_count=span.token_end - span.token_start,
                        source_page=str(document["source_page"]),
                        source_page_id=document.get("source_page_id"),
                        document_index=int(document["document_index"]),
                        source_url=str(document["source_url"]),
                        text=span.text,
                    )
                )
        return chunks

    def _get_tokenizer(self, config: ChunkConfig) -> TokenizerService:
        key = (config.tokenizer_model, config.tokenizer_revision)
        if key not in self._tokenizers:
            self._tokenizers[key] = TokenizerService(*key)
        return self._tokenizers[key]
