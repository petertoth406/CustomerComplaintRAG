"""Extract company letters from linked HTML pages."""

import re
from dataclasses import dataclass
from urllib.parse import unquote

from bs4 import BeautifulSoup, Tag

from app.models.source_page import DownloadedPage
from app.services.html_parser import (
    detect_encoding,
    extract_clean_text,
    message_element_without_nested_messages,
)


ANSWER_HEADING = re.compile(r"\bválasz(?:a|ai|levél)?[!.:]?$", re.IGNORECASE)
SALUTATION = re.compile(r"^(?:tisztelt|kedves|üdvözlöm|jó napot)\b", re.IGNORECASE)
SIGN_OFF = re.compile(
    r"\b(?:üdvözlettel|tisztelettel|köszönettel|szép napot)[,:!.](?=\s|$)",
    re.IGNORECASE,
)
REPLY_COLORS = {"#006464", "#00640a"}


class AnswerParseError(ValueError):
    """The HTML does not identify a company letter reliably."""


@dataclass(frozen=True)
class ReplyBlock:
    tag: Tag
    text: str
    marked: bool


def _matches_anchor(tag: Tag, fragment: str) -> bool:
    return tag.get("id") == fragment or (tag.name == "a" and tag.get("name") == fragment)


def _scope_blocks(container: Tag, tags: list[Tag], fragment: str) -> list[Tag]:
    if not fragment:
        return tags
    fragment = unquote(fragment)
    descendants = container.find_all(True)
    matches = [tag for tag in [container, *descendants] if _matches_anchor(tag, fragment)]
    if not matches:
        raise AnswerParseError("fragment_not_found")
    if len(matches) != 1:
        raise AnswerParseError("ambiguous_fragment")
    anchor = matches[0]
    enclosed = [tag for tag in tags if tag is anchor or any(parent is anchor for parent in tag.parents)]
    if anchor is container or (enclosed and all(tag is not anchor for tag in tags)):
        return enclosed

    # Legacy named anchors usually precede the letter rather than wrapping it.
    positions = {id(tag): index for index, tag in enumerate(descendants)}
    start = positions[id(anchor)]
    for tag in tags:
        if any(parent is tag for parent in anchor.parents):
            start = positions[id(tag)]
            break
    end = min(
        (
            position for tag in descendants
            if (position := positions[id(tag)]) > positions[id(anchor)]
            and (
                tag.name == "hr"
                or (tag.name == "a" and tag.has_attr("name"))
                or (tag.name in {"h2", "h6"} and tag.has_attr("id"))
            )
        ),
        default=len(positions),
    )
    return [tag for tag in tags if start <= positions[id(tag)] < end]


def _reply_blocks(tags: list[Tag]) -> tuple[list[ReplyBlock], bool]:
    blocks: list[ReplyBlock] = []
    answer_heading = False
    for tag in tags:
        own_tag = message_element_without_nested_messages(tag)
        text = extract_clean_text(own_tag)
        label = " ".join(text.split())
        if not label or label.strip("[] ").casefold() in {"vissza", "a lap tetejére"}:
            continue
        if len(label.split()) <= 8 and ANSWER_HEADING.search(label):
            if answer_heading and blocks:
                raise AnswerParseError("ambiguous_answer")
            answer_heading = True
            blocks.clear()
            continue
        marked = any(
            font["color"].strip().casefold() in REPLY_COLORS
            for font in own_tag.find_all("font", color=True)
        )
        blocks.append(ReplyBlock(tag, text, marked))
    return blocks, answer_heading


def _has_body(text: str) -> bool:
    while SALUTATION.match(text):
        text = re.sub(r"^[^\n!,]+(?:[!,]|\n|$)\s*", "", text, count=1)
    closing = SIGN_OFF.search(text)
    if closing:
        text = text[:closing.start()]
    return any(character.isalpha() for character in text)


def _letter_body(blocks: list[ReplyBlock], *, identified: bool) -> str:
    parts: list[str] = []
    has_body = False
    seen_salutation = False
    signed = False
    for block in blocks:
        text = block.text
        if signed:
            break
        salutation = SALUTATION.match(text) is not None
        if salutation and has_body and (seen_salutation or len(parts) > 1 or len(parts[0]) > 90):
            raise AnswerParseError("ambiguous_answer")
        parts.append(text)
        seen_salutation |= salutation
        has_body |= _has_body(text)
        signed = bool(SIGN_OFF.search(text))

    if not has_body:
        raise AnswerParseError("answer_text_not_found")
    if not (identified or signed):
        raise AnswerParseError("ambiguous_answer")
    return "\n".join(parts)


def _marked_letters(blocks: list[ReplyBlock]) -> list[str]:
    letters: list[str] = []
    current: list[ReplyBlock] = []
    has_body = False
    seen_salutation = False
    for block in blocks:
        salutation = SALUTATION.match(block.text) is not None
        if salutation and seen_salutation and has_body:
            letters.append(_letter_body(current, identified=True))
            current = []
            has_body = False
        current.append(block)
        has_body |= _has_body(block.text)
        seen_salutation |= salutation
    letters.append(_letter_body(current, identified=True))
    return letters


def parse_linked_answers(downloaded: DownloadedPage, fragment: str) -> list[str]:
    encoding = detect_encoding(downloaded.content, downloaded.content_type)
    try:
        decoded = downloaded.content.decode(encoding, errors="replace")
    except (LookupError, UnicodeError) as error:
        raise AnswerParseError("invalid_encoding") from error
    soup = BeautifulSoup(decoded, "html.parser")
    cells = soup.find_all("td", width="600")
    container = max(cells, key=lambda cell: len(cell.get_text(strip=True)), default=None)
    if container is None:
        raise AnswerParseError("answer_text_not_found")

    tags = _scope_blocks(container, container.find_all(["h2", "h6"]), fragment)
    blocks, answer_heading = _reply_blocks(tags)

    if not fragment and container.find("hr") is not None:
        block_ids = {id(block.tag) for block in blocks}
        seen_block = False
        separated = False
        for tag in container.find_all(True):
            if id(tag) in block_ids:
                if separated:
                    raise AnswerParseError("ambiguous_answer")
                seen_block = True
            elif tag.name == "hr" and seen_block:
                separated = True

    legacy_answers = [block for block in blocks if block.tag.name == "h6"]
    if legacy_answers:
        return [_letter_body([block], identified=True) for block in legacy_answers]

    marked = [block for block in blocks if block.marked]
    if marked:
        return _marked_letters(marked)
    return [_letter_body(blocks, identified=answer_heading)]
