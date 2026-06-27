"""
Google Drive RAG — read files from Drive, store in ILLIP memory.

Supports public files (no auth) and private files (service account).
Simplest path: share any Google Doc/file → copy share URL → paste to ILLIP.

For private Drive sync:
  1. Google Cloud Console → Service Account → download JSON key
  2. Share your Drive folder with the service account email
  3. Add to .env:
       GDRIVE_SERVICE_ACCOUNT_JSON=./data/gdrive_key.json
       GDRIVE_FOLDER_ID=your_folder_id (from Drive URL)

Supported file types: Google Docs, plain text, PDF (text extraction), CSV
"""

import os
import asyncio
from typing import Optional
from app.utils import logger

_GDRIVE_API = "https://www.googleapis.com/drive/v3"
_GDOCS_API  = "https://docs.googleapis.com/v1"


def _service_account_path() -> Optional[str]:
    p = os.environ.get("GDRIVE_SERVICE_ACCOUNT_JSON", "").strip()
    return p if p and os.path.exists(p) else None


async def fetch_public_gdoc(url: str) -> Optional[str]:
    """
    Fetch text from a public Google Doc/Drive share URL.
    Works with any 'anyone with link can view' Google Doc.
    """
    import httpx, re

    # Extract file ID from various Google URLs
    patterns = [
        r"/document/d/([a-zA-Z0-9_-]+)",
        r"/file/d/([a-zA-Z0-9_-]+)",
        r"id=([a-zA-Z0-9_-]+)",
        r"/spreadsheets/d/([a-zA-Z0-9_-]+)",
    ]
    file_id = None
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            file_id = m.group(1)
            break

    if not file_id:
        logger.debug(f"Could not extract file ID from URL: {url}")
        return None

    # Try Google Docs export as plain text
    export_url = f"https://docs.google.com/document/d/{file_id}/export?format=txt"
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(export_url)
            if r.status_code == 200 and len(r.text) > 10:
                return r.text.strip()
    except Exception:
        pass

    # Fallback: Drive file download
    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(download_url)
            if r.status_code == 200 and len(r.text) > 10:
                return r.text.strip()
    except Exception as e:
        logger.debug(f"Drive download failed: {e}")

    return None


async def ingest_url(url: str, project_id: str = "default") -> dict:
    """
    Fetch a Google Drive/Doc URL and store its content in ILLIP memory.
    Returns {"success": bool, "chunks": int, "preview": str}
    """
    from app.services.memory_qdrant import store_memory

    text = await fetch_public_gdoc(url)
    if not text:
        return {"success": False, "chunks": 0, "preview": "Could not read file. Make sure it's shared publicly."}

    # Split into ~500 char chunks with overlap
    chunk_size = 500
    overlap    = 50
    chunks = []
    i = 0
    while i < len(text):
        chunks.append(text[i:i + chunk_size])
        i += chunk_size - overlap

    # Store each chunk as a memory
    stored = 0
    for chunk in chunks[:50]:  # cap at 50 chunks per file
        chunk = chunk.strip()
        if len(chunk) > 30:
            ok = await store_memory(chunk, metadata={"category": "document"}, project_id=project_id)
            if ok:
                stored += 1

    preview = text[:200].replace("\n", " ")
    return {"success": stored > 0, "chunks": stored, "preview": preview}


async def list_drive_files(folder_id: Optional[str] = None) -> list[dict]:
    """List files in a Drive folder using service account. Returns [] if not configured."""
    sa_path = _service_account_path()
    if not sa_path:
        return []

    folder_id = folder_id or os.environ.get("GDRIVE_FOLDER_ID", "").strip()
    if not folder_id:
        return []

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = service_account.Credentials.from_service_account_file(
            sa_path, scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
        loop = asyncio.get_event_loop()
        def _list():
            svc = build("drive", "v3", credentials=creds)
            return svc.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="files(id,name,mimeType,modifiedTime)",
                pageSize=50,
            ).execute().get("files", [])
        return await loop.run_in_executor(None, _list)
    except Exception as e:
        logger.debug(f"Drive list failed: {e}")
        return []
