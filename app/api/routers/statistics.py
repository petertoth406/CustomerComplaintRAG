"""Controller for future dataset statistics."""

from fastapi import APIRouter, HTTPException, status


router = APIRouter(prefix="/statistics", tags=["statistics"])


@router.get("", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def get_statistics() -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="A statisztikák számítása még nincs bekötve.",
    )
