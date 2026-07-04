"""
Project service — scopes memory, history, and tasks to named projects.

Structure on disk:
  data/projects/{project_id}/
    meta.json        — name, description, created_at
    memory.json      — key-value memory entries
    history.json     — chat history for this project
"""

import json
import os
import uuid
import re
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional
from app.config import settings
from app.utils import logger

# Guards read-modify-write of the same JSON file against overlapping writers
# (background LLM tasks can append while the next request is mid-write).
# ponytail: one process-wide lock, fine for a local single-user app.
_write_lock = threading.Lock()

DEFAULT_PROJECT = "default"


def _projects_root() -> Path:
    p = settings.get_data_path() / "projects"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _project_dir(project_id: str) -> Path:
    p = _projects_root() / _safe_id(project_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _safe_id(project_id: str) -> str:
    """Sanitize project_id for use as directory name."""
    return re.sub(r"[^\w\-]", "_", project_id.strip().lower())[:64]


def _meta_path(project_id: str) -> Path:
    return _project_dir(project_id) / "meta.json"


def _memory_path(project_id: str) -> Path:
    return _project_dir(project_id) / "memory.json"


def _history_path(project_id: str) -> Path:
    return _project_dir(project_id) / "history.json"


def _read_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def _write_json(path: Path, data) -> None:
    """Atomic write: dump to a temp file, then os.replace. An interrupted or
    overlapping write can never truncate the real file — the worst case is the
    temp file is left behind, never a corrupt/empty history.json."""
    payload = json.dumps(data, indent=2, ensure_ascii=False)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)  # atomic on Windows + POSIX


# ── Project CRUD ──────────────────────────────────────────────────────────────

def create_project(name: str, description: str = "") -> dict:
    project_id = re.sub(r"\s+", "-", name.strip().lower())
    project_id = re.sub(r"[^\w\-]", "", project_id)[:48] or str(uuid.uuid4())[:8]

    if _meta_path(project_id).exists():
        raise ValueError(f"Project '{project_id}' already exists.")

    meta = {
        "id": project_id,
        "name": name,
        "description": description,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    _write_json(_meta_path(project_id), meta)
    logger.info(f"Project created: {project_id}")
    return meta


def get_project(project_id: str) -> Optional[dict]:
    path = _meta_path(project_id)
    if not path.exists():
        return None
    return _read_json(path, None)


def list_projects() -> list[dict]:
    root = _projects_root()
    projects = []
    for d in sorted(root.iterdir()):
        if d.is_dir():
            meta = _read_json(d / "meta.json", None)
            if meta:
                projects.append(meta)
    return projects


def ensure_default_project() -> dict:
    if not _meta_path(DEFAULT_PROJECT).exists():
        return create_project("Default", "Default project for all conversations")
    return get_project(DEFAULT_PROJECT)


# ── Per-project memory (key-value) ────────────────────────────────────────────

def memory_store(project_id: str, key: str, value: str, category: str = "general") -> dict:
    path = _memory_path(project_id)
    entry_id = str(uuid.uuid4())
    entry = {
        "id": entry_id,
        "key": key,
        "value": value,
        "category": category,
        "project_id": project_id,
        "created_at": datetime.now().isoformat(),
    }
    with _write_lock:
        entries = _read_json(path, {})
        entries[entry_id] = entry
        _write_json(path, entries)
    return entry


def memory_get_all(project_id: str, category: Optional[str] = None) -> list[dict]:
    path = _memory_path(project_id)
    entries = _read_json(path, {})
    result = list(entries.values())
    if category:
        result = [e for e in result if e.get("category") == category]
    return result


def memory_delete(project_id: str, entry_id: str) -> bool:
    path = _memory_path(project_id)
    entries = _read_json(path, {})
    if entry_id in entries:
        del entries[entry_id]
        _write_json(path, entries)
        return True
    return False


def memory_stats(project_id: str) -> dict:
    entries = memory_get_all(project_id)
    cats: dict[str, int] = {}
    for e in entries:
        cats[e.get("category", "general")] = cats.get(e.get("category", "general"), 0) + 1
    return {"project_id": project_id, "total_entries": len(entries), "categories": cats}


# ── Per-project chat history ───────────────────────────────────────────────────

def history_append(project_id: str, role: str, content: str) -> None:
    path = _history_path(project_id)
    with _write_lock:
        history = _read_json(path, [])
        history.append({"role": role, "content": content, "ts": datetime.now().isoformat()})
        # Keep last 200 messages on disk
        _write_json(path, history[-200:])


def history_load(project_id: str, limit: int = 50) -> list[dict]:
    path = _history_path(project_id)
    history = _read_json(path, [])
    return history[-limit:]


def history_clear(project_id: str) -> None:
    path = _history_path(project_id)
    _write_json(path, [])


# ── Qdrant collection name for a project ──────────────────────────────────────

def qdrant_collection(project_id: str) -> str:
    return f"illip_{_safe_id(project_id)}"
