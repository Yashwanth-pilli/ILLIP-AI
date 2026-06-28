"""
Skills / plugin endpoints.
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.skills.registry import get_registry

router = APIRouter(prefix="/skills", tags=["skills"])


class RunRequest(BaseModel):
    args: Dict[str, Any] = {}


class InstallRequest(BaseModel):
    url: str                          # raw .py URL, GitHub repo URL, or pypi:package-name
    persist: bool = False             # if True, save fetched file to data/connectors/ for restarts


class CleanupRequest(BaseModel):
    temp_path: str


@router.get("/")
async def list_skills():
    """List all registered skills."""
    return {"skills": get_registry().list_skills(), "count": len(get_registry().list_skills())}


@router.get("/specs")
async def list_tool_specs():
    """Return full Ollama-compatible tool specs for all skills."""
    return {"tools": get_registry().to_tool_specs()}


@router.post("/install")
async def install_skill(req: InstallRequest):
    """
    Install a skill or connector from any URL without downloading to disk.

    - Raw .py URL  → fetched into memory, zero disk write
    - GitHub repo  → cloned to temp dir, registered, cleanup prompt returned
    - pypi:name    → pip install then auto-register

    Response includes `cleanup_needed` and `prompt` asking user to keep or delete temp folder.
    """
    from app.skills.installer import install_from_url, save_to_user_connectors
    import httpx

    result = await install_from_url(req.url)

    # If user wants to persist a URL-fetched file so it survives restarts
    if result.installed and req.persist and not result.cleanup_needed:
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
                r = await c.get(req.url)
                saved = save_to_user_connectors(req.url, r.text)
                result.prompt += f" Saved to {saved} for auto-load on restart."
        except Exception as e:
            result.prompt += f" (Persist failed: {e})"

    return result.to_dict()


@router.post("/install/cleanup")
async def cleanup_install(req: CleanupRequest):
    """Delete downloaded temp folder after user chooses to free disk space."""
    from app.skills.installer import cleanup_temp
    ok = await cleanup_temp(req.temp_path)
    return {"deleted": ok, "path": req.temp_path}


@router.post("/install/keep")
async def keep_install(req: CleanupRequest):
    """
    User chose to keep the downloaded folder.
    Move it to data/connectors/ so ILLIP loads it on restart.
    """
    import shutil
    from pathlib import Path
    from app.config import settings

    src = Path(req.temp_path)
    if not src.exists():
        raise HTTPException(status_code=404, detail="Temp path not found")

    dest_dir = settings.get_data_path() / "connectors" / src.name
    try:
        shutil.move(str(src), str(dest_dir))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Move failed: {e}")

    return {"kept": True, "moved_to": str(dest_dir), "note": "Will auto-load on next restart"}


@router.post("/{name}/run")
async def run_skill(name: str, request: RunRequest):
    """Run a named skill with the given args dict."""
    skill = get_registry().get(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found.")
    result = await get_registry().run(name, request.args)
    return {"skill": name, "result": result}
