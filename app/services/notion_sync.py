"""
Notion memory sync — saves ILLIP memories to a Notion database.

Setup:
  1. Go to notion.so/my-integrations → New integration → copy token
  2. Create a Notion database with columns: Text (title), Project, Category, Date
  3. Share that database with your integration
  4. Copy database ID from URL (32-char hex after last slash, before ?)
  5. Add to .env:
       NOTION_API_KEY=secret_xxx
       NOTION_DB_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
"""

import os
import asyncio
from typing import Optional
from app.utils import logger

_NOTION_URL = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"

_enabled: Optional[bool] = None


def _creds() -> tuple[str, str]:
    return (
        os.environ.get("NOTION_API_KEY", "").strip(),
        os.environ.get("NOTION_DB_ID", "").strip(),
    )


def is_enabled() -> bool:
    global _enabled
    if _enabled is None:
        key, db = _creds()
        _enabled = bool(key and db)
    return _enabled


async def sync_memory(text: str, project_id: str = "default", category: str = "chat") -> bool:
    """Push one memory entry to Notion database. Fire-and-forget safe."""
    if not is_enabled():
        return False
    key, db_id = _creds()
    try:
        import httpx
        headers = {
            "Authorization": f"Bearer {key}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
        }
        payload = {
            "parent": {"database_id": db_id},
            "properties": {
                "Text": {"title": [{"text": {"content": text[:2000]}}]},
                "Project": {"rich_text": [{"text": {"content": project_id}}]},
                "Category": {"rich_text": [{"text": {"content": category}}]},
            },
        }
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(f"{_NOTION_URL}/pages", headers=headers, json=payload)
            if r.status_code in (200, 201):
                return True
            logger.debug(f"Notion sync failed: {r.status_code} {r.text[:200]}")
            return False
    except Exception as e:
        logger.debug(f"Notion sync error: {e}")
        return False


async def search_notion(query: str, project_id: str = "default", limit: int = 5) -> list[dict]:
    """Search Notion database for relevant memories."""
    if not is_enabled():
        return []
    key, db_id = _creds()
    try:
        import httpx
        headers = {
            "Authorization": f"Bearer {key}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
        }
        payload = {
            "filter": {
                "and": [
                    {"property": "Project", "rich_text": {"contains": project_id}},
                    {"property": "Text", "title": {"contains": query[:100]}},
                ]
            },
            "page_size": limit,
        }
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(
                f"{_NOTION_URL}/databases/{db_id}/query",
                headers=headers, json=payload,
            )
            if r.status_code != 200:
                return []
            results = r.json().get("results", [])
            memories = []
            for page in results:
                props = page.get("properties", {})
                title_parts = props.get("Text", {}).get("title", [])
                text = "".join(p.get("plain_text", "") for p in title_parts)
                if text:
                    memories.append({"text": text, "score": 0.7, "source": "notion"})
            return memories
    except Exception as e:
        logger.debug(f"Notion search error: {e}")
        return []
