"""
Agent endpoints
"""

from fastapi import APIRouter, HTTPException, Body
from typing import Any, Dict
from app.core import AgentListResponse
from app.services import get_agent_service
from app.utils import logger
import app.agents.sdk as agent_sdk

router = APIRouter(prefix="/agents", tags=["agents"])


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
