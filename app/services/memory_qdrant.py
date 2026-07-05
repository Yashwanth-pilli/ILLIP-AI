"""
ILLIP vector memory — semantic long-term memory using qdrant-client.

Storage: QdrantClient with local file path (no Docker, no server).
         Falls back to SQLite FTS5 when Qdrant unavailable.
Embeddings: Ollama nomic-embed-text (local, best quality).
            Falls back to keyword similarity when Ollama offline.

Works on laptop (full semantic) and Render cloud (keyword fallback).
Remembers every conversation across restarts.
"""

import asyncio
import hashlib
import re
import sqlite3
import time
from pathlib import Path
from typing import Optional

from app.utils import logger

# ── Paths (absolute so they work regardless of CWD) ────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DATA_DIR     = _PROJECT_ROOT / "data"
_QDRANT_PATH  = _DATA_DIR / "qdrant"
_FTS_DB       = _DATA_DIR / "memory_fts.db"

# ── Embedding config ────────────────────────────────────────────────────────
import os as _os
_OLLAMA_URL  = _os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_EMBED_MODEL = _os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
_VECTOR_SIZE = 768   # nomic-embed-text output

# ── State ───────────────────────────────────────────────────────────────────
_qdrant_client = None
_qdrant_ok     = False
_ollama_embed_ok: Optional[bool] = None



# ═══════════════════════════════════════════════════════════════════════════
# SQLite FTS5 — always-on fallback memory (no deps beyond stdlib)
# ═══════════════════════════════════════════════════════════════════════════

def _fts_conn() -> sqlite3.Connection:
    _FTS_DB.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"FTS connect: {_FTS_DB}")
    conn = sqlite3.connect(str(_FTS_DB))
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS memories
        USING fts5(text, project_id, category, ts)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories_meta (
            rowid   INTEGER PRIMARY KEY,
            ts_unix REAL
        )
    """)
    conn.commit()
    return conn


def _fts_store(text: str, project_id: str, category: str = "chat") -> None:
    try:
        conn = _fts_conn()
        ts   = str(time.time())
        cur  = conn.execute(
            "INSERT INTO memories(text, project_id, category, ts) VALUES (?,?,?,?)",
            (text, project_id, category, ts),
        )
        # OR REPLACE: FTS5 reuses rowids after deletes; stale meta rows
        # from a partial clear must never block new memory writes
        conn.execute(
            "INSERT OR REPLACE INTO memories_meta(rowid, ts_unix) VALUES (?,?)",
            (cur.lastrowid, float(ts)),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"FTS store failed: {e}")


def _fts_query_syntax(query: str) -> str:
    """
    Build a safe FTS5 MATCH expression from free-form user text.
    FTS5's query syntax treats ?, -, (, ), ", *, : as operators — a plain
    natural-language question like "What's the plan?" is a syntax error if
    passed raw. Extract word tokens and OR-quote them so any punctuation in
    the original text is inert.
    """
    words = re.findall(r"[A-Za-z0-9]+", query)
    if not words:
        return ""
    return " OR ".join(f'"{w}"' for w in words[:20])


def _fts_search(query: str, project_id: str, top_k: int = 5) -> list[dict]:
    match_expr = _fts_query_syntax(query)
    if not match_expr:
        return []
    try:
        conn = _fts_conn()
        # FTS5 MATCH search — safe, no injection (parameterized); match_expr
        # is built from sanitized word tokens only, see _fts_query_syntax.
        rows = conn.execute(
            """
            SELECT text, rank
            FROM memories
            WHERE project_id = ? AND memories MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (project_id, match_expr, top_k),
        ).fetchall()
        conn.close()
        return [{"text": r[0], "score": max(0.0, 1.0 + r[1] / 10)} for r in rows]
    except Exception as e:
        logger.error(f"FTS search failed: {e}")
        return []


def _fts_recent(project_id: str, limit: int = 5) -> list[dict]:
    """Return most recent memories (fallback when query has no FTS match)."""
    try:
        conn = _fts_conn()
        rows = conn.execute(
            """
            SELECT m.text FROM memories m
            JOIN memories_meta mm ON m.rowid = mm.rowid
            WHERE m.project_id = ?
            ORDER BY mm.ts_unix DESC
            LIMIT ?
            """,
            (project_id, limit),
        ).fetchall()
        conn.close()
        return [{"text": r[0], "score": 0.5} for r in rows]
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════════════
# Qdrant — semantic vector memory (best quality)
# ═══════════════════════════════════════════════════════════════════════════

def _collection(project_id: str) -> str:
    safe = project_id.replace("-", "_").replace(" ", "_")[:40]
    return f"illip_{safe}"


def _init_qdrant() -> bool:
    global _qdrant_client, _qdrant_ok
    if _qdrant_ok and _qdrant_client is not None:
        return True
    try:
        from qdrant_client import QdrantClient
        _QDRANT_PATH.mkdir(parents=True, exist_ok=True)
        _qdrant_client = QdrantClient(path=str(_QDRANT_PATH))
        _qdrant_ok = True
        logger.info(f"Qdrant: local file storage at {_QDRANT_PATH}")
        return True
    except Exception as e:
        logger.debug(f"Qdrant init failed: {e}")
        _qdrant_ok = False
        return False


def _ensure_collection(col: str) -> bool:
    try:
        from qdrant_client.models import Distance, VectorParams
        existing = [c.name for c in _qdrant_client.get_collections().collections]
        if col not in existing:
            _qdrant_client.create_collection(
                collection_name=col,
                vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
            )
        return True
    except Exception as e:
        logger.debug(f"Qdrant collection error: {e}")
        return False


async def _embed(text: str) -> Optional[list[float]]:
    """Get embedding from Ollama nomic-embed-text. Returns None if unavailable."""
    global _ollama_embed_ok
    if _ollama_embed_ok is False:
        return None
    try:
        import httpx
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(
                f"{_OLLAMA_URL}/api/embed",
                json={"model": _EMBED_MODEL, "input": text},
            )
            if r.status_code == 200:
                data = r.json()
                emb  = data.get("embeddings", [])
                if emb:
                    _ollama_embed_ok = True
                    return emb[0]
        _ollama_embed_ok = False
        return None
    except Exception:
        _ollama_embed_ok = False
        return None


def _qdrant_store_sync(text: str, project_id: str, category: str, embedding: list[float]) -> bool:
    try:
        from qdrant_client.models import PointStruct
        col      = _collection(project_id)
        if not _ensure_collection(col):
            return False
        point_id = int(hashlib.md5(f"{project_id}:{text}:{time.time()}".encode()).hexdigest()[:8], 16)
        _qdrant_client.upsert(
            collection_name=col,
            points=[PointStruct(
                id=point_id,
                vector=embedding,
                payload={"text": text, "project_id": project_id, "category": category, "ts": time.time()},
            )],
        )
        return True
    except Exception as e:
        logger.debug(f"Qdrant store failed: {e}")
        return False


def _qdrant_search_sync(query_vec: list[float], project_id: str, top_k: int, threshold: float) -> list[dict]:
    try:
        col     = _collection(project_id)
        results = _qdrant_client.search(
            collection_name=col,
            query_vector=query_vec,
            limit=top_k,
            score_threshold=threshold,
            with_payload=True,
        )
        return [{"text": r.payload.get("text", ""), "score": r.score} for r in results]
    except Exception as e:
        logger.debug(f"Qdrant search failed: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════
# Public API — used by chat.py
# ═══════════════════════════════════════════════════════════════════════════

async def store_memory(
    text: str,
    metadata: dict = None,
    project_id: str = "default",
) -> bool:
    """
    Store a memory. Always writes to SQLite FTS5.
    Also writes to Qdrant with semantic embedding when available.
    """
    if not text or not text.strip():
        return False

    category = (metadata or {}).get("category", "chat")

    # 1. Always store in SQLite (synchronous, never fails)
    _fts_store(text, project_id, category)

    # 2. Try Qdrant semantic storage
    if _init_qdrant():
        loop    = asyncio.get_event_loop()
        embedding = await _embed(text)
        if embedding:
            await loop.run_in_executor(
                None, _qdrant_store_sync, text, project_id, category, embedding
            )

    # 3. Fire-and-forget Notion sync (if NOTION_API_KEY + NOTION_DB_ID set)
    try:
        from app.services.notion_sync import sync_memory as _notion_sync, is_enabled as _notion_ok
        if _notion_ok():
            asyncio.create_task(_notion_sync(text, project_id, category))
    except Exception:
        pass

    return True


async def retrieve_memory(
    query: str,
    top_k: int = 5,
    score_threshold: float = 0.60,
    project_id: str = "default",
) -> list[dict]:
    """
    Retrieve relevant memories.
    Priority: Qdrant semantic → SQLite FTS5 → recent memories.
    """
    if not query or not query.strip():
        return []

    # 1. Try Qdrant semantic search (best quality)
    if _init_qdrant():
        loop      = asyncio.get_event_loop()
        embedding = await _embed(query)
        if embedding:
            results = await loop.run_in_executor(
                None, _qdrant_search_sync, embedding, project_id, top_k, score_threshold
            )
            if results:
                return results

    # 2. SQLite FTS5 keyword search
    loop    = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, _fts_search, query, project_id, top_k)
    if results:
        return results

    # 3. Recent memories as final fallback
    return await loop.run_in_executor(None, _fts_recent, project_id, top_k)


def format_memories_for_prompt(memories: list[dict]) -> str:
    """Format retrieved memories as a concise LLM context block."""
    if not memories:
        return ""
    seen  = set()
    lines = ["**What I remember:**"]
    for m in memories:
        text = m["text"].strip()
        if text not in seen and len(text) > 10:
            seen.add(text)
            lines.append(f"- {text[:300]}")
    return "\n".join(lines) if len(lines) > 1 else ""


def list_memories(project_id: str = "default", limit: int = 200, offset: int = 0,
                  search: str = "") -> list[dict]:
    """Browse stored memories (FTS is source of truth — every write lands there)."""
    try:
        conn = _fts_conn()
        if search:
            match_expr = _fts_query_syntax(search)
            rows = conn.execute(
                """
                SELECT m.rowid, m.text, m.category, m.ts FROM memories m
                WHERE m.project_id = ? AND memories MATCH ?
                ORDER BY m.rowid DESC LIMIT ? OFFSET ?
                """,
                (project_id, match_expr, limit, offset),
            ).fetchall() if match_expr else []
        else:
            rows = conn.execute(
                """
                SELECT m.rowid, m.text, m.category, m.ts FROM memories m
                WHERE m.project_id = ?
                ORDER BY m.rowid DESC LIMIT ? OFFSET ?
                """,
                (project_id, limit, offset),
            ).fetchall()
        conn.close()
        return [{"id": r[0], "text": r[1], "category": r[2], "ts": float(r[3] or 0)} for r in rows]
    except Exception as e:
        logger.error(f"list_memories failed: {e}")
        return []


def delete_memory_entry(rowid: int, project_id: str = "default") -> bool:
    """Delete one memory from FTS + matching text from Qdrant."""
    text = None
    try:
        conn = _fts_conn()
        row = conn.execute(
            "SELECT text FROM memories WHERE rowid = ? AND project_id = ?",
            (rowid, project_id),
        ).fetchone()
        if not row:
            conn.close()
            return False
        text = row[0]
        conn.execute("DELETE FROM memories WHERE rowid = ?", (rowid,))
        conn.execute("DELETE FROM memories_meta WHERE rowid = ?", (rowid,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"delete_memory_entry failed: {e}")
        return False

    # Purge same text from Qdrant (point ids aren't recomputable — filter on payload)
    if text and _init_qdrant():
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue, FilterSelector
            _qdrant_client.delete(
                collection_name=_collection(project_id),
                points_selector=FilterSelector(filter=Filter(must=[
                    FieldCondition(key="text", match=MatchValue(value=text)),
                ])),
            )
        except Exception as e:
            logger.debug(f"Qdrant delete failed: {e}")
    return True


def clear_project_memories(project_id: str = "default") -> int:
    """Wipe all memories for a project (FTS rows + Qdrant collection). Returns rows removed."""
    removed = 0
    try:
        conn = _fts_conn()
        rowids = [r[0] for r in conn.execute(
            "SELECT rowid FROM memories WHERE project_id = ?", (project_id,)
        ).fetchall()]
        conn.execute("DELETE FROM memories WHERE project_id = ?", (project_id,))
        if rowids:
            conn.executemany("DELETE FROM memories_meta WHERE rowid = ?", [(r,) for r in rowids])
        conn.commit()
        conn.close()
        removed = len(rowids)
    except Exception as e:
        logger.error(f"clear_project_memories failed: {e}")
    if _init_qdrant():
        try:
            _qdrant_client.delete_collection(_collection(project_id))
        except Exception as e:
            logger.debug(f"Qdrant collection drop failed: {e}")
    return removed


async def memory_stats(project_id: str = "default") -> dict:
    """Return memory counts for this project."""
    fts_count = 0
    qdrant_count = 0
    try:
        conn = _fts_conn()
        fts_count = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE project_id=?", (project_id,)
        ).fetchone()[0]
        conn.close()
    except Exception:
        pass
    if _qdrant_ok and _qdrant_client:
        try:
            col = _collection(project_id)
            info = _qdrant_client.get_collection(col)
            qdrant_count = info.points_count or 0
        except Exception:
            pass
    return {
        "fts_memories":    fts_count,
        "vector_memories": qdrant_count,
        "semantic_active": _qdrant_ok and _ollama_embed_ok is True,
        "embed_model":     _EMBED_MODEL if _ollama_embed_ok else None,
    }
