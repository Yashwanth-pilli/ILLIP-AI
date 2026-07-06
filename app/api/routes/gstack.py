"""
gstack — git helper for the chat. READ-ONLY: it inspects a repository and
suggests a commit message; it never commits, pushes, resets or mutates
anything. The user copies the suggested command and runs it themselves
(or asks the agent crew, which has its own confirm gates).

`/gstack [path]` -> branch, status, recent commits, staged diffstat,
                    and an LLM-written conventional-commit message when
                    there is anything staged.
"""

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.utils import logger

router = APIRouter(prefix="/gstack", tags=["gstack"])

_GIT_TIMEOUT = 15  # seconds per git call — local ops are fast or hung


class GstackRequest(BaseModel):
    path: str = ""  # empty = ILLIP's own repo (the folder the server runs from)


async def _git(repo: Path, *args: str) -> tuple[int, str]:
    """Run one read-only git command. Returns (exit_code, output)."""
    proc = await asyncio.create_subprocess_exec(
        "git", "-C", str(repo), *args,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=_GIT_TIMEOUT)
    except asyncio.TimeoutError:
        proc.kill()
        return 1, "git timed out"
    return proc.returncode or 0, out.decode("utf-8", errors="replace").strip()


async def gstack_report(raw_path: str = "") -> str:
    repo = Path(raw_path.strip().strip('"')) if raw_path.strip() \
        else Path(__file__).resolve().parents[3]
    if not repo.exists():
        return f"Path not found: `{repo}`"

    code, top = await _git(repo, "rev-parse", "--show-toplevel")
    if code != 0:
        return (f"`{repo}` is not a git repository.\n\n"
                f"Give me one: `/gstack E:/Projects/my-repo` — or run `git init` there first.")
    repo = Path(top)

    _, branch = await _git(repo, "branch", "--show-current")
    _, status = await _git(repo, "status", "--short")
    _, log = await _git(repo, "log", "--oneline", "-5")
    _, staged = await _git(repo, "diff", "--cached", "--stat")
    _, ahead = await _git(repo, "rev-list", "--count", "@{u}..HEAD")

    lines = [f"# 🌿 gstack: `{repo.name}`", "",
             f"**Branch:** `{branch or 'detached HEAD'}`"
             + (f" · **{ahead} commit(s) not pushed**" if ahead.isdigit() and int(ahead) > 0 else "")]

    if status:
        n = len(status.splitlines())
        lines += ["", f"## Working tree — {n} changed file(s)", "```", status[:2000], "```"]
    else:
        lines += ["", "Working tree clean. ✅"]

    if staged:
        lines += ["", "## Staged (ready to commit)", "```", staged[:2000], "```"]
        # Suggest a conventional-commit message from the staged diff.
        _, diff = await _git(repo, "diff", "--cached")
        try:
            from app.services.chat_service import get_llm
            msg = await get_llm().complete(
                "Write ONE conventional-commit message (subject <= 50 chars, "
                "format 'type: what', body only if the why isn't obvious, max 3 body "
                "lines) for this staged diff. Output ONLY the message, no quotes, "
                "no explanation.\n\n" + diff[:6000],
            )
            msg = (msg or "").strip().strip('"`')
            if msg:
                first = msg.splitlines()[0][:72]
                lines += ["", "## Suggested commit",
                          f"```", msg[:400], "```",
                          f"Run it: `git commit -m \"{first}\"`"]
        except Exception as e:
            logger.debug(f"gstack commit suggestion unavailable: {e}")
    elif status:
        lines += ["", "Nothing staged yet — `git add <files>` first, then `/gstack` again for a commit message."]

    if log:
        lines += ["", "## Recent commits", "```", log, "```"]

    lines += ["", "*gstack is read-only — it never commits or pushes for you.*"]
    return "\n".join(lines)


@router.post("/report")
async def gstack_route(req: GstackRequest):
    try:
        return {"report_md": await gstack_report(req.path)}
    except Exception as e:
        logger.error(f"gstack failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
