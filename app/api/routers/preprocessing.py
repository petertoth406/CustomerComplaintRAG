"""HTTP controller for download, processing, and future embedding."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_semantic_service
from app.clients.source_client import SourceDownloadError
from app.schemas.preprocessing import (
    DownloadRequest,
    DownloadResponse,
    DownloadResult,
    ProcessRequest,
    ProcessResponse,
    ProcessResult,
    RunRequest,
    RunResponse,
    RunResult,
)
from app.schemas.semantic_search import (
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingResult,
)
from app.services.preprocessing_service import PreprocessingService
from app.services.semantic_search_service import (
    SemanticBackendError,
    SemanticSearchService,
)


router = APIRouter(prefix="/preprocessing", tags=["preprocessing"])


def get_service() -> PreprocessingService:
    return PreprocessingService()


Service = Annotated[PreprocessingService, Depends(get_service)]
SemanticService = Annotated[SemanticSearchService, Depends(get_semantic_service)]


@router.post("/download", response_model=DownloadResponse)
def download_pages(request: DownloadRequest, service: Service) -> DownloadResponse:
    timestamp = service.create_timestamp() if request.timestamp else None
    output_root = f"output_{timestamp}" if timestamp else "output"
    results: list[DownloadResult] = []
    try:
        for page in request.source_pages():
            service.download(page, timestamp=timestamp)
            results.append(
                DownloadResult(
                    page=page.name,
                    output_directory=f"{output_root}/{page.name}",
                    source_url=page.url,
                    raw_html=f"{output_root}/{page.name}/raw.html",
                )
            )
    except SourceDownloadError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"A forrásoldal nem tölthető le: {error}",
        ) from error
    return DownloadResponse(timestamp=timestamp, results=results)


@router.post("/process", response_model=ProcessResponse)
def process_pages(request: ProcessRequest, service: Service) -> ProcessResponse:
    results: list[ProcessResult] = []
    try:
        for page in request.source_pages():
            block_count = service.process(page, save_blocks=request.save_blocks)
            results.append(
                ProcessResult(
                    page=page.name,
                    output_directory=f"output/{page.name}",
                    block_count=block_count,
                    blocks_json=f"output/{page.name}/blocks.json",
                )
            )
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"A mentett HTML-fájl nem található: {page.name}",
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    return ProcessResponse(results=results)


@router.post("/run", response_model=RunResponse)
def run_pipeline(request: RunRequest, service: Service) -> RunResponse:
    timestamp = service.create_timestamp() if request.timestamp else None
    output_root = f"output_{timestamp}" if timestamp else "output"
    results: list[RunResult] = []
    try:
        for page in request.source_pages():
            block_count = service.run(
                page,
                timestamp=timestamp,
                save_blocks=request.save_blocks,
            )
            results.append(
                RunResult(
                    page=page.name,
                    output_directory=f"{output_root}/{page.name}",
                    source_url=page.url,
                    raw_html=f"{output_root}/{page.name}/raw.html",
                    block_count=block_count,
                    blocks_json=f"{output_root}/{page.name}/blocks.json",
                )
            )
    except SourceDownloadError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"A forrásoldal nem tölthető le: {error}",
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    return RunResponse(timestamp=timestamp, results=results)


@router.post("/embeddings", response_model=EmbeddingResponse)
def create_embeddings(
    request: EmbeddingRequest,
    service: SemanticService,
) -> EmbeddingResponse:
    try:
        summaries = service.embed_pages(request.source_pages())
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A feldolgozott blocks.json fájl nem található a sima output mappában.",
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except SemanticBackendError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error

    results = [EmbeddingResult(**summary.__dict__) for summary in summaries]
    return EmbeddingResponse(
        results=results,
        embedded_count=sum(result.embedded_count for result in results),
        skipped_count=sum(result.skipped_count for result in results),
    )
