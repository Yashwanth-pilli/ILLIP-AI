"""
run_shell skill — lets agents run real shell commands in the workspace.

Routes through the same shell_service as the /terminal API, so the workspace
sandbox, timeout, and danger filter all apply. Agents call this WITHOUT confirm,
so destructive commands (rm -rf /, format, shutdown, …) are refused, not run.
Safe build/test commands (python, pytest, npm, ls, mkdir, git status) run fine.
"""

from app.skills.base_skill import BaseSKill
from app.services.shell_service import execute_shell


class ShellSkill(BaseSKill):
    name = "run_shell"
    description = (
        "Run a shell command in the workspace and get stdout/stderr/exit code. "
        "Use to install packages, run scripts, run tests, list files, git status, etc. "
        "Runs in a sandboxed workspace folder. Destructive commands are refused."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The shell command to run, e.g. 'python app.py' or 'pytest -q'."},
        },
        "required": ["command"],
    }

    async def execute(self, command: str, **_) -> str:
        r = await execute_shell(command, confirm=False)  # agents never auto-confirm danger
        if r.get("needs_confirm"):
            return f"REFUSED: '{command}' looks destructive and is blocked in autonomous mode."
        parts = []
        if r.get("stdout"):
            parts.append(r["stdout"].rstrip())
        if r.get("stderr"):
            parts.append("stderr:\n" + r["stderr"].rstrip())
        if not parts:
            parts.append("(no output)")
        parts.append(f"[exit {r.get('exit_code')} · cwd {r.get('cwd')}]")
        return "\n".join(parts)[:12000]
