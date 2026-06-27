"""
ILLIP Knowledge Graph — entities + relationships extracted from conversations.

Storage: SQLite (stdlib, no new deps).
  kg_nodes: id, name, type, description, created_at
  kg_edges: from_id, to_id, relation, weight, created_at

Entity types : person, project, tool, concept, file, place, org, event
Relation types: uses, created_by, part_of, related_to, depends_on,
                knows, works_on, located_in, has, is_a

Auto-extracts triples from every conversation turn via LLM.
Query: neighbors of a node, shortest path, entity search, full graph export.
"""

import json
import re
import sqlite3
import time
import uuid
import asyncio
from pathlib import Path
from typing import Optional
from app.utils import logger

_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "knowledge_graph.db"

_EXTRACT_PROMPT = """Extract knowledge graph triples from this conversation.
Return JSON array of triples: [{{"from": "entity", "from_type": "type", "relation": "relation", "to": "entity", "to_type": "type"}}]

Entity types: person, project, tool, concept, file, place, org, event
Relation types: uses, created_by, part_of, related_to, depends_on, knows, works_on, located_in, has, is_a, built_with, runs_on

Rules:
- Only extract clear factual relationships
- Entity names: proper nouns, specific tools/projects (not generic words)
- If nothing clear, return []
- Max 5 triples

Conversation:
USER: {user_msg}
ASSISTANT: {assistant_msg}

JSON only:"""


# ── DB helpers ──────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kg_nodes (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            name_lower  TEXT NOT NULL,
            type        TEXT NOT NULL DEFAULT 'concept',
            description TEXT DEFAULT '',
            created_at  REAL NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_kg_nodes_name ON kg_nodes(name_lower)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kg_edges (
            id         TEXT PRIMARY KEY,
            from_id    TEXT NOT NULL,
            to_id      TEXT NOT NULL,
            relation   TEXT NOT NULL,
            weight     REAL NOT NULL DEFAULT 1.0,
            created_at REAL NOT NULL,
            FOREIGN KEY(from_id) REFERENCES kg_nodes(id),
            FOREIGN KEY(to_id)   REFERENCES kg_nodes(id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_kg_edges_from ON kg_edges(from_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_kg_edges_to   ON kg_edges(to_id)")
    conn.commit()
    return conn


# ── Core CRUD ───────────────────────────────────────────────────────────────────

def _upsert_node(conn: sqlite3.Connection, name: str, node_type: str,
                 description: str = "") -> str:
    """Get or create node. Returns node id."""
    name = name.strip()[:120]
    name_lower = name.lower()
    row = conn.execute(
        "SELECT id FROM kg_nodes WHERE name_lower=?", (name_lower,)
    ).fetchone()
    if row:
        return row["id"]
    nid = str(uuid.uuid4())[:8]
    conn.execute(
        "INSERT INTO kg_nodes(id,name,name_lower,type,description,created_at) VALUES(?,?,?,?,?,?)",
        (nid, name, name_lower, node_type, description, time.time()),
    )
    return nid


def _upsert_edge(conn: sqlite3.Connection, from_id: str, to_id: str,
                 relation: str, weight: float = 1.0) -> None:
    existing = conn.execute(
        "SELECT id, weight FROM kg_edges WHERE from_id=? AND to_id=? AND relation=?",
        (from_id, to_id, relation),
    ).fetchone()
    if existing:
        # Strengthen existing edge
        conn.execute(
            "UPDATE kg_edges SET weight=? WHERE id=?",
            (min(existing["weight"] + 0.1, 5.0), existing["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO kg_edges(id,from_id,to_id,relation,weight,created_at) VALUES(?,?,?,?,?,?)",
            (str(uuid.uuid4())[:8], from_id, to_id, relation, weight, time.time()),
        )


# ── Public write API ─────────────────────────────────────────────────────────────

def add_triple(from_name: str, from_type: str, relation: str,
               to_name: str, to_type: str) -> bool:
    """Add one knowledge triple. Idempotent."""
    try:
        conn = _conn()
        from_id = _upsert_node(conn, from_name, from_type)
        to_id   = _upsert_node(conn, to_name,   to_type)
        _upsert_edge(conn, from_id, to_id, relation.lower().replace(" ", "_"))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.debug(f"KG add_triple failed: {e}")
        return False


def add_triples(triples: list[dict]) -> int:
    """Batch add triples. Returns count stored."""
    if not triples:
        return 0
    try:
        conn = _conn()
        saved = 0
        for t in triples:
            try:
                fn = t.get("from", "").strip()
                ft = t.get("from_type", "concept").strip()
                r  = t.get("relation", "related_to").strip()
                tn = t.get("to", "").strip()
                tt = t.get("to_type", "concept").strip()
                if fn and tn and r:
                    fid = _upsert_node(conn, fn, ft)
                    tid = _upsert_node(conn, tn, tt)
                    _upsert_edge(conn, fid, tid, r)
                    saved += 1
            except Exception:
                continue
        conn.commit()
        conn.close()
        return saved
    except Exception as e:
        logger.debug(f"KG batch failed: {e}")
        return 0


# ── Query API ────────────────────────────────────────────────────────────────────

def get_neighbors(name: str, depth: int = 2) -> dict:
    """
    Return all nodes within `depth` hops of `name`.
    Returns {"center": node, "nodes": [...], "edges": [...]}
    """
    try:
        conn  = _conn()
        lower = name.strip().lower()
        root  = conn.execute(
            "SELECT * FROM kg_nodes WHERE name_lower=?", (lower,)
        ).fetchone()
        if not root:
            # fuzzy: contains
            root = conn.execute(
                "SELECT * FROM kg_nodes WHERE name_lower LIKE ? LIMIT 1",
                (f"%{lower}%",),
            ).fetchone()
        if not root:
            conn.close()
            return {"center": None, "nodes": [], "edges": []}

        visited_ids = {root["id"]}
        frontier    = {root["id"]}
        all_edges   = []

        for _ in range(depth):
            if not frontier:
                break
            placeholders = ",".join("?" * len(frontier))
            rows = conn.execute(
                f"SELECT * FROM kg_edges WHERE from_id IN ({placeholders}) "
                f"OR to_id IN ({placeholders})",
                list(frontier) + list(frontier),
            ).fetchall()
            new_frontier = set()
            for e in rows:
                all_edges.append(dict(e))
                for nid in (e["from_id"], e["to_id"]):
                    if nid not in visited_ids:
                        visited_ids.add(nid)
                        new_frontier.add(nid)
            frontier = new_frontier

        # Fetch all visited nodes
        placeholders = ",".join("?" * len(visited_ids))
        nodes = conn.execute(
            f"SELECT * FROM kg_nodes WHERE id IN ({placeholders})",
            list(visited_ids),
        ).fetchall()
        conn.close()

        return {
            "center": dict(root),
            "nodes":  [dict(n) for n in nodes],
            "edges":  all_edges,
        }
    except Exception as e:
        logger.debug(f"KG get_neighbors failed: {e}")
        return {"center": None, "nodes": [], "edges": []}


def search_nodes(query: str, limit: int = 10) -> list[dict]:
    try:
        conn  = _conn()
        lower = query.strip().lower()
        rows  = conn.execute(
            "SELECT * FROM kg_nodes WHERE name_lower LIKE ? ORDER BY created_at DESC LIMIT ?",
            (f"%{lower}%", limit),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.debug(f"KG search failed: {e}")
        return []


def stats() -> dict:
    try:
        conn = _conn()
        nc   = conn.execute("SELECT COUNT(*) FROM kg_nodes").fetchone()[0]
        ec   = conn.execute("SELECT COUNT(*) FROM kg_edges").fetchone()[0]
        conn.close()
        return {"nodes": nc, "edges": ec}
    except Exception:
        return {"nodes": 0, "edges": 0}


def export_json() -> dict:
    """Full graph export for visualization (D3, Cytoscape, etc.)"""
    try:
        conn  = _conn()
        nodes = [dict(r) for r in conn.execute("SELECT * FROM kg_nodes").fetchall()]
        edges = [dict(r) for r in conn.execute("SELECT * FROM kg_edges").fetchall()]
        conn.close()
        return {"nodes": nodes, "edges": edges}
    except Exception:
        return {"nodes": [], "edges": []}


def format_for_prompt(name: str, depth: int = 1) -> str:
    """Format KG neighborhood as LLM context."""
    result = get_neighbors(name, depth=depth)
    if not result["center"] or not result["edges"]:
        return ""
    node_map = {n["id"]: n["name"] for n in result["nodes"]}
    lines    = [f"**Knowledge graph for '{result['center']['name']}':**"]
    for e in result["edges"][:12]:
        fn = node_map.get(e["from_id"], e["from_id"])
        tn = node_map.get(e["to_id"],   e["to_id"])
        lines.append(f"- {fn} —[{e['relation']}]→ {tn}")
    return "\n".join(lines)


# ── LLM auto-extraction ──────────────────────────────────────────────────────────

async def auto_extract(user_msg: str, assistant_msg: str) -> int:
    """Extract triples from conversation turn. Runs in background."""
    if len(user_msg) < 15:
        return 0
    try:
        from app.providers import get_provider
        from app.core import Message

        provider = await get_provider()
        prompt   = _EXTRACT_PROMPT.format(
            user_msg=user_msg[:800],
            assistant_msg=assistant_msg[:800],
        )
        msgs = [Message(role="user", content=prompt, timestamp="")]
        raw  = await provider.generate_response(msgs, temperature=0.1, max_tokens=400)

        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"```[a-z]*\n?", "", raw).strip()

        triples = json.loads(raw)
        if not isinstance(triples, list):
            return 0

        saved = await asyncio.get_event_loop().run_in_executor(None, add_triples, triples)
        if saved:
            logger.info(f"KG: extracted {saved} triples")
        return saved
    except Exception as e:
        logger.debug(f"KG auto_extract (non-critical): {e}")
        return 0
