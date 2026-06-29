"""
Provider factory — auto-selects best available LLM backend.

Priority:
  1. Ollama      (local GPU) — if reachable
  2. OpenRouter  (cloud, 200+ models, free tier) — if OPENROUTER_API_KEY set
  3. Groq        (cloud, fast, free tier) — if GROQ_API_KEY set
  4. Mock        (dev only) — fallback

Set MODEL_PROVIDER=ollama/openrouter/groq/auto in .env.
"auto" picks Ollama when running, falls to OpenRouter/Groq when PC is off.
"""

import os
from typing import Optional
from app.config import settings
from app.providers.base_provider import BaseProvider
from app.providers.mock_provider import MockProvider
from app.providers.ollama_provider import OllamaProvider
from app.utils import logger

_provider: Optional[BaseProvider] = None
_provider_name: str = ""


_MODEL_BLOCKLIST = ("deepseek",)  # per PDF §28 model policy


def _check_model_policy(model_name: str) -> None:
    """Raise if model name violates project policy."""
    lower = (model_name or "").lower()
    for blocked in _MODEL_BLOCKLIST:
        if blocked in lower:
            raise RuntimeError(
                f"Model '{model_name}' is blocked by ILLIP model policy (§28). "
                f"Blocked families: {_MODEL_BLOCKLIST}. "
                "Allowed: Llama, Mistral, Phi, Gemma, Granite, Nemotron, Qwen."
            )


async def _make_provider() -> BaseProvider:
    mode = (os.environ.get("MODEL_PROVIDER") or settings.model_provider or "auto").lower()
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    or_key   = os.environ.get("OPENROUTER_API_KEY", "").strip()

    # Enforce model policy on any explicitly configured model name
    for env_var in ("OLLAMA_MODEL", "AIRLLM_MODEL", "LLAMAFILE_MODEL", "GROQ_MODEL"):
        _check_model_policy(os.environ.get(env_var, ""))

    if mode == "groq":
        if not groq_key:
            raise RuntimeError("MODEL_PROVIDER=groq but GROQ_API_KEY not set in .env")
        from app.providers.groq_provider import GroqProvider
        logger.info("Provider: Groq (forced)")
        return GroqProvider(groq_key)

    if mode == "openrouter":
        if not or_key:
            raise RuntimeError("MODEL_PROVIDER=openrouter but OPENROUTER_API_KEY not set in .env")
        from app.providers.openrouter_provider import OpenRouterProvider
        logger.info("Provider: OpenRouter (forced)")
        return OpenRouterProvider(or_key)

    if mode == "llamafile":
        from app.providers.llamafile_provider import LlamafileProvider
        p = LlamafileProvider()
        if not await p.health_check():
            logger.warning(f"llamafile unreachable at {p.base_url} — is it running?")
        else:
            logger.info(f"Provider: llamafile ({p.base_url})")
        return p

    if mode == "airllm":
        from app.providers.airllm_provider import AirLLMProvider
        logger.info("Provider: AirLLM (layer-streaming, large models on low VRAM)")
        return AirLLMProvider()

    if mode == "ollama":
        p = OllamaProvider()
        ok = await p.health_check()
        if not ok:
            logger.warning("Ollama unreachable and MODEL_PROVIDER=ollama — is 'ollama serve' running?")
        else:
            logger.info("Provider: Ollama (local GPU)")
        return p

    # auto: Ollama → AirLLM (if configured) → OpenRouter → Groq → Mock
    ollama = OllamaProvider()
    if await ollama.health_check():
        logger.info("Provider: Ollama (auto-selected, GPU active)")
        return ollama

    # llamafile fallback — if running at LLAMAFILE_URL
    llamafile_url = os.environ.get("LLAMAFILE_URL", "http://localhost:8080").strip()
    if llamafile_url:
        try:
            from app.providers.llamafile_provider import LlamafileProvider
            p = LlamafileProvider()
            if await p.health_check():
                logger.info("Provider: llamafile (auto-detected)")
                return p
        except Exception:
            pass

    # AirLLM fallback when AIRLLM_MODEL is set and Ollama is down
    airllm_model = os.environ.get("AIRLLM_MODEL", "").strip()
    if airllm_model:
        try:
            import airllm  # noqa
            from app.providers.airllm_provider import AirLLMProvider
            logger.info("Provider: AirLLM (auto-fallback — Ollama down, AIRLLM_MODEL set)")
            return AirLLMProvider()
        except ImportError:
            pass

    if or_key:
        from app.providers.openrouter_provider import OpenRouterProvider
        logger.info("Provider: OpenRouter (auto-fallback — Ollama not reachable)")
        return OpenRouterProvider(or_key)

    if groq_key:
        from app.providers.groq_provider import GroqProvider
        logger.info("Provider: Groq (auto-fallback — Ollama + OpenRouter not available)")
        return GroqProvider(groq_key)

    logger.warning("Provider: Mock (no Ollama, no OPENROUTER_API_KEY, no GROQ_API_KEY)")
    return MockProvider()


async def get_provider() -> BaseProvider:
    """Return active provider, re-checking if Ollama came back online."""
    global _provider, _provider_name

    mode = (os.environ.get("MODEL_PROVIDER") or settings.model_provider or "auto").lower()
    if mode == "auto" and _provider_name in ("openrouter", "groq"):
        ollama = OllamaProvider()
        if await ollama.health_check():
            logger.info("Provider: Ollama back online — switching from cloud")
            _provider = ollama
            _provider_name = "ollama"
            return _provider

    if _provider is None:
        _provider = await _make_provider()
        _provider_name = _provider.name

    return _provider


def reset_provider():
    global _provider, _provider_name
    _provider = None
    _provider_name = ""


class ProviderFactory:
    @classmethod
    def list_providers(cls) -> list:
        available = ["ollama", "llamafile"]
        if os.environ.get("AIRLLM_MODEL", ""):
            available.append("airllm")
        if os.environ.get("OPENROUTER_API_KEY", ""):
            available.append("openrouter")
        if os.environ.get("GROQ_API_KEY", ""):
            available.append("groq")
        available.append("mock")
        return available
