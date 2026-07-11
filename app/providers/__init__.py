"""
Provider factory — auto-selects best available LLM backend.

Priority (auto mode):
  1. Ollama            — local GPU/CPU (ollama serve)
  2. OpenAI-compat     — any OpenAI-compatible endpoint (DeepSeek, vLLM, LM Studio, Together, etc.)
  3. Anthropic         — Claude (best quality cloud)
  4. OpenRouter        — 200+ models, free tier
  5. Groq              — fast cloud, free tier
  6. Mock              — dev fallback

Set MODEL_PROVIDER in .env:
  auto | ollama | openai_compat | anthropic | openrouter | groq | llamafile | airllm | mock

No model restrictions. Use any model you want.
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

# Runtime "cloud mode" override — /cloud on points ILLIP at OmniRoute (an
# OpenAI-compatible local proxy to free cloud models) for zero local strain.
# When set, get_provider() returns this instead of the local brain.
_override: Optional[BaseProvider] = None


def set_cloud_override() -> str:
    """Route subsequent requests through OmniRoute (OpenAI-compat). Returns
    'ok', or 'not_configured' if OPENAI_COMPAT_BASE_URL isn't set."""
    global _override
    base = os.environ.get("OPENAI_COMPAT_BASE_URL", "").strip()
    if not base:
        return "not_configured"
    from app.providers.openai_compat_provider import OpenAICompatProvider
    _override = OpenAICompatProvider(base)
    logger.info(f"Cloud mode ON — routing via OmniRoute at {base}")
    return "ok"


def clear_cloud_override() -> None:
    global _override
    if _override is not None:
        logger.info("Cloud mode OFF — back to the local brain")
    _override = None


def cloud_override_active() -> bool:
    return _override is not None


async def _make_provider() -> BaseProvider:
    mode          = (os.environ.get("MODEL_PROVIDER") or settings.model_provider or "auto").lower()
    groq_key      = os.environ.get("GROQ_API_KEY", "").strip()
    or_key        = os.environ.get("OPENROUTER_API_KEY", "").strip()
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    compat_url    = os.environ.get("OPENAI_COMPAT_BASE_URL", "").strip()

    # ── Forced modes ──────────────────────────────────────────────────────────

    if mode == "openai_compat":
        if not compat_url:
            raise RuntimeError("MODEL_PROVIDER=openai_compat but OPENAI_COMPAT_BASE_URL not set")
        from app.providers.openai_compat_provider import OpenAICompatProvider
        logger.info(f"Provider: OpenAI-compat at {compat_url} (forced)")
        return OpenAICompatProvider(compat_url)

    if mode == "anthropic":
        if not anthropic_key:
            raise RuntimeError("MODEL_PROVIDER=anthropic but ANTHROPIC_API_KEY not set in .env")
        from app.providers.anthropic_provider import AnthropicProvider
        logger.info("Provider: Anthropic Claude (forced)")
        return AnthropicProvider(anthropic_key)

    if mode == "openrouter":
        if not or_key:
            raise RuntimeError("MODEL_PROVIDER=openrouter but OPENROUTER_API_KEY not set in .env")
        from app.providers.openrouter_provider import OpenRouterProvider
        logger.info("Provider: OpenRouter (forced)")
        return OpenRouterProvider(or_key)

    if mode == "groq":
        if not groq_key:
            raise RuntimeError("MODEL_PROVIDER=groq but GROQ_API_KEY not set in .env")
        from app.providers.groq_provider import GroqProvider
        logger.info("Provider: Groq (forced)")
        return GroqProvider(groq_key)

    if mode == "llamafile":
        from app.providers.llamafile_provider import LlamafileProvider
        p = LlamafileProvider()
        if await p.health_check():
            logger.info(f"Provider: llamafile at {p.base_url} (forced)")
        else:
            logger.warning(f"llamafile not reachable at {p.base_url} — is it running?")
        return p

    if mode == "airllm":
        from app.providers.airllm_provider import AirLLMProvider
        logger.info("Provider: AirLLM (forced)")
        return AirLLMProvider()

    if mode == "ollama":
        p = OllamaProvider()
        if not await p.health_check():
            logger.warning("Ollama unreachable — is 'ollama serve' running?")
        else:
            logger.info("Provider: Ollama (forced)")
        return p

    if mode == "mock":
        logger.info("Provider: Mock (forced)")
        return MockProvider()

    # ── Auto mode: pick best available ───────────────────────────────────────

    ollama = OllamaProvider()
    if await ollama.health_check():
        logger.info("Provider: Ollama (auto — local GPU active)")
        return ollama

    # Any OpenAI-compatible endpoint (DeepSeek API, vLLM, LM Studio, Together AI…)
    if compat_url:
        from app.providers.openai_compat_provider import OpenAICompatProvider
        p = OpenAICompatProvider(compat_url)
        if await p.health_check():
            logger.info(f"Provider: OpenAI-compat at {compat_url} (auto)")
            return p

    # llamafile — single-file model runner
    llamafile_url = os.environ.get("LLAMAFILE_URL", "").strip()
    if llamafile_url:
        try:
            from app.providers.llamafile_provider import LlamafileProvider
            p = LlamafileProvider()
            if await p.health_check():
                logger.info("Provider: llamafile (auto-detected)")
                return p
        except Exception:
            pass

    # AirLLM — large models on low VRAM via layer streaming
    airllm_model = os.environ.get("AIRLLM_MODEL", "").strip()
    if airllm_model:
        try:
            import airllm  # noqa
            from app.providers.airllm_provider import AirLLMProvider
            logger.info("Provider: AirLLM (auto — Ollama down, AIRLLM_MODEL set)")
            return AirLLMProvider()
        except ImportError:
            pass

    if anthropic_key:
        from app.providers.anthropic_provider import AnthropicProvider
        logger.info("Provider: Anthropic Claude (auto — no local model available)")
        return AnthropicProvider(anthropic_key)

    if or_key:
        from app.providers.openrouter_provider import OpenRouterProvider
        logger.info("Provider: OpenRouter (auto — no Anthropic key)")
        return OpenRouterProvider(or_key)

    if groq_key:
        from app.providers.groq_provider import GroqProvider
        logger.info("Provider: Groq (auto — last cloud option)")
        return GroqProvider(groq_key)

    logger.warning(
        "Provider: Mock — no model configured. "
        "Set ANTHROPIC_API_KEY, GROQ_API_KEY, or OPENROUTER_API_KEY in .env, "
        "or run 'ollama serve' for local models."
    )
    return MockProvider()


async def get_provider() -> BaseProvider:
    """Return active provider. Re-checks if Ollama comes back online in auto mode."""
    global _provider, _provider_name

    # Cloud mode (/cloud on) wins — every request goes through OmniRoute.
    if _override is not None:
        return _override

    mode = (os.environ.get("MODEL_PROVIDER") or settings.model_provider or "auto").lower()
    if mode == "auto" and _provider_name in ("anthropic", "openrouter", "groq", "openai_compat", "mock"):
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
        if os.environ.get("OPENAI_COMPAT_BASE_URL", ""):
            available.append("openai_compat")
        if os.environ.get("AIRLLM_MODEL", ""):
            available.append("airllm")
        if os.environ.get("ANTHROPIC_API_KEY", ""):
            available.append("anthropic")
        if os.environ.get("OPENROUTER_API_KEY", ""):
            available.append("openrouter")
        if os.environ.get("GROQ_API_KEY", ""):
            available.append("groq")
        available.append("mock")
        return available
