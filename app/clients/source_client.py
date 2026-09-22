"""HTTP client for the external consumer protection source."""

import ssl
import urllib.error
import urllib.request

from app.core.config import SOURCE_INSECURE
from app.models.source_page import DownloadedPage, SourcePage


class SourceDownloadError(Exception):
    """The source page could not be fetched."""


class SourceClient:
    def download(self, page: SourcePage) -> DownloadedPage:
        request = urllib.request.Request(
            page.url,
            headers={"User-Agent": "CustomerComplaintRAG (Óbudai Egyetem)"},
        )
        ssl_context = ssl._create_unverified_context() if SOURCE_INSECURE else None
        try:
            with urllib.request.urlopen(request, timeout=30, context=ssl_context) as response:
                return DownloadedPage(
                    content=response.read(),
                    content_type=response.headers.get("Content-Type", ""),
                )
        except (urllib.error.URLError, TimeoutError) as error:
            raise SourceDownloadError(str(error)) from error
