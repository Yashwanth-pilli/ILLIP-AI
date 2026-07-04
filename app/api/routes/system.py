"""
System endpoints
"""

from fastapi import APIRouter, HTTPException
from app.core import SystemStatus
from app.services import (
    get_model_service,
    get_chat_service,
    get_agent_service,
    get_task_service,
    get_memory_service,
)
from app.providers import get_provider
from app.hardware import get_hardware_info
from app.utils import logger, get_current_timestamp
import time

router = APIRouter(prefix="/system", tags=["system"])

# Track startup time
_startup_time = time.time()


@router.get("/status", response_model=SystemStatus)
async def get_system_status() -> SystemStatus:
    """Get overall system status"""
    try:
        # Get provider status
        provider = await get_provider()
        
        # Get stats from services
        chat_service = get_chat_service()
        task_service = get_task_service()
        memory_service = get_memory_service()
        agent_service = get_agent_service()
        
        task_stats = task_service.get_stats()
        memory_stats = memory_service.get_stats()
        agent_stats = agent_service.list_agents()
        
        # Calculate uptime
        uptime = time.time() - _startup_time
        
        from app.api.routes.chat import get_active_model
        return SystemStatus(
            status="running",
            model_provider=provider.name,
            active_model=get_active_model() if provider.name == "ollama" else provider.name,
            database_connected=True,
            memory_count=memory_stats["total_entries"],
            task_count=task_stats["total"],
            agent_count=agent_stats["total_count"],
            uptime_seconds=uptime,
            timestamp=get_current_timestamp()
        )
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/info")
async def get_system_info():
    """Get detailed system information"""
    try:
        model_service = get_model_service()
        agent_service = get_agent_service()
        task_service = get_task_service()
        memory_service = get_memory_service()
        
        provider_status = await model_service.get_provider_status()
        agents = agent_service.list_agents()
        tasks = task_service.get_stats()
        memory = memory_service.get_stats()
        
        return {
            "provider": provider_status,
            "agents": agents,
            "tasks": tasks,
            "memory": memory,
            "timestamp": get_current_timestamp().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hardware")
async def get_hardware():
    """Get hardware info and model recommendations."""
    try:
        hw = get_hardware_info()
        return {
            "tier": hw.tier,
            "tier_label": ["", "Low-end", "Mid-range", "Good", "High-end"][hw.tier],
            "cpu_cores": hw.cpu_cores,
            "ram_gb": hw.ram_gb,
            "ram_available_gb": hw.ram_available_gb,
            "gpu_name": hw.gpu_name,
            "gpu_vram_gb": hw.gpu_vram_gb,
            "os": hw.os,
            "recommended_model": hw.recommended_model,
            "max_context": hw.max_context,
            "safe_threads": hw.safe_threads,
            "warnings": hw.warnings,
        }
    except Exception as e:
        logger.error(f"Hardware info error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hardware/live")
async def get_hardware_live():
    """Live hardware state — temp, VRAM, CPU, pressure, loaded models."""
    try:
        import aiohttp
        from app.hardware.guard import read_hardware_state_async
        s = await read_hardware_state_async()

        # Ask Ollama which models are loaded in GPU right now
        loaded_models = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "http://localhost:11434/api/ps",
                    timeout=aiohttp.ClientTimeout(total=2),
                ) as r:
                    if r.status == 200:
                        data = await r.json()
                        for m in data.get("models", []):
                            loaded_models.append({
                                "name": m.get("name", ""),
                                "size_mb": round(m.get("size", 0) / 1024 / 1024),
                                "processor": m.get("details", {}).get("processor", "GPU"),
                            })
        except Exception:
            pass

        from app.services.self_heal import recent_actions
        return {
            "cpu_percent":      s.cpu_percent,
            "ram_percent":      s.ram_percent,
            "gpu_temp_c":       s.gpu_temp_c,
            "gpu_util_percent": s.gpu_util_percent,
            "vram_used_mb":     s.gpu_vram_used_mb,
            "vram_total_mb":    s.gpu_vram_total_mb,
            "vram_percent":     round(s.vram_percent, 1),
            "pressure":         s.pressure,
            "is_safe":          s.is_safe,
            "reason":           s.reason,
            "loaded_models":    loaded_models,
            "heal_actions":     recent_actions()[-5:],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ghost-engine/{model_name:path}")
async def get_ghost_plan(model_name: str, ctx: int = 8192):
    """
    Calculate Ghost Engine loading plan for any model on current hardware.
    Queries Ollama /api/show for real architecture (param count, quant, layers).
    Falls back to name-based estimation if Ollama offline.
    """
    try:
        from app.hardware.ghost_engine import calculate_plan
        from app.config import settings as _cfg
        plan = await calculate_plan(model_name, requested_ctx=ctx, base_url=_cfg.ollama_base_url)
        return {
            "model":          plan.model,
            "strategy":       plan.strategy,
            "gpu_layers":     plan.gpu_layers,
            "cpu_layers":     plan.cpu_layers,
            "total_layers":   plan.total_layers,
            "vram_used_gb":   plan.vram_used_gb,
            "ram_used_gb":    plan.ram_used_gb,
            "context_limit":  plan.context_limit,
            "feasible":       plan.feasible,
            "warnings":       plan.warnings,
            "ollama_options": plan.ollama_options,
            "draft_model":    plan.draft_model,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ghost-engine-recommend")
async def ghost_recommend_model():
    """Recommend best installed model for current hardware. Dynamic — no hardcoding."""
    from app.hardware.ghost_engine import recommend_model, calculate_plan
    from app.config import settings as _cfg
    model = await recommend_model(_cfg.ollama_base_url)
    if not model:
        return {"recommended_model": None, "reason": "No models installed or Ollama offline"}
    plan = await calculate_plan(model, base_url=_cfg.ollama_base_url)
    return {"recommended_model": model, "plan": plan.ollama_options, "strategy": plan.strategy}


@router.get("/context-budget")
async def context_budget_info():
    """Show current token budget breakdown — how ILLIP manages context like GTA map zones."""
    from app.hardware.context_manager import _BUDGET, TOTAL_SAFE_BUDGET, _RAW_TURNS
    return {
        "total_safe_budget_tokens": TOTAL_SAFE_BUDGET,
        "budget_breakdown": _BUDGET,
        "raw_turns_kept": _RAW_TURNS,
        "description": (
            f"Last {_RAW_TURNS} turns sent raw. Older turns compressed by 3B model. "
            f"Total context capped at ~{TOTAL_SAFE_BUDGET} tokens regardless of model size."
        ),
    }


@router.get("/models")
async def list_models_with_plans():
    """
    List ALL Ollama models installed on this machine.
    For each: ghost plan, VRAM fit, strategy, hardware recommendation.
    Nothing hardcoded — pulls live from Ollama /api/tags + hardware detector.
    """
    from app.hardware.ghost_engine import calculate_plan, recommend_model
    from app.hardware.detector import get_hardware_info
    from app.config import settings as _cfg
    import aiohttp

    hw = get_hardware_info()
    recommended = await recommend_model(_cfg.ollama_base_url) or ""

    # Fetch installed models from Ollama
    installed = []
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                f"{_cfg.ollama_base_url}/api/tags",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    installed = data.get("models", [])
    except Exception:
        pass

    results = []
    for m in installed:
        name = m.get("name", "")
        size_bytes = m.get("size", 0)
        size_gb = round(size_bytes / 1024 ** 3, 2)
        try:
            plan = await calculate_plan(name, 8192, _cfg.ollama_base_url)
            results.append({
                "name": name,
                "size_gb": size_gb,
                "strategy": plan.strategy,
                "gpu_layers": plan.gpu_layers,
                "total_layers": plan.total_layers,
                "vram_used_gb": plan.vram_used_gb,
                "context_limit": plan.context_limit,
                "feasible": plan.feasible,
                "warnings": plan.warnings,
                "is_recommended": name == recommended or name.split(":")[0] == recommended.split(":")[0],
            })
        except Exception:
            results.append({"name": name, "size_gb": size_gb, "feasible": True, "warnings": []})

    # Sort: recommended first, then by VRAM fit
    results.sort(key=lambda x: (not x.get("is_recommended"), not x.get("feasible")))

    return {
        "models": results,
        "recommended": recommended,
        "active": _cfg.ollama_model,
        "hardware_summary": f"{hw.gpu_name} · {hw.gpu_vram_gb}GB VRAM · {hw.ram_gb}GB RAM",
        "ollama_running": len(installed) > 0,
    }


@router.post("/models/switch")
async def switch_active_model(body: dict):
    """
    Switch active model at runtime — no restart needed.
    Triggers Ghost Engine pre-warm so first request is fast.
    """
    import asyncio
    model = body.get("model", "").strip()
    if not model:
        raise HTTPException(status_code=400, detail="model required")
    from app.config import settings as _cfg
    old_model = _cfg.ollama_model
    _cfg.ollama_model = model

    # Update provider singleton
    from app.providers import get_provider
    provider = await get_provider()
    if hasattr(provider, "model"):
        provider.model = model

    # Drop old model from warmed cache so next request uses Ghost Engine for new model
    from app.hardware.speed_optimizer import _warmed
    _warmed.pop(old_model, None)

    # Get Ghost plan for the new model (fast — just Ollama /api/show + hw query)
    ghost_info = {}
    try:
        from app.hardware.ghost_engine import calculate_plan
        plan = await calculate_plan(model, requested_ctx=8192, base_url=_cfg.ollama_base_url)
        ghost_info = {
            "strategy":      plan.strategy,
            "gpu_layers":    plan.gpu_layers,
            "total_layers":  plan.total_layers,
            "context_limit": plan.context_limit,
            "vram_used_gb":  plan.vram_used_gb,
            "warnings":      plan.warnings[:2],  # top 2 only
        }
        # Pre-warm in background so first chat request is instant
        asyncio.create_task(
            _pre_warm_model(model, _cfg.ollama_base_url, plan.ollama_options.get("num_ctx", 4096))
        )
    except Exception as e:
        logger.warning(f"Ghost plan failed for {model}: {e}")

    logger.info(f"Model switched: {old_model} → {model} | strategy={ghost_info.get('strategy','?')}")
    return {"switched_to": model, "ghost": ghost_info}


async def _pre_warm_model(model: str, base_url: str, num_ctx: int) -> None:
    """Background: load model into VRAM with Ghost-computed ctx so first request has zero reload penalty."""
    try:
        from app.hardware.speed_optimizer import pre_warm
        await pre_warm(model, base_url, num_ctx=num_ctx)
        logger.info(f"Ghost pre-warm complete: {model} ctx={num_ctx}")
    except Exception as e:
        logger.debug(f"Ghost pre-warm failed (non-critical): {e}")


@router.get("/doctor")
async def system_doctor():
    """One-shot diagnostics — Ollama, models, hardware, deps, disk, power. Read-only."""
    from app.services.doctor import run_diagnostics, format_report
    from app.services.self_heal import recent_actions
    result = await run_diagnostics()
    result["auto_heal_actions"] = recent_actions()[-5:]
    result["report_md"] = format_report(result)
    return result


@router.post("/doctor/heal")
async def system_doctor_heal():
    """Run the self-healing doctor now: auto-fix Ollama/model problems. Safe actions only."""
    from app.services.self_heal import heal, recent_actions
    fixed = await heal(reason="manual")
    return {
        "fixed": fixed,
        "recent_actions": recent_actions()[-10:],
        "message": (f"Fixed {len(fixed)} issue(s)." if fixed else "No problems found — system healthy."),
    }


@router.get("/reflexion/stats")
async def reflexion_stats():
    """Show reflexion quality tracking stats."""
    from app.agents.reflexion_agent import _PATTERN_FILE
    if not _PATTERN_FILE.exists():
        return {"total_patterns": 0, "avg_score": None}
    import json as _json
    lines = _PATTERN_FILE.read_text(encoding="utf-8").strip().splitlines()
    records = [_json.loads(l) for l in lines if l.strip()]
    avg = round(sum(r["score"] for r in records) / len(records), 2) if records else None
    return {
        "total_patterns": len(records),
        "avg_score": avg,
        "high_quality": sum(1 for r in records if r["score"] >= 8),
        "retry_count": sum(1 for r in records if r.get("was_retry")),
    }


@router.post("/refresh")
async def refresh_system(body: dict = {}):
    """
    Soft refresh — clear in-memory state, reset model, keep ALL data on disk.

    What gets cleared (RAM only, disk untouched):
      - In-memory conversation buffers (all projects)
      - Whisper model (reloads on next voice request)
      - Ollama model unloaded from GPU then reloaded (via keep_alive=0 then pre-warm)

    What is KEPT (nothing lost):
      - All chat history (disk: data/projects/*/history.json)
      - All memory (Qdrant + data/projects/*/memory.json)
      - All tasks, proposals, learning data
      - All plugins and skills

    Use when: AI giving irrelevant answers, context feels polluted, model seems stuck.
    """
    from app.config import settings as _cfg
    import aiohttp

    cleared = []

    # 1. Flush in-memory conversation buffers (they're already on disk)
    try:
        from app.services.chat_service import get_chat_service
        svc = get_chat_service()
        svc._histories.clear()   # in-memory cache only; disk untouched
        cleared.append("conversation_buffers")
    except Exception as e:
        logger.warning(f"Refresh: buffer clear failed: {e}")

    # 2. Unload Ollama model from GPU (keep_alive=0 = unload immediately)
    try:
        async with aiohttp.ClientSession() as s:
            await s.post(
                f"{_cfg.ollama_base_url}/api/generate",
                json={"model": _cfg.ollama_model, "prompt": "", "keep_alive": 0},
                timeout=aiohttp.ClientTimeout(total=5),
            )
        cleared.append("ollama_model_unloaded")
    except Exception:
        pass   # Ollama may not be running, that's fine

    # 3. Drop Whisper from memory
    try:
        from app.api.routes.voice import _WHISPER_MODEL
        import app.api.routes.voice as _vm
        _vm._WHISPER_MODEL = None
        cleared.append("whisper_model")
    except Exception:
        pass

    # 4. Re-warm model in background (non-blocking)
    try:
        import asyncio
        from app.hardware.speed_optimizer import warmup_on_startup
        asyncio.create_task(warmup_on_startup(_cfg.ollama_model, _cfg.ollama_base_url))
        cleared.append("model_rewarm_queued")
    except Exception:
        pass

    project_id = body.get("project_id")
    note = (
        f"Refreshed project '{project_id}' context" if project_id
        else "Refreshed all in-memory context"
    )
    logger.info(f"System refresh: {cleared}")
    return {
        "status": "refreshed",
        "cleared": cleared,
        "note": note,
        "data_safe": True,
        "history_on_disk": True,
        "memory_on_disk": True,
    }


@router.post("/reset")
async def reset_system():
    """Alias for /refresh — same safe behavior, no data loss."""
    return await refresh_system()
