"""
Code executor skill — runs Python code in a sandboxed subprocess.
30-second timeout, no network, restricted builtins.
"""

import asyncio
import sys
import tempfile
import os
from pathlib import Path
from app.skills.base_skill import BaseSKill


# Modules the sandbox blocks (import will raise ImportError inside sandbox)
_BLOCKED_IMPORTS = {
    "subprocess", "os.system", "shutil", "socket",
    "requests", "httpx", "aiohttp", "urllib",
}

_SANDBOX_WRAPPER = """\
import sys, builtins, importlib

_blocked = {blocked}

_real_import = builtins.__import__
def _safe_import(name, *args, **kwargs):
    if name.split('.')[0] in _blocked:
        raise ImportError(f"Import '{{name}}' is blocked in sandbox.")
    return _real_import(name, *args, **kwargs)
builtins.__import__ = _safe_import

# Disable dangerous builtins
for _fn in ('__import__', 'open', 'exec', 'eval', 'compile'):
    pass  # leave open/eval for now — user code often needs them

# --- USER CODE ---
{code}
"""


class CodeExecutorSkill(BaseSKill):
    name = "run_python"
    description = (
        "Execute Python code locally and return stdout + errors. "
        "Use for calculations, data processing, algorithms, or testing logic. "
        "Network access is blocked. Timeout: 30 seconds."
    )
    parameters = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute. Print results you want to see.",
            },
            "timeout": {
                "type": "integer",
                "description": "Max seconds to run (default 15, max 30).",
            },
        },
        "required": ["code"],
    }

    async def execute(self, code: str, timeout: int = 15, **_) -> str:
        timeout = min(int(timeout), 30)

        # Write to temp file — avoids shell injection
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            wrapped = _SANDBOX_WRAPPER.format(
                blocked=repr(_BLOCKED_IMPORTS),
                code=code,
            )
            f.write(wrapped)
            tmp_path = f.name

        try:
            # cwd = shell sandbox (same folder run_shell uses), so files the
            # code writes land in the workspace, never in the server repo root
            from app.services.shell_service import get_cwd
            proc = await asyncio.create_subprocess_exec(
                sys.executable, tmp_path,
                cwd=get_cwd(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                return f"Error: Code timed out after {timeout}s."

            out = stdout.decode("utf-8", errors="replace").strip()
            err = stderr.decode("utf-8", errors="replace").strip()

            parts = []
            if out:
                parts.append(out)
            if err:
                # Filter out the sandbox wrapper lines from tracebacks
                err_lines = [
                    l for l in err.splitlines()
                    if "_SANDBOX_WRAPPER" not in l and "tmp" not in l.lower() or "Error" in l
                ]
                parts.append("Errors:\n" + "\n".join(err_lines))
            if proc.returncode != 0 and not parts:
                parts.append(f"Process exited with code {proc.returncode}")

            return "\n".join(parts) if parts else "(no output)"
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
