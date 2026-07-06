"""
Idea Journey endpoints — /idea, /stuck, /opps chat commands + vault.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import idea_journey
from app.utils import logger

router = APIRouter(prefix="/idea", tags=["idea"])


class IdeaRequest(BaseModel):
    idea: str
    project_id: str = "default"


class StuckRequest(BaseModel):
    situation: str = ""
    project_id: str = "default"


class OppsRequest(BaseModel):
    about: str = ""
    project_id: str = "default"


@router.post("/journey")
async def idea_journey_route(req: IdeaRequest):
    if not req.idea.strip():
        raise HTTPException(status_code=400, detail="Idea cannot be empty")
    try:
        report = await idea_journey.analyze_idea(req.idea.strip(), req.project_id)
        return {"report_md": report}
    except Exception as e:
        logger.error(f"idea journey failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stuck")
async def stuck_route(req: StuckRequest):
    try:
        report = await idea_journey.next_step(req.situation.strip(), req.project_id)
        return {"report_md": report}
    except Exception as e:
        logger.error(f"stuck mode failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/opportunities")
async def opportunities_route(req: OppsRequest):
    try:
        report = await idea_journey.find_opportunities(req.about.strip(), req.project_id)
        return {"report_md": report}
    except Exception as e:
        logger.error(f"opportunities failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vault")
async def vault_route():
    entries = idea_journey.vault_list()
    # Don't ship full idea text in the listing — hash + timestamp is the proof.
    return {"count": len(entries),
            "entries": [{"sha256": e["sha256"], "timestamp": e["timestamp"],
                         "preview": e.get("idea", "")[:80]} for e in entries]}
