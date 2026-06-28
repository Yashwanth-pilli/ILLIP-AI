"""Scheduler API — manage recurring jobs."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.scheduler_agent import get_scheduler

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


class AddJobRequest(BaseModel):
    name: str
    interval_s: float
    skip_if_stressed: bool = False


@router.get("/jobs")
async def list_jobs():
    return {"jobs": get_scheduler().list_jobs()}


@router.post("/jobs/{job_id}/enable")
async def enable_job(job_id: str):
    if not get_scheduler().set_enabled(job_id, True):
        raise HTTPException(404, "job not found")
    return {"ok": True}


@router.post("/jobs/{job_id}/disable")
async def disable_job(job_id: str):
    if not get_scheduler().set_enabled(job_id, False):
        raise HTTPException(404, "job not found")
    return {"ok": True}


@router.post("/jobs/{job_id}/run")
async def run_job_now(job_id: str):
    ok = await get_scheduler().run_job_now(job_id)
    if not ok:
        raise HTTPException(404, "job not found")
    return {"ok": True}


@router.delete("/jobs/{job_id}")
async def remove_job(job_id: str):
    if not get_scheduler().remove_job(job_id):
        raise HTTPException(404, "job not found")
    return {"ok": True}
