"""
Computer skills — let ILLIP act on the whole laptop, not just the workspace.

Design: READ + OPEN are laptop-wide (that's where the daily value is);
WRITE stays confined to the workspace sandbox (shell/read_file skills).
So ILLIP can find your resume, open Chrome, read a config — but cannot
modify or delete anything outside its sandbox.
"""

import asyncio
import os
import subprocess
from pathlib import Path

from app.skills.base_skill import BaseSKill

# Roots find_files may search. User-profile dirs + data drives.
_SEARCH_ROOTS = [
    Path.home() / "Desktop",
    Path.home() / "Documents",
    Path.home() / "Downloads",
    Path.home() / "Pictures",
    Path("E:/"),
    Path("D:/"),
]
_SKIP_DIRS = {"node_modules", ".git", ".venv", "__pycache__", "AppData",
              "$RECYCLE.BIN", "System Volume Information", "ollama_models"}

# Files we refuse to read even read-only (credential material).
_SENSITIVE_NAMES = {".env", "id_rsa", "id_ed25519", ".netrc", "credentials.json",
                    "secrets.json", ".npmrc", ".pypirc"}
_SENSITIVE_DIRS = {".ssh", ".gnupg", ".aws", ".azure"}


class OpenAppSkill(BaseSKill):
    name = "open_app"
    description = (
        "Open an application, file, folder, or URL on the user's computer. "
        "Examples: 'notepad', 'calc', 'chrome', 'https://gmail.com', "
        "'C:/Users/me/Documents', 'E:/report.pdf'. Opens with the default handler."
    )
    parameters = {
        "type": "object",
        "properties": {
            "target": {"type": "string",
                       "description": "App name, file path, folder path, or URL to open."},
        },
        "required": ["target"],
    }

    async def execute(self, target: str, **_) -> str:
        target = target.strip().strip('"')
        if not target:
            return "Error: empty target."
        try:
            if target.startswith(("http://", "https://")) or Path(target).exists():
                os.startfile(target)  # default handler: browser, explorer, app
                return f"Opened: {target}"
            # Not a path/URL — treat as an app name on PATH / app alias
            proc = await asyncio.create_subprocess_exec(
                "cmd", "/c", "start", "", target,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
            )
            _, err = await asyncio.wait_for(proc.communicate(), timeout=10)
            if proc.returncode == 0:
                return f"Launched: {target}"
            return f"Could not launch '{target}': {err.decode(errors='replace')[:200]}"
        except Exception as e:
            return f"Error opening '{target}': {e}"


class FindFilesSkill(BaseSKill):
    name = "find_files"
    description = (
        "Search the user's computer for files by name (Desktop, Documents, Downloads, "
        "Pictures, D:, E:). Example: pattern 'resume' finds resume.pdf anywhere. "
        "Returns matching paths. Read-only."
    )
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string",
                        "description": "Part of the filename to search for, e.g. 'resume' or '.pdf'."},
            "max_results": {"type": "integer", "description": "Max matches (default 20)."},
        },
        "required": ["pattern"],
    }

    async def execute(self, pattern: str, max_results: int = 20, **_) -> str:
        pattern = pattern.strip().lower()
        if len(pattern) < 2:
            return "Error: pattern too short (min 2 chars)."
        max_results = min(int(max_results), 50)

        def _scan() -> list[str]:
            found: list[str] = []
            for root in _SEARCH_ROOTS:
                if not root.exists():
                    continue
                try:
                    for dirpath, dirnames, filenames in os.walk(root):
                        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS
                                       and not d.startswith(".")]
                        for f in filenames:
                            if pattern in f.lower():
                                found.append(str(Path(dirpath) / f))
                                if len(found) >= max_results:
                                    return found
                except (PermissionError, OSError):
                    continue
            return found

        loop = asyncio.get_event_loop()
        try:
            found = await asyncio.wait_for(loop.run_in_executor(None, _scan), timeout=45)
        except asyncio.TimeoutError:
            return "Search timed out at 45s — try a more specific pattern."
        if not found:
            return f"No files matching '{pattern}' found."
        return f"Found {len(found)} file(s):\n" + "\n".join(found)


class ReadAnywhereSkill(BaseSKill):
    name = "read_any_file"
    description = (
        "Read any text file on the computer by absolute path (READ-ONLY). "
        "Use after find_files to read documents, notes, configs, code anywhere. "
        "Credential files (.env, ssh keys, etc.) are refused."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute file path, e.g. 'E:/notes/todo.txt'."},
            "max_lines": {"type": "integer", "description": "Max lines to return (default 200)."},
        },
        "required": ["path"],
    }

    async def execute(self, path: str, max_lines: int = 200, **_) -> str:
        p = Path(path.strip().strip('"'))
        if not p.is_absolute():
            return "Error: give an absolute path (use find_files first)."
        if not p.exists() or not p.is_file():
            return f"Error: file not found: {p}"
        if p.name.lower() in _SENSITIVE_NAMES or \
                any(part in _SENSITIVE_DIRS for part in p.parts):
            return "REFUSED: that looks like a credential/secret file."
        if p.stat().st_size > 5 * 1024 * 1024:
            return f"Error: file too large ({p.stat().st_size // 1024} KB, limit 5 MB)."
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"Error reading file: {e}"
        lines = text.splitlines()
        out = "\n".join(lines[: int(max_lines)])
        if len(lines) > int(max_lines):
            out += f"\n\n[... truncated at {max_lines} of {len(lines)} lines]"
        return out or "(empty file)"


if __name__ == "__main__":
    # ponytail self-check: sandbox guards are the only tricky logic
    import asyncio as _a
    r = _a.run(ReadAnywhereSkill().execute("relative/path.txt"))
    assert "absolute" in r, r
    r = _a.run(ReadAnywhereSkill().execute(str(Path.home() / ".ssh" / "id_rsa")))
    assert "REFUSED" in r or "not found" in r, r
    r = _a.run(FindFilesSkill().execute("x"))
    assert "too short" in r, r
    print("computer skills self-check ok")
