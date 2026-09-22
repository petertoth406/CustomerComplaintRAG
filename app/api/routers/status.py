"""Application status endpoint."""

from fastapi import APIRouter


router = APIRouter(prefix="/status", tags=["status"])


@router.get("")
def get_status() -> dict[str, str]:
    return {"status": "running"}
