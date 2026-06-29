"""
Multi-device sync — export/import data/ as zip.

POST /api/sync/export  → returns zip of data/ (memory, history, tasks, images)
POST /api/sync/import  → accepts zip, restores data/
GET  /api/sync/status  → last export/import timestamps + git remote if configured
POST /api/sync/git-push → push data/ to configured git remote (SYNC_GIT_REMOTE in .env)
"""

import io
import os
import zipfile
import asyncio
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse

from app.utils import logger

router = APIRouter(prefix="/sync", tags=["sync"])

_DATA_DIR = Path("data")
_SYNC_STATE = Path("data/.sync_state.json")
_EXCLUDE = {".sync_state.json", ".DS_Store"}
# Skip generated/heavy dirs that don't need syncing
_SKIP_DIRS = {"__pycache__"}


def _read_sync_state() -> dict:
    try:
        import json
        return json.loads(_SYNC_STATE.read_text())
    except Exception:
        return {}


def _write_sync_state(state: dict) -> None:
    import json
    _DATA_DIR.mkdir(exist_ok=True)
    _SYNC_STATE.write_text(json.dumps(state, indent=2))


@router.get("/status")
async def sync_status():
    state = _read_sync_state()
    git_remote = os.getenv("SYNC_GIT_REMOTE", "")
    return {
        "last_export": state.get("last_export"),
        "last_import": state.get("last_import"),
        "last_git_push": state.get("last_git_push"),
        "git_remote_configured": bool(git_remote),
        "data_dir": str(_DATA_DIR.resolve()),
    }


@router.post("/export")
async def export_data():
    """Create zip of data/ and return as download."""
    if not _DATA_DIR.exists():
        raise HTTPException(404, "data/ directory not found")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(_DATA_DIR.rglob("*")):
            if not path.is_file():
                continue
            if path.name in _EXCLUDE:
                continue
            if any(part in _SKIP_DIRS for part in path.parts):
                continue
            # Skip large binary files > 50MB
            if path.stat().st_size > 50 * 1024 * 1024:
                logger.debug(f"Sync export: skipping large file {path}")
                continue
            arc_name = path.relative_to(_DATA_DIR.parent)
            zf.write(path, arc_name)

    buf.seek(0)
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"illip_sync_{now}.zip"

    state = _read_sync_state()
    state["last_export"] = datetime.now().isoformat()
    _write_sync_state(state)

    logger.info(f"Sync export: {buf.getbuffer().nbytes // 1024}KB")
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/import")
async def import_data(file: UploadFile = File(...)):
    """Restore data/ from uploaded zip. Merges — does not delete existing files."""
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(400, "Upload a .zip file created by /sync/export")

    content = await file.read()
    buf = io.BytesIO(content)

    try:
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
            # Safety: only extract into data/
            bad = [n for n in names if not n.startswith("data/") or ".." in n]
            if bad:
                raise HTTPException(400, f"Zip contains unexpected paths: {bad[:3]}")

            restored = 0
            for name in names:
                target = Path(name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(name))
                restored += 1
    except zipfile.BadZipFile:
        raise HTTPException(400, "Invalid or corrupted zip file")

    state = _read_sync_state()
    state["last_import"] = datetime.now().isoformat()
    _write_sync_state(state)

    logger.info(f"Sync import: {restored} files restored")
    return {"ok": True, "files_restored": restored}


@router.post("/git-push")
async def git_push():
    """
    Push data/ to git remote for cross-device sync.
    Set SYNC_GIT_REMOTE=https://github.com/you/illip-data.git in .env
    The remote must be a private repo you control.
    """
    remote = os.getenv("SYNC_GIT_REMOTE", "").strip()
    if not remote:
        raise HTTPException(400, "SYNC_GIT_REMOTE not set in .env")

    data_git = _DATA_DIR / ".git"

    try:
        if not data_git.exists():
            # Init git repo inside data/
            proc = await asyncio.create_subprocess_exec(
                "git", "init", str(_DATA_DIR),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            proc = await asyncio.create_subprocess_exec(
                "git", "-C", str(_DATA_DIR), "remote", "add", "origin", remote,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

        # Add all, commit, push
        await _run_git(_DATA_DIR, "add", ".")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        result = await _run_git(_DATA_DIR, "commit", "-m", f"sync: {ts}", "--allow-empty")
        push_out, push_err, push_rc = await _run_git_capture(_DATA_DIR, "push", "-u", "origin", "HEAD")

        if push_rc != 0:
            raise HTTPException(500, f"git push failed: {push_err}")

        state = _read_sync_state()
        state["last_git_push"] = datetime.now().isoformat()
        state["git_remote"] = remote
        _write_sync_state(state)

        return {"ok": True, "remote": remote, "message": push_out or "Pushed"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Git sync failed: {e}")


async def _run_git(cwd: Path, *args: str):
    proc = await asyncio.create_subprocess_exec(
        "git", "-C", str(cwd), *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()


async def _run_git_capture(cwd: Path, *args: str) -> tuple[str, str, int]:
    proc = await asyncio.create_subprocess_exec(
        "git", "-C", str(cwd), *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    return out.decode().strip(), err.decode().strip(), proc.returncode or 0
