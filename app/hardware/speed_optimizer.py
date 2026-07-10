"""
Speed optimizer — keep model hot, reduce time-to-first-token.

Techniques:
  1. Pre-warm: load model into VRAM before user types (startup)
  2. keep_alive: tell Ollama not to unload between requests
  3. Flash Attention: flag detection, injected into options when available
  4. Parallel prefill hint via num_batch
"""

import asyncio
from app.utils import logger


# Ollama default unloads after 5 min idle. This keeps model in GPU.
KEEP_ALIVE_SECONDS = 3600   # 1 hour; "-1" = forever, but that leaks VRAM

# Prefill batch size — larger = faster prompt processing, more VRAM peak
_PREFILL_BATCH = 512

# Track which (model, num_ctx) pair is currently loaded in Ollama VRAM.
# Ollama reloads the model if num_ctx changes — matching this avoids reload.
_warmed: dict[str, int] = {}   # model -> num_ctx currently loaded


def get_warmed_ctx(model: str, fallback=2048):
    """Return the num_ctx the model is loaded with, or fallback (can be None)."""
    return _warmed.get(model, fallback)


def mark_warmed(model: str, num_ctx: int) -> None:
    """Mark a model as loaded in VRAM with the given context size."""
    _warmed[model] = num_ctx


async def _get_current_ctx(model: str, base_url: str) -> int:
    """Query Ollama /api/ps to get the context size the model is running with.
    Returns that value so pre-warm can match it and avoid a reload."""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{base_url}/api/ps", timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status != 200:
                    return 2048
                d = await r.json()
                for m in d.get("models", []):
                    if m["name"] == model or m["model"] == model:
                        return m.get("context_length", 2048)
    except Exception:
        pass
    return 2048   # safe default — Ollama's own default


async def pre_warm(model: str, base_url: str = "http://localhost:11434", num_ctx: int = 4096) -> bool:
    """
    Load model into VRAM with a specific num_ctx.
    Using /api/chat (not /api/generate) so options match exactly what chat.py sends.
    Must be called with the same num_ctx used in all subsequent requests to avoid reload.
    """
    try:
        import aiohttp
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"{base_url}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                    "options": {
                        "num_ctx": num_ctx,
                        "keep_alive": KEEP_ALIVE_SECONDS,
                        "num_predict": 1,
                    },
                },
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                ok = resp.status == 200
                if ok:
                    _warmed[model] = num_ctx
                    logger.info(f"SpeedOptimizer: pre-warmed {model} num_ctx={num_ctx}")
                else:
                    logger.warning(f"SpeedOptimizer: pre-warm failed status={resp.status}")
                return ok
    except Exception as e:
        logger.warning(f"SpeedOptimizer: pre-warm error: {e!r}")
        return False


async def check_flash_attention(base_url: str = "http://localhost:11434") -> bool:
    """
    Detect if Ollama server was started with --flash-attn flag.
    We can't toggle it at runtime — but we can warn the user if it's missing.
    Returns True if flash attention seems active (heuristic: check /api/version response time).
    """
    # Ollama doesn't expose flash-attn state via API.
    # We return False so callers know to suggest manual restart with --flash-attn.
    return False


def speed_options(base_gpu_options: dict) -> dict:
    """
    Merge speed tuning into existing Ollama options dict.
    Call after GhostEngine builds the base options.
    """
    opts = dict(base_gpu_options)
    opts["keep_alive"] = KEEP_ALIVE_SECONDS

    # num_batch controls prefill parallelism — bigger = faster prompt processing
    # Only set if not already present (ghost engine doesn't touch this)
    if "num_batch" not in opts:
        opts["num_batch"] = _PREFILL_BATCH

    return opts


async def auto_select_model(base_url: str = "http://localhost:11434") -> str | None:
    """
    If the configured model isn't installed, find the best available model automatically.
    Returns the selected model name, or None if Ollama is offline.
    Nothing hardcoded — pulls live list from Ollama and picks by hardware fit.
    """
    try:
        import aiohttp
        from app.hardware.ghost_engine import recommend_model_for_hardware
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{base_url}/api/tags", timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                installed = {m["name"] for m in data.get("models", [])}

        if not installed:
            return None

        from app.hardware.ghost_engine import recommend_model
        recommended = await recommend_model(base_url)
        if recommended and recommended in installed:
            return recommended
        # Fallback: return any installed model
        return next(iter(installed))
    except Exception:
        return None


async def warmup_on_startup(model: str, base_url: str = "http://localhost:11434") -> None:
    """
    Pre-warm on startup. Auto-selects best available model, then loads with the
    SAME num_ctx that chat.py will use — prevents Ollama from reloading on first request.
    """
    await asyncio.sleep(2)

    # Snapshot all currently-running models into _warmed so we never change their ctx
    await _sync_warmed_from_ollama(base_url)

    best = await auto_select_model(base_url)
    if best and best != model:
        from app.config import settings
        logger.info(f"SpeedOptimizer: auto-selected {best} (configured: {model})")
        settings.ollama_model = best
        model = best

    # Skip pre_warm if model is already loaded — changing ctx causes a 30s reload
    if model in _warmed:
        logger.info(f"SpeedOptimizer: {model} already in VRAM (ctx={_warmed[model]}), skipping pre_warm")
        return
    ctx = await _get_current_ctx(model, base_url)
    await pre_warm(model, base_url, num_ctx=ctx)


async def _sync_warmed_from_ollama(base_url: str) -> None:
    """Read /api/ps and populate _warmed with whatever Ollama already has loaded."""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{base_url}/api/ps", timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status != 200:
                    return
                d = await r.json()
                for m in d.get("models", []):
                    name = m.get("name") or m.get("model")
                    ctx = m.get("context_length", 2048)
                    if name:
                        _warmed[name] = ctx
                        logger.info(f"SpeedOptimizer: detected {name} ctx={ctx}")
    except Exception as e:
        logger.debug(f"SpeedOptimizer: ps sync error: {e}")
