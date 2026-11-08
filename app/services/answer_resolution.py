"""Resolve references while retaining both the source link and the resolution outcome."""

from collections import defaultdict
from dataclasses import replace
from pathlib import PurePosixPath
from unicodedata import normalize
from urllib.parse import unquote, urlsplit, urlunsplit

from app.clients.source_client import SourceClient, SourceDownloadError, is_source_url
from app.models.document import CanonicalDocument, Message, join_message_text
from app.models.source_page import DownloadedPage
from app.services.answer_parser import AnswerParseError, parse_linked_answers


MIN_MESSAGE_CHARACTERS = 50


def _meets_minimum_length(text: str) -> bool:
    return len(" ".join(text.split())) >= MIN_MESSAGE_CHARACTERS


def _answer_key(text: str) -> str:
    return " ".join(normalize("NFC", text).casefold().split())


def _filter_short_messages(document: CanonicalDocument) -> CanonicalDocument | None:
    messages = [
        message for message in document.messages
        if message.type == "answer_reference" or _meets_minimum_length(message.text)
    ]
    if not any(message.type == "complaint" for message in messages):
        return None
    if len(messages) == len(document.messages):
        return document

    short_answers = [
        message for message in document.messages
        if message.type == "answer" and not _meets_minimum_length(message.text)
    ]
    if short_answers:
        short_linked_urls = {
            message.url for message in short_answers if message.answer_source == "linked"
        }
        linked_urls = {
            message.url for message in messages if message.answer_source == "linked"
        }
        short_inline = any(message.answer_source != "linked" for message in short_answers)
        # A previously resolved reference may have been deduplicated against a short inline answer.
        messages = [
            replace(message, resolution_status="unresolved", resolution_error="answer_too_short")
            if (
                message.type == "answer_reference"
                and message.resolution_status == "resolved"
                and message.url not in linked_urls
                and (short_inline or message.url in short_linked_urls)
            )
            else message
            for message in messages
        ]
    return replace(document, messages=messages, text=join_message_text(messages))


def _resolve(
    url: str | None,
    source_client: SourceClient,
    downloads: dict[str, DownloadedPage | SourceDownloadError],
) -> list[str]:
    if not url or not is_source_url(url):
        raise AnswerParseError("invalid_source_url")
    target = urlsplit(url)
    if PurePosixPath(unquote(target.path)).suffix.lower() == ".pdf":
        raise AnswerParseError("unsupported_format")

    download_url = urlunsplit(target._replace(fragment=""))
    if download_url not in downloads:
        try:
            downloads[download_url] = source_client.download_answer(download_url)
        except SourceDownloadError as error:
            downloads[download_url] = error
    downloaded = downloads[download_url]
    if isinstance(downloaded, SourceDownloadError):
        raise AnswerParseError(f"download_failed: {downloaded}")

    media_type = downloaded.content_type.partition(";")[0].strip().lower()
    if media_type not in {"", "text/html", "application/xhtml+xml"} or downloaded.content.startswith(b"%PDF-"):
        raise AnswerParseError("unsupported_format")
    answers = [
        text for text in parse_linked_answers(downloaded, target.fragment)
        if _meets_minimum_length(text)
    ]
    if not answers:
        raise AnswerParseError("answer_too_short")
    return answers


def resolve_answers(
    documents: list[CanonicalDocument],
    source_client: SourceClient,
) -> list[CanonicalDocument]:
    documents = [
        filtered for document in documents
        if (filtered := _filter_short_messages(document)) is not None
    ]
    owners: dict[str, set[str]] = defaultdict(set)
    for document in documents:
        for message in document.messages:
            if message.type == "answer_reference" and message.url:
                owners[message.url].add(document.document_id)

    downloads: dict[str, DownloadedPage | SourceDownloadError] = {}
    outcomes: dict[str | None, list[str] | AnswerParseError] = {}
    result: list[CanonicalDocument] = []
    for document in documents:
        known_answers = {
            _answer_key(message.text) for message in document.messages if message.type == "answer"
        }
        messages: list[Message] = []
        added_answer = False
        for message in document.messages:
            if message.type == "answer" and message.answer_source is None:
                messages.append(replace(message, url=message.url or document.source_url, answer_source="inline"))
                continue
            if message.type != "answer_reference" or message.resolution_status == "resolved":
                messages.append(message)
                continue

            if message.url not in outcomes:
                try:
                    if message.url and len(owners[message.url]) > 1:
                        raise AnswerParseError("ambiguous_reference")
                    outcomes[message.url] = _resolve(message.url, source_client, downloads)
                except AnswerParseError as error:
                    outcomes[message.url] = error

            outcome = outcomes[message.url]
            if isinstance(outcome, AnswerParseError):
                messages.append(replace(message, resolution_status="unresolved", resolution_error=str(outcome)))
                continue

            messages.append(replace(message, resolution_status="resolved", resolution_error=None))
            for answer in outcome:
                key = _answer_key(answer)
                if key in known_answers:
                    continue
                known_answers.add(key)
                added_answer = True
                messages.append(Message(type="answer", text=answer, url=message.url, answer_source="linked"))

        text = join_message_text(messages) if added_answer else document.text
        result.append(replace(document, messages=messages, text=text))
    return result
