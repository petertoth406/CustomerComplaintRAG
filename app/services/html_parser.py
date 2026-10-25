"""Parse canonical complaint documents from a downloaded HTML page."""

import codecs
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.core.config import CANONICAL_DOCUMENT_SCHEMA_VERSION
from app.models.document import CanonicalDocument, Message
from app.models.source_page import SourcePage


HR_PATTERN = re.compile(r"<hr\b[^>]*>", re.IGNORECASE)
CHARSET_PATTERN = re.compile(rb"charset\s*=\s*[\"']?\s*([a-zA-Z0-9._-]+)", re.IGNORECASE)


def is_known_encoding(name: str) -> bool:
    try:
        codecs.lookup(name)
    except LookupError:
        return False
    return True


def detect_encoding(content: bytes, content_type: str | None) -> str:
    if content_type:
        match = re.search(r"charset\s*=\s*([a-zA-Z0-9._-]+)", content_type, re.IGNORECASE)
        if match and is_known_encoding(match.group(1)):
            return match.group(1)

    match = CHARSET_PATTERN.search(content[:10_000])
    if match:
        encoding = match.group(1).decode("ascii")
        if is_known_encoding(encoding):
            return encoding

    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        return "cp1250"
    return "utf-8"


def extract_clean_text(element) -> str:
    for br in element.find_all("br"):
        br.replace_with("\n")
    raw_text = element.get_text("\n", strip=True)
    return "\n".join(
        " ".join(line.split())
        for line in raw_text.splitlines()
        if line.strip()
    )


def message_element_without_nested_messages(element):
    fragment = BeautifulSoup(str(element), "html.parser")
    cloned_element = fragment.find(element.name)
    if cloned_element is None:
        return fragment
    for nested_message in cloned_element.find_all(["h2", "h6"]):
        nested_message.decompose()
    return cloned_element

def count_own_hr(cell):
    return sum(
        hr.find_parent("td") is cell
        for hr in cell.find_all("hr")
    )


def find_content_cell(soup):
    cells = soup.find_all("td", attrs={"width": "600"})

    return max(
        cells,
        key=count_own_hr,
        default=None,
    )


def parse_html(content: bytes, content_type: str, page: SourcePage) -> list[CanonicalDocument]:
    encoding = detect_encoding(content, content_type)
    soup = BeautifulSoup(content.decode(encoding, errors="replace"), "html.parser")
    content_cell = find_content_cell(soup)
    if content_cell is None:
        raise ValueError("Nem található a leveleket tartalmazó HTML-elem.")

    fragments = [
        fragment.strip()
        for fragment in HR_PATTERN.split(content_cell.decode_contents())
        if fragment.strip()
    ]
    documents: list[CanonicalDocument] = []

    for index, fragment in enumerate(fragments, start=1):
        fragment_soup = BeautifulSoup(fragment, "html.parser")
        messages: list[Message] = []

        for element in fragment_soup.find_all(["h2", "h6"]):
            own_element = message_element_without_nested_messages(element)
            element_text = extract_clean_text(own_element)
            if not element_text:
                continue

            answer_link = next(
                (
                    anchor for anchor in own_element.find_all("a", href=True)
                    if "válasza" in anchor.get_text(" ", strip=True).casefold()
                ),
                None,
            )
            if element.name == "h2" and answer_link is not None:
                messages.append(
                    Message(
                        type="answer_reference",
                        text=answer_link.get_text(" ", strip=True),
                        url=urljoin(page.url, answer_link["href"]),
                    )
                )
                continue

            message_type = "answer" if element.name == "h6" else "complaint"
            if messages and messages[-1].type == message_type:
                previous = messages[-1]
                messages[-1] = Message(
                    type=previous.type,
                    text=previous.text + "\n" + element_text,
                )
            else:
                messages.append(Message(type=message_type, text=element_text))

        text = "\n\n".join(
            message.text
            for message in messages
            if message.type != "answer_reference"
        )
        if not text.strip():
            continue
        documents.append(
            CanonicalDocument(
                schema_version=CANONICAL_DOCUMENT_SCHEMA_VERSION,
                document_id=f"complaint:{page.name}:{index:04d}",
                source_page=page.name,
                source_page_id=page.page_id,
                document_index=index,
                source_url=page.url,
                messages=messages,
                text=text,
            )
        )

    return documents
