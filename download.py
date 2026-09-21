import argparse
import codecs
import json
import re
import ssl
import urllib.request
from pathlib import Path
from bs4 import BeautifulSoup


BASE_URL = "https://fogyasztovedelem.hu/Varia_x"
HR_PATTERN = re.compile(r"<hr\b[^>]*>", re.IGNORECASE)
CHARSET_PATTERN = re.compile(
    rb"charset\s*=\s*[\"']?\s*([a-zA-Z0-9._-]+)", re.IGNORECASE
)


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


def is_known_encoding(name: str) -> bool:
    try:
        codecs.lookup(name)
    except LookupError:
        return False
    return True

def extract_clean_text(element) -> str:
    for br in element.find_all("br"):
        br.replace_with("\n")

    raw_text = element.get_text("\n", strip=True)

    lines = [
        " ".join(line.split())
        for line in raw_text.splitlines()
        if line.strip()
    ]

    return "\n".join(lines)

def download(url: str, *, insecure: bool = False) -> tuple[bytes, str]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "CustomerComplaintRAG (Óbudai Egyetem)"},
    )
    ssl_context = ssl._create_unverified_context() if insecure else None

    with urllib.request.urlopen(request, timeout=30, context=ssl_context) as response:
        content = response.read()
        content_type = response.headers.get("Content-Type", "")
    return content, content_type


def split_and_save(content: bytes, content_type: str, output_dir: Path, source_url: str, *, save_blocks: bool = False) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "raw.html").write_bytes(content)

    encoding = detect_encoding(content, content_type)
    html = content.decode(encoding, errors="replace")

    soup = BeautifulSoup(html, "html.parser")
    content_cell = soup.find("td", attrs={"width": "600"}, valign="top")

    if content_cell is None:
        raise ValueError("Nem található a leveleket tartalmazó HTML-elem.")

    print("A leveleket tartalmazó HTML-elem megtalálva.")

    content_html = content_cell.decode_contents()

    fragments = [
        fragment.strip()
        for fragment in HR_PATTERN.split(content_html)
        if fragment.strip()
    ]

    if save_blocks:
        blocks_dir = output_dir / "blocks"
        blocks_dir.mkdir(exist_ok=True)

    blocks_data = []

    for index, fragment in enumerate(fragments, start=1):
        if save_blocks:
            block = '<meta charset="utf-8">\n' + fragment
            (blocks_dir / f"block_{index:03d}.html").write_text(block, encoding="utf-8")

        fragment_soup = BeautifulSoup(fragment, "html.parser")

        messages = []

        for element in fragment_soup.find_all(["h2", "h6"]):
            element_text = extract_clean_text(element)

            if not element_text:
                continue

            if element.name == "h2" and element.find("a") and "válasza" in element_text.casefold():
                continue

            message_type = "answer" if element.name == "h6" else "complaint"

            if messages and messages[-1]["type"] == message_type:
                messages[-1]["text"] += "\n" + element_text
            else:
                messages.append(
                    {
                        "type": message_type,
                        "text": element_text,
                    }
                )

        clean_text = "\n\n".join(message["text"] for message in messages)

        blocks_data.append(
            {
                "block_id": index,
                "source_url": source_url,
                "messages": messages,
                "full_text": clean_text,
            }
        )

    json_path = output_dir / "blocks.json"

    json_path.write_text(
        json.dumps(blocks_data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"Felismert karakterkódolás: {encoding}")
    return len(fragments)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fogyasztóvédelmi levelek letöltése és feldolgozása."
    )
    parser.add_argument(
        "--range",
        dest="page_range",
        type=int,
        nargs="+",
        metavar=("START", "END"),
        help="Egy oldalazonosító, vagy egy kezdő és záró azonosító.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output"),
        help="A kimeneti gyökérkönyvtár.",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="TLS-tanúsítvány ellenőrzésének kikapcsolása (csak indokolt esetben).",
    )
    parser.add_argument(
        "--save-blocks",
        action="store_true",
        help="A feldolgozott blokkok külön HTML-fájlokba mentése.",
    )
    args = parser.parse_args()

    if args.page_range is None:
        page_ids: list[int | None] = [None]
    elif len(args.page_range) == 1:
        page_ids = [args.page_range[0]]
    elif len(args.page_range) == 2:
        start, end = args.page_range
        step = 1 if start <= end else -1
        page_ids = list(range(start, end + step, step))
    else:
        parser.error("A --range után egy vagy két szám adható meg.")

    if any(page_id is not None and page_id < 1 for page_id in page_ids):
        parser.error("Az oldalazonosítónak pozitív számnak kell lennie.")

    for page_id in page_ids:
        page_name = "levelek" if page_id is None else f"levelek{page_id}"
        url = f"{BASE_URL}/{page_name}.htm"
        output_dir = args.output / page_name

        print(f"Levelek letöltése innen: {url}")
        content, content_type = download(url, insecure=args.insecure)
        block_count = split_and_save(content, content_type, output_dir, url, save_blocks=args.save_blocks)

        print(f"Nyers HTML: {output_dir / 'raw.html'}")
        print(f"JSON: {output_dir / 'blocks.json'}")
        print(f"Feldolgozott blokkok: {block_count} db")
        if args.save_blocks:
            print(f"HTML-blokkok: {output_dir / 'blocks'}")


if __name__ == "__main__":
    main()
