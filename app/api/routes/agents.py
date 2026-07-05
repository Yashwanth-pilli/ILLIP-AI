"""
Agent endpoints
"""

import json
from fastapi import APIRouter, HTTPException, Body, Query
from fastapi.responses import StreamingResponse
from typing import Any, Dict
from app.core import AgentListResponse
from app.services import get_agent_service
from app.utils import logger
import app.agents.sdk as agent_sdk

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/run/stream")
async def run_agents_stream(task: str = Query(..., description="The goal to run through the agent company")):
    """Run a task through Planner + agents, streaming live progress via SSE.

    Events: step_start (agent + what it's doing), plan (the full step list),
    step_done (result summary), final (combined answer), end.
    """
    from app.services.agent_orchestrator import run_task_stream

    async def gen():
        try:
            async for ev in run_task_stream(task):
                yield f"data: {json.dumps(ev)}\n\n"
        except Exception as e:
            logger.error(f"Agent orchestration error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        yield 'data: {"type": "end"}\n\n'

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/clarify")
async def clarify_task(task: str = Query(..., description="Goal to generate clarifying questions for")):
    """Ask 2-4 clarifying questions BEFORE building (how top models work).
    Returns {questions: [...]}. Empty list means the goal is clear enough."""
    from app.agents import get_agent_registry
    registry = get_agent_registry()
    agent = registry.get_agent("planner") or registry.get_agent("ceo")
    prompt = (
        "A user wants an AI agent team to do this task:\n"
        f"\"{task[:1200]}\"\n\n"
        "Before starting, what do you need to know? Write 2-4 SHORT clarifying "
        "questions that would change how you build it (scope, style, target, "
        "constraints). If the task is already fully clear, return an empty array.\n"
        "Reply with ONLY a JSON array of question strings, e.g. "
        '["What platform?", "Dark or light theme?"]'
    )
    questions: list[str] = []
    try:
        res = await agent.execute_task(prompt)
        text = res.get("output", "") if res.get("status") == "success" else ""
        m = __import__("re").search(r"\[.*?\]", text, __import__("re").DOTALL)
        if m:
            raw = json.loads(m.group(0))
            questions = [str(q).strip() for q in raw if str(q).strip()][:4]
    except Exception as e:
        logger.warning(f"Clarify failed: {e}")
    return {"task": task, "questions": questions}


@router.get("/loop/stream")
async def run_agents_loop_stream(
    task: str = Query(..., description="The goal to loop on until QA passes"),
    max_loops: int = Query(3, ge=1, le=5),
):
    """Agentic LOOP: run crew -> QA verdict -> retry with feedback until done.

    Extra events vs /run/stream: loop_start {loop,max,feedback},
    loop_check {loop,done,feedback}, loop_end {loops_used,done}.
    """
    from app.services.agent_orchestrator import run_task_loop_stream

    async def gen():
        try:
            async for ev in run_task_loop_stream(task, max_loops):
                yield f"data: {json.dumps(ev)}\n\n"
        except Exception as e:
            logger.error(f"Agent loop error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        yield 'data: {"type": "end"}\n\n'

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/run/{run_id}/zip")
async def download_run_zip(run_id: str):
    """Zip up all files an agent run produced and return them as one download."""
    import io
    import re
    import zipfile
    from fastapi import HTTPException
    from fastapi.responses import Response
    from app.services.shell_service import WS_ROOT

    if not re.fullmatch(r"run_\d+", run_id):  # no path traversal
        raise HTTPException(400, "bad run id")
    run_dir = (WS_ROOT / "agent_runs" / run_id).resolve()
    if not str(run_dir).startswith(str(WS_ROOT.resolve())) or not run_dir.is_dir():
        raise HTTPException(404, "run not found")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in run_dir.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(run_dir))
    buf.seek(0)
    return Response(
        buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{run_id}.zip"'},
    )


@router.get("/", response_model=AgentListResponse)
async def list_agents():
    """List all available agents"""
    try:
        agent_service = get_agent_service()
        data = agent_service.list_agents()
        return AgentListResponse(
            agents=data["agents"],
            total_available=data["available_count"]
        )
    except Exception as e:
        logger.error(f"Error listing agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_type}")
async def get_agent_status(agent_type: str):
    """Get status of a specific agent"""
    try:
        agent_service = get_agent_service()
        status = agent_service.get_agent_status(agent_type)
        if not status:
            raise HTTPException(status_code=404, detail="Agent not found")
        return status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_type}/execute")
async def execute_agent_task(agent_type: str, task_input: str, context: dict = None):
    """Execute a task using a specific agent.

    `task_input` is accepted as a query parameter to keep the starter API easy
    to try from the browser docs. A future version can add a request body when
    richer agent inputs are needed.
    """
    try:
        if not task_input or not task_input.strip():
            raise HTTPException(status_code=400, detail="Task input cannot be empty")
        
        agent_service = get_agent_service()
        result = await agent_service.execute_agent_task(agent_type, task_input, context)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing agent task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── SDK-registered agents ────────────────────────────────────────────────────

@router.get("/sdk/list")
async def sdk_list_agents():
    """List all SDK-registered external agents."""
    return {"agents": agent_sdk.list_agents()}


@router.post("/sdk/run/{agent_name}")
async def sdk_run_agent(
    agent_name: str,
    task: str = Body(..., embed=True),
    context: Dict[str, Any] = Body({}, embed=True),
):
    """Run an SDK-registered agent by name."""
    try:
        result = await agent_sdk.run_agent(agent_name, task, context)
        return {"agent": agent_name, "result": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"SDK agent error [{agent_name}]: {e}")
        raise HTTPException(status_code=500, detail=str(e))
