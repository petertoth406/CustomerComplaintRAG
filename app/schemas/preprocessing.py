"""Request and response contracts for the preprocessing API."""

from pydantic import BaseModel, Field, model_validator

from app.models.source_page import SourcePage


class PageSelection(BaseModel):
    page_id: int | None = Field(default=None, ge=1)
    start_page: int | None = Field(default=None, ge=1)
    end_page: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_selection(self) -> "PageSelection":
        if self.page_id is not None and (
            self.start_page is not None or self.end_page is not None
        ):
            raise ValueError("A page_id és a tartomány egyszerre nem adható meg.")
        if self.end_page is not None and self.start_page is None:
            raise ValueError("Az end_page mezőhöz start_page is szükséges.")
        return self

    def source_pages(self) -> list[SourcePage]:
        if self.page_id is not None:
            return [SourcePage(self.page_id)]
        if self.start_page is None:
            return [SourcePage()]
        end_page = self.end_page if self.end_page is not None else self.start_page
        step = 1 if self.start_page <= end_page else -1
        return [
            SourcePage(page_id)
            for page_id in range(self.start_page, end_page + step, step)
        ]


class PageRequest(PageSelection):
    pass


class DownloadRequest(PageSelection):
    timestamp: bool = False


class ProcessRequest(PageSelection):
    save_blocks: bool = False


class RunRequest(ProcessRequest):
    timestamp: bool = False


class DownloadResult(BaseModel):
    page: str
    output_directory: str
    source_url: str
    raw_html: str


class ProcessResult(BaseModel):
    page: str
    output_directory: str
    block_count: int
    blocks_json: str
    documents_jsonl: str


class RunResult(DownloadResult):
    block_count: int
    blocks_json: str
    documents_jsonl: str


class DownloadResponse(BaseModel):
    timestamp: str | None
    results: list[DownloadResult]


class ProcessResponse(BaseModel):
    results: list[ProcessResult]


class RunResponse(BaseModel):
    timestamp: str | None
    results: list[RunResult]
