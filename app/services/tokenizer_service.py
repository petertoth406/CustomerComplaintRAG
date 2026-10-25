"""Tokenizer adapter used by all chunking strategies."""

from dataclasses import dataclass

from tokenizers import Tokenizer

from app.services.semantic_backend import SemanticBackendError


@dataclass(frozen=True)
class TokenizedText:
    token_ids: list[int]
    offsets: list[tuple[int, int]]


class TokenizerService:
    def __init__(self, model: str, revision: str) -> None:
        self.model = model
        self.revision = revision
        try:
            self.tokenizer = Tokenizer.from_pretrained(
                model,
                revision=revision,
            )
        except Exception as error:
            raise SemanticBackendError(
                f"A tokenizer nem tölthető be ({model}@{revision}): {error}"
            ) from error

    def encode(self, text: str) -> TokenizedText:
        encoding = self.tokenizer.encode(text, add_special_tokens=False)
        return TokenizedText(
            token_ids=list(encoding.ids),
            offsets=[tuple(offset) for offset in encoding.offsets],
        )
