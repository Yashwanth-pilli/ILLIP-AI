"""
API routes module
"""

from fastapi import APIRouter
from app.api.routes import (
    health,
    chat,
    tasks,
    memory,
    agents,
    system,
    workspace,
    search,
    skills,
    learning,
    projects,
    self_dev,
    voice,
    plugins,
    telegram,
    governance,
    twin,
    monitoring,
    storage,
    webhooks,
    integrations,
    research,
    browser_tasks,
    image_gen,
    video_gen,
    scheduler,
    sync,
    terminal,
    idea,
    guardian,
    reminders,
)

# n8n, whatsapp routes — import separately (may not exist yet)
try:
    from app.api.routes import n8n as n8n_routes
    _has_n8n = True
except ImportError:
    _has_n8n = False

try:
    from app.api.routes import whatsapp as whatsapp_routes
    _has_whatsapp = True
except ImportError:
    _has_whatsapp = False

api_router = APIRouter(prefix="/api")

# Core
api_router.include_router(health.router)
api_router.include_router(chat.router)
api_router.include_router(tasks.router)
api_router.include_router(memory.router)
api_router.include_router(agents.router)
api_router.include_router(system.router)
api_router.include_router(workspace.router)
api_router.include_router(search.router)
api_router.include_router(skills.router)
api_router.include_router(learning.router)
api_router.include_router(projects.router)
api_router.include_router(self_dev.router)
api_router.include_router(voice.router)
api_router.include_router(plugins.router)
api_router.include_router(telegram.router)

# New layers
api_router.include_router(governance.router)
api_router.include_router(twin.router)
api_router.include_router(monitoring.router)
api_router.include_router(storage.router)
api_router.include_router(webhooks.router)
api_router.include_router(integrations.router)
api_router.include_router(research.router)
api_router.include_router(browser_tasks.router)
api_router.include_router(image_gen.router)
api_router.include_router(video_gen.router)
api_router.include_router(scheduler.router)
api_router.include_router(sync.router)
api_router.include_router(terminal.router)
api_router.include_router(idea.router)
api_router.include_router(guardian.router)
api_router.include_router(reminders.router)

if _has_n8n:
    api_router.include_router(n8n_routes.router)
if _has_whatsapp:
    api_router.include_router(whatsapp_routes.router)
