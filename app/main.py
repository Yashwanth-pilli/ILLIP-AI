"""
ILLIP AI — Main FastAPI application
"""

import os
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.utils import logger, ensure_all_directories
from app.api import api_router
from app.db import init_database
import app.skills   # noqa: F401 — registers built-in skills on import
import app.plugins  # noqa: F401 — loads user-defined plugins from data/plugins/

# Ensure all directories exist
ensure_all_directories()

# Initialize database
try:
    init_database()
except Exception as e:
    logger.warning(f"Database initialization failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager for startup and shutdown events"""
    import asyncio
    from app.hardware.speed_optimizer import warmup_on_startup
    logger.info("ILLIP AI starting up...")
    logger.info(f"Configuration: {settings.model_provider}")

    # Start GPU safety monitor
    from app.hardware.safety_monitor import start_monitor
    start_monitor()

    # Start self-healing doctor — auto-repairs Ollama/model problems in the background
    from app.services.self_heal import start_self_heal
    start_self_heal()

    # Start observability metrics collector
    from app.monitoring.collector import get_metrics_collector
    get_metrics_collector().start()

    # Auto-select a model that fits THIS hardware before warming. Makes ILLIP
    # run on any laptop with zero config: if the configured model isn't installed
    # (or won't fit), fall back to the best installed model the GPU/RAM can handle.
    async def _auto_select_and_warm():
        try:
            from app.hardware.ghost_engine import list_installed_models, recommend_model, calculate_plan
            from app.providers import get_provider
            installed = await list_installed_models(settings.ollama_base_url)
            names = {m["name"] for m in installed}
            chosen = settings.ollama_model
            fits = False
            if chosen in names:
                try:
                    plan = await calculate_plan(chosen, base_url=settings.ollama_base_url)
                    fits = plan.feasible
                except Exception:
                    fits = True  # can't check → trust it
            if not fits and installed:
                rec = await recommend_model(settings.ollama_base_url)
                if rec:
                    logger.warning(
                        f"Startup: '{settings.ollama_model}' not installed/feasible on this "
                        f"hardware — auto-switching to '{rec}'."
                    )
                    settings.ollama_model = rec
                    provider = await get_provider()
                    if hasattr(provider, "model"):
                        provider.model = rec
        except Exception as e:
            logger.debug(f"Startup auto-select skipped (non-fatal): {e}")
        await warmup_on_startup(settings.ollama_model, settings.ollama_base_url)

    async def _prewarm_heavy_model():
        """Pre-warm the LARGE (MoE) model in the background so the FIRST heavy task
        doesn't pay the one-time load cost. Delayed so it doesn't fight startup, and
        skipped if LARGE == the everyday model (nothing extra to load). Ollama +
        Ghost Engine manage placement; the safety monitor guards against pressure."""
        try:
            await asyncio.sleep(25)  # let the everyday model settle first
            from app.services.router_service import LARGE, SMALL
            if not LARGE or LARGE == SMALL or LARGE == settings.ollama_model:
                return
            from app.hardware.ghost_engine import calculate_plan
            from app.hardware.speed_optimizer import pre_warm
            plan = await calculate_plan(LARGE, base_url=settings.ollama_base_url)
            if not plan.feasible:
                logger.info(f"Skip pre-warming {LARGE}: not feasible on this hardware.")
                return
            logger.info(f"Pre-warming heavy model {LARGE} in background (first big task will be instant)…")
            await pre_warm(LARGE, settings.ollama_base_url, num_ctx=plan.ollama_options.get("num_ctx", 4096))
            logger.info(f"Heavy model {LARGE} warm and ready.")
        except Exception as e:
            logger.debug(f"Heavy-model pre-warm skipped (non-fatal): {e}")

    asyncio.create_task(_auto_select_and_warm())
    asyncio.create_task(_prewarm_heavy_model())

    # Start Telegram bot — wrapped so any crash (anyio/Python 3.14 compat) is non-fatal
    if settings.telegram_bot_token:
        async def _safe_telegram():
            try:
                from app.connectors.telegram_bot import start_bot
                await start_bot(settings.telegram_bot_token)
            except Exception as _tg_err:
                logger.warning(f"Telegram bot stopped (non-fatal): {_tg_err}")
        asyncio.create_task(_safe_telegram())
        logger.info("Telegram bot queued for startup")

    # Start all connectors — non-fatal
    async def _safe_connectors():
        try:
            from app.connectors.registry import get_connector_registry
            await get_connector_registry().start_all()
        except Exception as e:
            logger.warning(f"Connector registry error (non-fatal): {e}")
    asyncio.create_task(_safe_connectors())
    logger.info("Connector registry starting all configured connectors")

    # Start agent event bus — non-fatal
    async def _safe_bus():
        try:
            from app.agents.bus import get_bus
            await get_bus().start()
        except Exception as e:
            logger.warning(f"Agent bus error (non-fatal): {e}")
    asyncio.create_task(_safe_bus())
    logger.info("Agent event bus started")

    # Start scheduler — non-fatal
    async def _safe_scheduler():
        try:
            from app.agents.scheduler_agent import get_scheduler
            scheduler = get_scheduler()
            from app.services.reminder_service import check_due_reminders
            scheduler.add_job("user_reminders", check_due_reminders, interval_s=60)
            await scheduler.start()
        except Exception as e:
            logger.warning(f"Scheduler error (non-fatal): {e}")
    asyncio.create_task(_safe_scheduler())
    logger.info("SchedulerAgent started")

    yield

    logger.info("ILLIP AI shutting down...")

    # Stop all connectors
    from app.connectors.registry import get_connector_registry
    await get_connector_registry().stop_all()

    # Stop Telegram bot
    if settings.telegram_bot_token:
        from app.connectors.telegram_bot import stop_bot
        await stop_bot()

    # Stop metrics collector
    from app.monitoring.collector import get_metrics_collector
    await get_metrics_collector().stop()


# Create FastAPI app with lifespan handler
app = FastAPI(
    title="ILLIP AI",
    description="Your AI company — portable, private, local-first.",
    version="3.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# API key auth — enabled when ILLIP_API_KEYS set in .env
from app.auth import APIKeyMiddleware
app.add_middleware(APIKeyMiddleware)

# CORS — configurable via CORS_ORIGINS in .env (default: open for local use)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)

# OpenAI-compatible endpoint at /v1/* (Continue.dev, OpenAI SDK clients)
from app.api.routes.openai_compat import router as _oai_router
app.include_router(_oai_router)

# Serve generated images
data_dir = settings.project_root / "data"
data_dir.mkdir(exist_ok=True)
app.mount("/data", StaticFiles(directory=str(data_dir)), name="data")

# Serve frontend — Vite build output (dist/) takes priority, falls back to root
_frontend_root = settings.project_root / "frontend"
_frontend_dist  = _frontend_root / "dist"
_serve_dir = _frontend_dist if _frontend_dist.exists() else _frontend_root

if _serve_dir.exists():
    from fastapi.responses import FileResponse

    _index_file = _serve_dir / "index.html"

    # Serve index.html with no-cache so the browser ALWAYS gets the newest asset
    # references (the hashed JS/CSS below still cache forever — their names change
    # each build). Without this, a cached index.html pins users to a stale bundle.
    @app.get("/", include_in_schema=False)
    async def _spa_index():
        return FileResponse(_index_file, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

    app.mount("/", StaticFiles(directory=str(_serve_dir), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level="info",
    )
