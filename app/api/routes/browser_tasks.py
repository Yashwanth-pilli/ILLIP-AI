"""
Browser Task API — AI-controlled browser automation with SSE streaming.

POST /api/browser/task        → start a browser task (streams via SSE)
GET  /api/browser/task/stream → SSE stream of BrowserStep events
GET  /api/browser/status      → is Playwright installed?
"""

import json

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agents.browser_task_agent import get_browser_task_agent
from app.utils import logger

router = APIRouter(prefix="/api/browser", tags=["browser"])


class BrowserTaskRequest(BaseModel):
    task: str
    start_url: str = ""
    credentials: dict = {}
    headless: bool | None = None        # None = use BROWSER_HEADLESS env
    capture_screenshots: bool = True
    max_steps: int = 50


@router.get("/status")
async def browser_status():
    """Check if Playwright is installed and ready."""
    try:
        from playwright.async_api import async_playwright  # noqa
        installed = True
    except ImportError:
        installed = False

    return {
        "playwright_installed": installed,
        "install_command": "pip install playwright && playwright install chromium" if not installed else None,
        "headless_mode": __import__("os").getenv("BROWSER_HEADLESS", "true"),
    }


@router.get("/stream")
async def stream_browser_task(
    task: str = Query(...),
    start_url: str = Query(""),
    headless: str = Query("null"),
    max_steps: int = Query(50),
    capture_screenshots: bool = Query(True),
):
    """
    SSE stream for browser task execution.
    Connect with EventSource — receives step events + screenshots.

    Event types:
      start   — task beginning
      step    — each action (action, target, result, optional screenshot_b64)
      done    — task completed with final result
      failed  — task failed with reason
    """
    _headless = None
    if headless.lower() == "true":
        _headless = True
    elif headless.lower() == "false":
        _headless = False

    agent = get_browser_task_agent()

    async def generate():
        try:
            async for event in agent.run_task(
                task=task,
                start_url=start_url,
                headless=_headless,
                capture_screenshots=capture_screenshots,
                max_steps=max_steps,
            ):
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") in ("done", "failed"):
                    break
        except Exception as e:
            err = {"type": "failed", "data": {"reason": str(e)}}
            yield f"data: {json.dumps(err)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/task")
async def start_browser_task(req: BrowserTaskRequest):
    """Returns stream URL for the task — connect via EventSource."""
    params = f"task={__import__('urllib.parse', fromlist=['quote']).quote(req.task)}"
    if req.start_url:
        params += f"&start_url={__import__('urllib.parse', fromlist=['quote']).quote(req.start_url)}"
    if req.headless is not None:
        params += f"&headless={str(req.headless).lower()}"
    params += f"&max_steps={req.max_steps}"
    params += f"&capture_screenshots={str(req.capture_screenshots).lower()}"

    return {
        "task": req.task,
        "stream_url": f"/api/browser/stream?{params}",
        "note": "Connect to stream_url with EventSource to see live progress.",
    }
