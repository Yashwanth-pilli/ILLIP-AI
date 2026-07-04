"""
Terminal API — run real shell commands locally, like a dev terminal.

Thin HTTP layer over app.services.shell_service (which owns the workspace
sandbox, danger filter, timeout, and persistent cwd). The user path passes
confirm through so destructive commands prompt first; localhost-only.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.shell_service import execute_shell, get_cwd, WS_ROOT, TIMEOUT

router = APIRouter(prefix="/terminal", tags=["terminal"])


class CmdRequest(BaseModel):
    command: str
    confirm: bool = False


@router.get("/status")
async def terminal_status():
    return {"cwd": get_cwd(), "workspace_root": str(WS_ROOT), "timeout_s": TIMEOUT}


@router.post("/run")
async def run_command(req: CmdRequest):
    return await execute_shell(req.command, req.confirm)
