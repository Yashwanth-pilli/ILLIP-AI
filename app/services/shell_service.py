"""
Shared shell execution — used by the /terminal API (user-driven, with a confirm
gate) and the run_shell skill (agent-driven, dangerous commands hard-blocked).

One place owns: the workspace sandbox, the danger filter, the timeout, and the
persistent cwd. Both callers route through execute_shell so the safety rules
can never drift apart.
"""

import os
import re
import asyncio
import subprocess
from pathlib import Path

from app.config import settings
from app.utils import logger

TIMEOUT = 60  # seconds per command

WS_ROOT = (Path(settings.get_data_path()) / "terminal").resolve()
WS_ROOT.mkdir(parents=True, exist_ok=True)

# Persistent cwd across calls (single local user).
_cwd = str(WS_ROOT)

_DANGER = [
    r"\brm\s+-rf?\s+[/~]", r"\brm\s+-rf?\s+\*", r":\(\)\s*\{", r"\bmkfs\b",
    r"\bdd\s+if=", r">\s*/dev/sd", r"\bshutdown\b", r"\breboot\b",
    r"\bdel\s+/[sqf]", r"\bformat\s+[a-z]:", r"\brmdir\s+/s", r"\bformat\b.*/[xy]",
    r"\bgit\s+push\b.*--force", r"\bchmod\s+-R\s+000", r"\b(sudo|runas)\b",
]
_DANGER_RE = re.compile("|".join(_DANGER), re.IGNORECASE)


def is_dangerous(cmd: str) -> bool:
    return bool(_DANGER_RE.search(cmd))


def get_cwd() -> str:
    return _cwd


def set_cwd(path) -> None:
    """Point the shell at a directory (server-controlled, e.g. an agent run dir
    so files it writes and commands it runs share the same folder)."""
    global _cwd
    p = Path(path).resolve()
    p.mkdir(parents=True, exist_ok=True)
    _cwd = str(p)


def _resolve_cd(cmd: str):
    """Handle `cd` so cwd persists and stays inside the workspace.
    Returns (handled: bool, message: str)."""
    global _cwd
    m = re.match(r"^\s*cd\s+(.+?)\s*$", cmd)
    if not m:
        return False, ""
    target = m.group(1).strip().strip('"').strip("'")
    if target in ("~", ""):
        _cwd = str(WS_ROOT)
        return True, _cwd
    new = (Path(_cwd) / target).resolve()
    try:
        new.relative_to(WS_ROOT)
    except ValueError:
        return True, f"blocked: cannot leave workspace ({WS_ROOT})"
    if not new.is_dir():
        return True, f"no such directory: {target}"
    _cwd = str(new)
    return True, _cwd


async def execute_shell(command: str, confirm: bool = False) -> dict:
    """Run a shell command in the sandboxed workspace. Dangerous commands need
    confirm=True; without it they return needs_confirm (the user path) — the
    agent path always passes confirm=False, so dangerous commands are refused."""
    global _cwd
    cmd = (command or "").strip()
    if not cmd:
        return {"stdout": "", "stderr": "", "exit_code": 0, "cwd": _cwd}

    handled, msg = _resolve_cd(cmd)
    if handled:
        blocked = msg.startswith("blocked") or msg.startswith("no such")
        return {"stdout": "" if blocked else f"cwd → {msg}", "stderr": msg if blocked else "",
                "exit_code": 1 if blocked else 0, "cwd": _cwd}

    if is_dangerous(cmd) and not confirm:
        return {"stdout": "", "stderr": "", "exit_code": -1, "cwd": _cwd,
                "needs_confirm": True,
                "warning": "This looks destructive. Re-run with confirm to proceed."}

    logger.info(f"Shell run (cwd={_cwd}): {cmd}")
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd, cwd=_cwd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            return {"stdout": "", "stderr": f"timed out after {TIMEOUT}s", "exit_code": 124, "cwd": _cwd}
        return {
            "stdout": out.decode("utf-8", "replace")[:20000],
            "stderr": err.decode("utf-8", "replace")[:8000],
            "exit_code": proc.returncode,
            "cwd": _cwd,
        }
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "exit_code": 1, "cwd": _cwd}
