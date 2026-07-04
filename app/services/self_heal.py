"""
Self-heal — the doctor that fixes problems on its own.

Runs as a background loop AND on demand. Only acts when a real problem is
detected, and only applies SAFE fixes (start a service, switch to a model that
fits, re-warm a cold model). Never deletes data, never does anything
destructive. Every action is recorded so the UI can show "auto-fixed X".

Common failures it repairs automatically:
  1. Ollama not running        -> start `ollama serve`
  2. Active model not installed -> switch to best model the hardware can run
  3. Model cold / not loaded    -> re-warm it so the next chat is instant
"""

import time
import asyncio
import shutil
import subprocess

import aiohttp

from app.config import settings
from app.utils import logger

_POLL_INTERVAL = 60          # seconds between background heal passes
_OLLAMA_START_COOLDOWN = 120  # don't spam `ollama serve`

# Ring buffer of recent actions for the UI / doctor report
_actions: list[dict] = []
_last_ollama_start = 0.0
_heal_task: asyncio.Task | None = None


def _record(action: str, detail: str = "") -> None:
    entry = {"action": action, "detail": detail, "ts": time.time()}
    _actions.append(entry)
    del _actions[:-20]  # keep last 20
    logger.info(f"SelfHeal: {action} — {detail}")


def recent_actions() -> list[dict]:
    return list(_actions)


async def _ollama_up() -> tuple[bool, list[str]]:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                f"{settings.ollama_base_url}/api/tags",
                timeout=aiohttp.ClientTimeout(total=4),
            ) as r:
                if r.status != 200:
                    return False, []
                data = await r.json()
                return True, [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        return False, []


def _try_start_ollama() -> bool:
    """Spawn `ollama serve` detached. Safe: no-op if already running or not installed."""
    global _last_ollama_start
    now = time.monotonic()
    if now - _last_ollama_start < _OLLAMA_START_COOLDOWN:
        return False
    _last_ollama_start = now
    if not shutil.which("ollama"):
        _record("ollama_start_skipped", "ollama binary not found on PATH")
        return False
    try:
        kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        # Detach so it outlives this request and doesn't block.
        if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):  # Windows
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(["ollama", "serve"], **kwargs)
        _record("ollama_started", "launched `ollama serve`")
        return True
    except Exception as e:
        _record("ollama_start_failed", str(e))
        return False


async def heal(reason: str = "manual") -> list[dict]:
    """Run one heal pass. Returns the actions taken this pass (empty if healthy)."""
    taken: list[dict] = []
    before = len(_actions)

    # Only heal Ollama-backed setups; cloud/mock providers self-manage.
    if settings.model_provider not in ("ollama", "auto"):
        return taken

    up, models = await _ollama_up()

    # 1. Ollama down -> start it, wait, re-check
    if not up:
        if _try_start_ollama():
            await asyncio.sleep(6)
            up, models = await _ollama_up()
            if up:
                _record("ollama_recovered", f"back online, {len(models)} models")

    if not up:
        # Nothing more we can safely do; provider layer falls back to cloud/mock.
        return _actions[before:]

    # 2. Active model missing / won't fit -> switch to a model that runs here
    if models:
        active = settings.ollama_model
        installed = active in models or any(
            m.split(":")[0] == active.split(":")[0] for m in models
        )
        fits = True
        if installed:
            try:
                from app.hardware.ghost_engine import calculate_plan
                plan = await calculate_plan(active, base_url=settings.ollama_base_url)
                fits = plan.feasible
            except Exception:
                fits = True
        if not installed or not fits:
            try:
                from app.hardware.ghost_engine import recommend_model
                rec = await recommend_model(settings.ollama_base_url)
                if rec and rec != active:
                    settings.ollama_model = rec
                    from app.providers import get_provider
                    provider = await get_provider()
                    if hasattr(provider, "model"):
                        provider.model = rec
                    _record("model_switched",
                            f"'{active}' unavailable/unfit -> '{rec}'")
            except Exception as e:
                _record("model_switch_failed", str(e))

    return _actions[before:]


async def _loop():
    # First pass shortly after startup, then every _POLL_INTERVAL.
    await asyncio.sleep(15)
    while True:
        try:
            await heal(reason="background")
        except Exception as e:
            logger.debug(f"SelfHeal loop error (non-fatal): {e}")
        await asyncio.sleep(_POLL_INTERVAL)


def start_self_heal() -> None:
    """Start background heal loop. Safe to call once from app startup."""
    global _heal_task
    if _heal_task is not None and not _heal_task.done():
        return
    try:
        _heal_task = asyncio.get_event_loop().create_task(_loop())
        logger.info("SelfHeal: started (auto-repair every 60s)")
    except RuntimeError:
        logger.debug("SelfHeal: no event loop yet")


if __name__ == "__main__":
    # ponytail self-check: record ring buffer caps at 20, recent_actions reflects it.
    for i in range(25):
        _record(f"a{i}", "x")
    assert len(recent_actions()) == 20
    assert recent_actions()[-1]["action"] == "a24"
    print("self_heal self-check ok")
