"""
Workspace Intelligence — project-aware file search + context injection.

Workspaces are directories on disk. ILLIP reads code/files from them,
injects relevant context into chat, and answers questions about the codebase.

Features:
  - File search (ripgrep or Python fallback)
  - Relevant-file finder for a query (keyword overlap heuristic)
  - Context injection: auto-attach top-N relevant files to chat
  - Workspace stats (language breakdown, file count, size)
"""

import os
import re
import uuid
import json
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List
from app.utils import logger, get_current_timestamp, get_workspaces_path

_WORKSPACE_DB = Path("data/workspaces.json")
_TEXT_EXTS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".cpp", ".c", ".h",
    ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".scala", ".sh",
    ".yaml", ".yml", ".toml", ".json", ".md", ".txt", ".html", ".css",
    ".sql", ".r", ".m", ".lua", ".dart", ".ex", ".exs",
}
_SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", "dist",
    "build", ".next", ".nuxt", "target", "out",
}
_MAX_FILE_BYTES = 64 * 1024  # 64KB per file for context
_MAX_CONTEXT_FILES = 5


def _load_db() -> dict:
    try:
        return json.loads(_WORKSPACE_DB.read_text())
    except Exception:
        return {"workspaces": {}, "current": None}


def _save_db(db: dict) -> None:
    _WORKSPACE_DB.parent.mkdir(parents=True, exist_ok=True)
    _WORKSPACE_DB.write_text(json.dumps(db, indent=2))


class WorkspaceService:
    """Project-aware workspace management with code intelligence."""

    def create_workspace(self, name: str, path: str = "", description: str = "") -> Dict[str, Any]:
        db = _load_db()
        ws_id = str(uuid.uuid4())[:8]
        ws = {
            "id": ws_id,
            "name": name,
            "path": str(Path(path).resolve()) if path else "",
            "description": description,
            "created_at": get_current_timestamp().isoformat(),
            "status": "active",
        }
        db["workspaces"][ws_id] = ws
        if not db["current"]:
            db["current"] = ws_id
        _save_db(db)
        logger.info(f"Workspace created: {name} ({path})")
        return ws

    def get_current_workspace(self) -> Optional[Dict[str, Any]]:
        db = _load_db()
        cur = db.get("current")
        return db["workspaces"].get(cur) if cur else None

    def set_current_workspace(self, workspace_id: str) -> bool:
        db = _load_db()
        if workspace_id not in db["workspaces"]:
            return False
        db["current"] = workspace_id
        _save_db(db)
        return True

    def list_workspaces(self) -> Dict[str, Any]:
        db = _load_db()
        return {
            "workspaces": list(db["workspaces"].values()),
            "current": db.get("current"),
            "total": len(db["workspaces"]),
        }

    def get_stats(self) -> Dict[str, Any]:
        db = _load_db()
        ws = self.get_current_workspace()
        stats: Dict[str, Any] = {
            "total_workspaces": len(db["workspaces"]),
            "current_workspace": db.get("current"),
        }
        if ws and ws.get("path") and Path(ws["path"]).exists():
            stats.update(self._dir_stats(Path(ws["path"])))
        return stats

    def _dir_stats(self, root: Path) -> dict:
        lang_counts: Dict[str, int] = {}
        total_files = 0
        total_bytes = 0
        for f in self._iter_files(root):
            ext = f.suffix.lower()
            lang_counts[ext] = lang_counts.get(ext, 0) + 1
            total_files += 1
            try:
                total_bytes += f.stat().st_size
            except Exception:
                pass
        return {
            "file_count": total_files,
            "size_mb": round(total_bytes / 1e6, 2),
            "languages": dict(sorted(lang_counts.items(), key=lambda x: -x[1])[:10]),
        }

    def _iter_files(self, root: Path):
        """Yield text files under root, skipping ignored dirs."""
        for item in root.rglob("*"):
            if item.is_file() and item.suffix.lower() in _TEXT_EXTS:
                if not any(skip in item.parts for skip in _SKIP_DIRS):
                    yield item

    def search_files(self, query: str, workspace_path: str = "", max_results: int = 20) -> List[dict]:
        """
        Search for query string across workspace files.
        Uses ripgrep if available, falls back to Python search.
        """
        root = self._resolve_root(workspace_path)
        if root is None:
            return []

        results = []
        pattern = re.compile(re.escape(query), re.IGNORECASE)

        for fpath in self._iter_files(root):
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
                matches = []
                for i, line in enumerate(text.splitlines(), 1):
                    if pattern.search(line):
                        matches.append({"line": i, "text": line.rstrip()})
                        if len(matches) >= 5:
                            break
                if matches:
                    results.append({
                        "file": str(fpath.relative_to(root)),
                        "matches": matches,
                    })
                    if len(results) >= max_results:
                        break
            except Exception:
                pass

        return results

    def read_file(self, rel_path: str, workspace_path: str = "") -> dict:
        """Read a specific file from workspace."""
        root = self._resolve_root(workspace_path)
        if root is None:
            return {"error": "No workspace path configured"}

        fpath = (root / rel_path).resolve()
        # Path traversal guard
        if not str(fpath).startswith(str(root)):
            return {"error": "Path outside workspace"}

        if not fpath.exists():
            return {"error": f"File not found: {rel_path}"}

        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
            if len(content) > _MAX_FILE_BYTES:
                content = content[:_MAX_FILE_BYTES] + "\n\n... [truncated]"
            return {
                "path": rel_path,
                "content": content,
                "lines": content.count("\n") + 1,
                "size_bytes": fpath.stat().st_size,
            }
        except Exception as e:
            return {"error": str(e)}

    def get_relevant_context(self, query: str, workspace_path: str = "", max_files: int = _MAX_CONTEXT_FILES) -> str:
        """
        Find files relevant to query, return formatted context string
        for injection into chat messages.
        """
        root = self._resolve_root(workspace_path)
        if root is None:
            return ""

        # Score files by keyword overlap with query
        query_words = set(re.findall(r"\w+", query.lower())) - {"the", "a", "is", "in", "for", "what", "how"}
        scored: List[tuple[float, Path, str]] = []

        for fpath in self._iter_files(root):
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")[:_MAX_FILE_BYTES]
                words = set(re.findall(r"\w+", text.lower()))
                score = len(query_words & words)
                # Boost by filename match
                if any(w in fpath.name.lower() for w in query_words):
                    score += 3
                if score > 0:
                    scored.append((score, fpath, text))
            except Exception:
                pass

        scored.sort(key=lambda x: -x[0])
        top = scored[:max_files]

        if not top:
            return ""

        parts = []
        for _, fpath, text in top:
            rel = str(fpath.relative_to(root))
            # Truncate long files
            if len(text) > 3000:
                text = text[:3000] + "\n... [truncated]"
            parts.append(f"### {rel}\n```\n{text}\n```")

        return "\n\n".join(parts)

    def list_files(self, workspace_path: str = "", max_files: int = 200) -> List[str]:
        """List all text files in workspace."""
        root = self._resolve_root(workspace_path)
        if root is None:
            return []
        files = []
        for f in self._iter_files(root):
            files.append(str(f.relative_to(root)))
            if len(files) >= max_files:
                break
        return sorted(files)

    def _resolve_root(self, workspace_path: str) -> Optional[Path]:
        if workspace_path:
            p = Path(workspace_path)
            return p if p.is_dir() else None
        ws = self.get_current_workspace()
        if ws and ws.get("path"):
            p = Path(ws["path"])
            return p if p.is_dir() else None
        return None


_workspace_service: Optional[WorkspaceService] = None


def get_workspace_service() -> WorkspaceService:
    global _workspace_service
    if _workspace_service is None:
        _workspace_service = WorkspaceService()
    return _workspace_service
