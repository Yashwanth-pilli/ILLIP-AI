"""
Projects endpoints — create, list, switch projects.
Memory, history, and vector store are scoped per project.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services.project_service import (
    create_project, get_project, list_projects, delete_project,
    memory_get_all, memory_stats, history_load, history_clear,
    DEFAULT_PROJECT,
)
from app.services.chat_service import get_chat_service

router = APIRouter(prefix="/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""


@router.get("/")
async def list_all_projects():
    return {"projects": list_projects()}


@router.post("/")
async def create_new_project(req: CreateProjectRequest):
    try:
        project = create_project(req.name, req.description)
        return project
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/{project_id}")
async def get_project_info(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
    stats = memory_stats(project_id)
    return {**project, "memory_stats": stats}


@router.get("/{project_id}/memory")
async def get_project_memory(project_id: str, category: Optional[str] = None):
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
    entries = memory_get_all(project_id, category)
    return {"project_id": project_id, "entries": entries, "count": len(entries)}


@router.get("/{project_id}/history")
async def get_project_history(project_id: str, limit: int = 50):
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
    return {"project_id": project_id, "history": history_load(project_id, limit)}


@router.delete("/{project_id}/history")
async def clear_project_history(project_id: str):
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
    get_chat_service().clear_history(project_id)
    return {"status": "cleared", "project_id": project_id}


@router.delete("/{project_id}")
async def delete_project_endpoint(project_id: str):
    if project_id == DEFAULT_PROJECT:
        raise HTTPException(status_code=400, detail="Cannot delete the default project.")
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
    delete_project(project_id)
    return {"status": "deleted", "project_id": project_id}
