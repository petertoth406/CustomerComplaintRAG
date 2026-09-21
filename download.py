from __future__ import annotations

import argparse
import codecs
import re
import ssl
import urllib.request
from pathlib import Path


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


def split_and_save(content: bytes, content_type: str, output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "raw.html").write_bytes(content)

    encoding = detect_encoding(content, content_type)
    html = content.decode(encoding, errors="replace")
    fragments = [fragment.strip() for fragment in HR_PATTERN.split(html) if fragment.strip()]

    blocks_dir = output_dir / "blocks"
    blocks_dir.mkdir(exist_ok=True)
    for index, fragment in enumerate(fragments, start=1):
        block = '<meta charset="utf-8">\n' + fragment
        (blocks_dir / f"block_{index:03d}.html").write_text(block, encoding="utf-8")

    print(f"Felismert karakterkódolás: {encoding}")
    return len(fragments)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
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
        block_count = split_and_save(content, content_type, output_dir)

        print(f"Nyers HTML: {output_dir / 'raw.html'}")
        print(f"Létrehozott blokkok: {block_count} db ({output_dir / 'blocks'})")


if __name__ == "__main__":
    main()
