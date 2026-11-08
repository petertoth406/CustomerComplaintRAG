"""HTTP client for the external consumer protection source."""

import ssl
import urllib.request
from http.client import HTTPException
from urllib.parse import quote, urlsplit

from app.core.config import BASE_URL, SOURCE_INSECURE
from app.models.source_page import DownloadedPage, SourcePage


class SourceDownloadError(Exception):
    """The source page could not be fetched."""


def is_source_url(url: str) -> bool:
    try:
        target = urlsplit(url)
        return (
            target.scheme in {"http", "https"}
            and target.hostname == urlsplit(BASE_URL).hostname
            and target.username is None
            and target.port in {None, 443 if target.scheme == "https" else 80}
        )
    except ValueError:
        return False


class SourceRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not is_source_url(newurl):
            raise SourceDownloadError("Az átirányítás a forrásoldal domainjén kívülre mutat.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class SourceClient:
    def download(self, page: SourcePage) -> DownloadedPage:
        ssl_context = ssl._create_unverified_context() if SOURCE_INSECURE else None
        return self._download(page.url, lambda request: urllib.request.urlopen(
            request, timeout=30, context=ssl_context,
        ))

    def download_answer(self, url: str) -> DownloadedPage:
        if not is_source_url(url):
            raise SourceDownloadError("A válaszlink a forrásoldal domainjén kívülre mutat.")
        ssl_context = ssl._create_unverified_context() if SOURCE_INSECURE else None
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ssl_context),
            SourceRedirectHandler(),
        )
        return self._download(url, lambda request: opener.open(request, timeout=30))

    @staticmethod
    def _download(url, open_request) -> DownloadedPage:
        request = urllib.request.Request(
            quote(url, safe=":/?&=%;@+$,[]!()*'-._~"),
            headers={"User-Agent": "CustomerComplaintRAG (Óbudai Egyetem)"},
        )
        try:
            with open_request(request) as response:
                return DownloadedPage(
                    content=response.read(),
                    content_type=response.headers.get("Content-Type", ""),
                )
        except (OSError, HTTPException, ValueError) as error:
            raise SourceDownloadError(str(error)) from error
