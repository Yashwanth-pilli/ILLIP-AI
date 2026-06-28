"""
Research API — Perplexity-style deep research with SSE streaming.

POST /api/research        → start research, returns task_id
GET  /api/research/stream → SSE stream of ResearchStep events
GET  /api/research/tasks  → list all agent pool tasks
"""

import asyncio
import json

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agents.research_agent import get_research_agent
from app.agents.pool import get_pool
from app.utils import logger

router = APIRouter(prefix="/api/research", tags=["research"])


class ResearchRequest(BaseModel):
    query: str
    depth: str = "standard"    # "quick" | "standard" | "deep"


@router.post("")
async def start_research(req: ResearchRequest):
    """Start research and stream via /api/research/stream?query=..."""
    return {"query": req.query, "depth": req.depth, "stream_url": f"/api/research/stream?query={req.query}&depth={req.depth}"}


@router.get("/stream")
async def stream_research(
    query: str = Query(...),
    depth: str = Query("standard"),
):
    """
    SSE endpoint — streams ResearchStep events as they happen.
    Frontend connects with EventSource.

    Event format:
        data: {"type": "search", "message": "...", "data": {...}}
    """
    agent = get_research_agent()

    async def event_generator():
        try:
            async for step in agent.research(query=query, depth=depth):
                yield step.to_sse()
                if step.type in ("done", "error"):
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            err = json.dumps({"type": "error", "message": str(e), "data": {}})
            yield f"data: {err}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/tasks")
async def list_tasks():
    """Show all running/recent agent pool tasks."""
    pool = get_pool()
    return {
        "active": pool.active_tasks(),
        "recent": pool.all_tasks(limit=20),
    }


@router.delete("/tasks/clear")
async def clear_done_tasks():
    pool = get_pool()
    cleared = pool.clear_done()
    return {"cleared": cleared}
