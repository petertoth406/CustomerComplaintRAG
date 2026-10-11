"""Parse complaint blocks from a downloaded HTML page."""

import codecs
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.models.complaint import Block, Message, ParsedPage


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


# def find_content_cell(soup):
#     cells = soup.find_all("td", attrs={"width": "600"})
#     if not cells:
#         return None
#     return max(
#         cells,
#         key=lambda element: (
#             len(element.find_all("hr")),
#             len(element.find_all(["h2", "h6"])),
#             len(element.get_text(strip=True)),
#         ),
#     )

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


def parse_html(content: bytes, content_type: str, source_url: str) -> ParsedPage:
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
    blocks: list[Block] = []

    for index, fragment in enumerate(fragments, start=1):
        fragment_soup = BeautifulSoup(fragment, "html.parser")
        messages: list[Message] = []

        for element in fragment_soup.find_all(["h2", "h6"]):
            element_text = extract_clean_text(element)
            if not element_text:
                continue

            answer_link = next(
                (
                    anchor for anchor in element.find_all("a", href=True)
                    if "válasza" in anchor.get_text(" ", strip=True).casefold()
                ),
                None,
            )
            if element.name == "h2" and answer_link is not None:
                messages.append(
                    Message(
                        type="answer_reference",
                        text=answer_link.get_text(" ", strip=True),
                        url=urljoin(source_url, answer_link["href"]),
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

        blocks.append(
            Block(
                block_id=index,
                source_url=source_url,
                messages=messages,
                full_text="\n\n".join(
                    message.text for message in messages
                    if message.type != "answer_reference"
                ),
            )
        )

    return ParsedPage(blocks=blocks, html_fragments=fragments)
