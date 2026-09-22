"""Controller for the future download and preprocessing workflow."""

from fastapi import APIRouter, HTTPException, status


router = APIRouter(prefix="/preprocessing", tags=["preprocessing"])


@router.post("", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def start_preprocessing() -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="A letöltés és előfeldolgozás még nincs bekötve.",
    )
