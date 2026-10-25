"""Validation contracts for chunk configuration and JSONL records."""

from pydantic import BaseModel, Field, model_validator

from app.models.chunk import ChunkStrategy


class ChunkConfig(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    strategy: ChunkStrategy
    collection_name: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]+$")
    tokenizer_model: str = Field(min_length=1)
    tokenizer_revision: str = Field(min_length=1)
    max_tokens: int | None = Field(default=None, ge=1)
    overlap_tokens: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_strategy_parameters(self) -> "ChunkConfig":
        if self.strategy == "structural":
            if self.max_tokens is not None or self.overlap_tokens != 0:
                raise ValueError(
                    "A strukturális konfigurációhoz nem adható meg tokenméret vagy átfedés."
                )
            return self

        if self.max_tokens is None:
            raise ValueError("A fix tokenes konfigurációhoz max_tokens szükséges.")
        if self.overlap_tokens >= self.max_tokens:
            raise ValueError("Az átfedésnek kisebbnek kell lennie a chunkméretnél.")
        return self


class ChunkRecord(BaseModel):
    chunk_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    chunk_config_id: str = Field(min_length=1)
    strategy: ChunkStrategy
    chunk_index: int = Field(ge=1)
    token_start: int = Field(ge=0)
    token_end: int = Field(ge=0)
    token_count: int = Field(ge=0)
    source_page: str = Field(min_length=1)
    source_page_id: int | None = Field(default=None, ge=1)
    document_index: int = Field(ge=1)
    source_url: str = Field(min_length=1)
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_token_range(self) -> "ChunkRecord":
        if self.token_end < self.token_start:
            raise ValueError("A chunk tokenvége nem előzheti meg a tokenkezdetet.")
        if self.token_count != self.token_end - self.token_start:
            raise ValueError("A chunkszám és a tokentartomány nem egyezik.")
        return self
