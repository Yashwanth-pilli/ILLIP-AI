"""
Memory Ball — structured, named, typed long-term memory for ILLIP AI.

Works exactly like a coding agent's memory system:
- Every memory = a named .md file with frontmatter + body
- Types: user, project, feedback, reference, fact
- MEMORY_INDEX.md = searchable index of all memories
- Auto-extracts memorable facts from conversations via LLM
- Recalls by name, type, or semantic search

Storage: data/memory/structured/
  MEMORY_INDEX.md
  user/      ← who the user is, preferences, goals
  project/   ← what we're building, decisions, context
  feedback/  ← what worked, what didn't, corrections
  reference/ ← links, API keys hints, tool locations
  fact/      ← standalone facts worth remembering
"""

import asyncio
import json
import re
import time
from pathlib import Path
from typing import Optional
from app.utils import logger
from app.config import settings

_BASE = Path(__file__).resolve().parent.parent.parent / "data" / "memory" / "structured"
_INDEX = _BASE / "MEMORY_INDEX.md"
_TYPES = ("user", "project", "feedback", "reference", "fact")

_EXTRACT_PROMPT = """You are a memory extractor. Given a conversation, extract facts worth remembering long-term.

Only extract facts that are:
- Non-obvious personal preferences or goals
- Project decisions or constraints
- Corrections the user made
- Important references (tools, links, names)
- Facts about who the user is

Return JSON array. Each item: {"name": "kebab-slug", "type": "user|project|feedback|reference|fact", "description": "one line", "body": "2-4 sentences of what to remember and why"}

If nothing worth remembering, return [].

Conversation:
USER: {user_msg}
ASSISTANT: {assistant_msg}

JSON only, no markdown:"""


# ── Storage helpers ────────────────────────────────────────────────────────────

def _ensure_dirs():
    _BASE.mkdir(parents=True, exist_ok=True)
    for t in _TYPES:
        (_BASE / t).mkdir(exist_ok=True)
    if not _INDEX.exists():
        _INDEX.write_text("# ILLIP Memory Index\n\n", encoding="utf-8")


def _mem_path(name: str, mem_type: str) -> Path:
    safe = re.sub(r"[^\w\-]", "-", name.lower())[:60]
    return _BASE / mem_type / f"{safe}.md"


def _write_memory(name: str, mem_type: str, description: str, body: str) -> Path:
    _ensure_dirs()
    path = _mem_path(name, mem_type)
    content = (
        f"---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        f"metadata:\n"
        f"  type: {mem_type}\n"
        f"  created: {time.strftime('%Y-%m-%d')}\n"
        f"  updated: {time.strftime('%Y-%m-%d')}\n"
        f"---\n\n"
        f"{body.strip()}\n"
    )
    path.write_text(content, encoding="utf-8")
    _update_index(name, mem_type, description, path)
    return path


def _update_index(name: str, mem_type: str, description: str, path: Path):
    _ensure_dirs()
    text = _INDEX.read_text(encoding="utf-8") if _INDEX.exists() else "# ILLIP Memory Index\n\n"
    rel  = path.relative_to(_BASE)
    entry = f"- [{name}]({rel}) — {description}\n"
    # Replace existing entry or append
    pattern = re.compile(rf"^- \[{re.escape(name)}\].*\n", re.MULTILINE)
    if pattern.search(text):
        text = pattern.sub(entry, text)
    else:
        text = text.rstrip("\n") + "\n" + entry
    _INDEX.write_text(text, encoding="utf-8")


def _read_memory(name: str, mem_type: str) -> Optional[dict]:
    for t in ([mem_type] if mem_type else list(_TYPES)):
        path = _mem_path(name, t)
        if path.exists():
            raw  = path.read_text(encoding="utf-8")
            body = re.sub(r"^---.*?---\n", "", raw, flags=re.DOTALL).strip()
            m    = re.search(r"description:\s*(.+)", raw)
            desc = m.group(1).strip() if m else ""
            m2   = re.search(r"type:\s*(.+)", raw)
            typ  = m2.group(1).strip() if m2 else t
            return {"name": name, "type": typ, "description": desc, "body": body, "path": str(path)}
    return None


def _list_memories(mem_type: Optional[str] = None) -> list[dict]:
    _ensure_dirs()
    results = []
    types = [mem_type] if mem_type else list(_TYPES)
    for t in types:
        folder = _BASE / t
        for f in sorted(folder.glob("*.md")):
            raw  = f.read_text(encoding="utf-8")
            m    = re.search(r"name:\s*(.+)", raw)
            m2   = re.search(r"description:\s*(.+)", raw)
            name = m.group(1).strip() if m else f.stem
            desc = m2.group(1).strip() if m2 else ""
            results.append({"name": name, "type": t, "description": desc})
    return results


def _search_memories(query: str, mem_type: Optional[str] = None, limit: int = 5) -> list[dict]:
    """Keyword search across all memory files."""
    _ensure_dirs()
    q_words = query.lower().split()
    scored  = []
    types   = [mem_type] if mem_type else list(_TYPES)
    for t in types:
        for f in (_BASE / t).glob("*.md"):
            raw   = f.read_text(encoding="utf-8").lower()
            score = sum(raw.count(w) for w in q_words)
            if score > 0:
                body_raw = f.read_text(encoding="utf-8")
                body     = re.sub(r"^---.*?---\n", "", body_raw, flags=re.DOTALL).strip()
                m        = re.search(r"name:\s*(.+)", body_raw)
                m2       = re.search(r"description:\s*(.+)", body_raw)
                scored.append({
                    "name":        m.group(1).strip() if m else f.stem,
                    "type":        t,
                    "description": m2.group(1).strip() if m2 else "",
                    "body":        body[:500],
                    "score":       score,
                })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]


def _delete_memory(name: str, mem_type: Optional[str] = None) -> bool:
    for t in ([mem_type] if mem_type else list(_TYPES)):
        path = _mem_path(name, t)
        if path.exists():
            path.unlink()
            # Remove from index
            if _INDEX.exists():
                text = _INDEX.read_text(encoding="utf-8")
                text = re.sub(rf"^- \[{re.escape(name)}\].*\n", "", text, flags=re.MULTILINE)
                _INDEX.write_text(text, encoding="utf-8")
            return True
    return False


# ── LLM auto-extraction ────────────────────────────────────────────────────────

async def auto_extract(user_msg: str, assistant_msg: str, project_id: str = "default") -> int:
    """
    After a conversation turn, extract memorable facts via LLM.
    Runs async in background — never blocks chat response.
    Returns count of memories saved.
    """
    # Skip trivial exchanges
    if len(user_msg) < 20 or len(assistant_msg) < 30:
        return 0
    # Skip purely technical/code exchanges
    if user_msg.strip().startswith(("/", "!")):
        return 0

    try:
        from app.providers import get_provider
        from app.core import Message

        provider  = await get_provider()
        prompt    = _EXTRACT_PROMPT.format(
            user_msg=user_msg[:1000],
            assistant_msg=assistant_msg[:1000],
        )
        messages  = [Message(role="user", content=prompt, timestamp="")]
        raw       = await provider.generate_response(messages, temperature=0.2, max_tokens=800)

        # Parse JSON
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"```[a-z]*\n?", "", raw).strip()
        items = json.loads(raw)
        if not isinstance(items, list):
            return 0

        saved = 0
        for item in items[:5]:  # cap at 5 per turn
            name  = item.get("name", "").strip()
            typ   = item.get("type", "fact").strip()
            desc  = item.get("description", "").strip()
            body  = item.get("body", "").strip()
            if name and typ in _TYPES and body:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, _write_memory, name, typ, desc, body)
                saved += 1

        if saved:
            logger.info(f"Memory Ball: extracted {saved} memories from conversation")
        return saved

    except Exception as e:
        logger.debug(f"Memory Ball auto-extract failed (non-critical): {e}")
        return 0


# ── Public API ─────────────────────────────────────────────────────────────────

def save_memory(name: str, mem_type: str, description: str, body: str) -> bool:
    """Explicitly save a named memory. Returns True on success."""
    if mem_type not in _TYPES:
        mem_type = "fact"
    try:
        _write_memory(name, mem_type, description, body)
        return True
    except Exception as e:
        logger.error(f"Memory Ball save failed: {e}")
        return False


def get_memory(name: str, mem_type: Optional[str] = None) -> Optional[dict]:
    return _read_memory(name, mem_type or "")


def list_all(mem_type: Optional[str] = None) -> list[dict]:
    return _list_memories(mem_type)


def search(query: str, mem_type: Optional[str] = None, limit: int = 5) -> list[dict]:
    return _search_memories(query, mem_type, limit)


def delete(name: str, mem_type: Optional[str] = None) -> bool:
    return _delete_memory(name, mem_type)


def format_for_prompt(memories: list[dict]) -> str:
    """Format structured memories as LLM context block."""
    if not memories:
        return ""
    lines = ["**What I know about you and this project:**"]
    for m in memories:
        desc = m.get("description") or m.get("body", "")[:100]
        lines.append(f"- [{m['type']}] {m['name']}: {desc}")
    return "\n".join(lines)


def get_index_summary() -> str:
    """Return MEMORY_INDEX.md content for display."""
    _ensure_dirs()
    if _INDEX.exists():
        return _INDEX.read_text(encoding="utf-8")
    return "No memories yet."
