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

    # Start observability metrics collector
    from app.monitoring.collector import get_metrics_collector
    get_metrics_collector().start()

    # Pre-warm default model in background
    asyncio.create_task(warmup_on_startup(settings.ollama_model, settings.ollama_base_url))

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
            await get_scheduler().start()
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
