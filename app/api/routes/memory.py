"""
Memory endpoints
"""

from fastapi import APIRouter, HTTPException
from app.services import get_memory_service
from app.utils import logger

router = APIRouter(prefix="/memory", tags=["memory"])


@router.post("/store")
async def store_memory(key: str, value: str, category: str = "general"):
    """Store a memory entry"""
    try:
        memory_service = get_memory_service()
        entry = memory_service.store(key, value, category)
        return entry
    except Exception as e:
        logger.error(f"Error storing memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/retrieve/{key}")
async def retrieve_memory(key: str):
    """Retrieve a memory entry by key"""
    try:
        memory_service = get_memory_service()
        value = memory_service.retrieve(key)
        if value is None:
            raise HTTPException(status_code=404, detail="Memory entry not found")
        return {"key": key, "value": value}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_memory(query: str, category: str = None, limit: int = 10):
    """Search memory entries"""
    try:
        memory_service = get_memory_service()
        results = memory_service.search(query, category, limit)
        return {
            "query": query,
            "results": results,
            "count": len(results),
        }
    except Exception as e:
        logger.error(f"Error searching memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all")
async def get_all_memory(category: str = None):
    """Get all memory entries"""
    try:
        memory_service = get_memory_service()
        entries = memory_service.get_all(category)
        return {
            "entries": entries,
            "count": len(entries),
        }
    except Exception as e:
        logger.error(f"Error getting all memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{entry_id}")
async def delete_memory(entry_id: str):
    """Delete a memory entry"""
    try:
        memory_service = get_memory_service()
        success = memory_service.delete(entry_id)
        if not success:
            raise HTTPException(status_code=404, detail="Memory entry not found")
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vector/list")
async def list_vector_memories(project_id: str = "default", limit: int = 200,
                               offset: int = 0, search: str = ""):
    """Browse long-term chat/vector memories."""
    from app.services import memory_qdrant
    entries = memory_qdrant.list_memories(project_id, limit, offset, search)
    stats = await memory_qdrant.memory_stats(project_id)
    return {"entries": entries, "count": len(entries), "stats": stats}


@router.delete("/vector/{rowid}")
async def delete_vector_memory(rowid: int, project_id: str = "default"):
    """Delete one long-term memory (FTS + Qdrant)."""
    from app.services import memory_qdrant
    if not memory_qdrant.delete_memory_entry(rowid, project_id):
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "deleted", "id": rowid}


@router.post("/vector/clear")
async def clear_vector_memories(project_id: str = "default"):
    """Wipe ALL long-term memories for a project. Fixes persona poisoning."""
    from app.services import memory_qdrant
    removed = memory_qdrant.clear_project_memories(project_id)
    return {"status": "cleared", "removed": removed, "project_id": project_id}


@router.get("/stats/overview")
async def get_memory_stats():
    """Get memory statistics"""
    try:
        memory_service = get_memory_service()
        stats = memory_service.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting memory stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
