"""Domain objects independent of the HTTP and storage formats."""

from dataclasses import dataclass
from typing import Literal


MessageType = Literal["complaint", "answer", "answer_reference"]


@dataclass(frozen=True)
class Message:
    type: MessageType
    text: str
    url: str | None = None


@dataclass(frozen=True)
class Block:
    block_id: int
    source_url: str
    messages: list[Message]
    full_text: str


@dataclass(frozen=True)
class ParsedPage:
    blocks: list[Block]
    html_fragments: list[str]
