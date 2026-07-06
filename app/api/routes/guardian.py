"""
Guardian endpoints — scan downloaded files for malicious signs.
Read-only static analysis; nothing is ever executed.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.file_guardian import scan_path
from app.utils import logger

router = APIRouter(prefix="/guardian", tags=["guardian"])


class ScanRequest(BaseModel):
    path: str = ""  # empty = newest file in Downloads


@router.post("/scan")
async def scan_route(req: ScanRequest):
    try:
        report = await scan_path(req.path)
        return {"report_md": report}
    except Exception as e:
        logger.error(f"guardian scan failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
