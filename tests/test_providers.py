"""Provider factory and individual provider tests."""

import os
import pytest
from unittest.mock import AsyncMock, patch


def test_provider_factory_list():
    from app.providers import ProviderFactory
    providers = ProviderFactory.list_providers()
    assert "ollama" in providers
    assert "mock" in providers
    assert isinstance(providers, list)


def test_provider_factory_includes_anthropic_when_key_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    from app.providers import ProviderFactory
    # Re-evaluate — list_providers reads env at call time
    providers = ProviderFactory.list_providers()
    assert "anthropic" in providers


def test_provider_factory_includes_openai_compat_when_url_set(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPAT_BASE_URL", "http://localhost:8000")
    from app.providers import ProviderFactory
    providers = ProviderFactory.list_providers()
    assert "openai_compat" in providers


def test_provider_factory_includes_groq_when_key_set(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    from app.providers import ProviderFactory
    providers = ProviderFactory.list_providers()
    assert "groq" in providers


def test_provider_factory_includes_openrouter_when_key_set(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    from app.providers import ProviderFactory
    providers = ProviderFactory.list_providers()
    assert "openrouter" in providers


@pytest.mark.asyncio
async def test_mock_provider_health():
    from app.providers.mock_provider import MockProvider
    p = MockProvider()
    ok = await p.health_check()
    assert ok is True


@pytest.mark.asyncio
async def test_mock_provider_generates():
    from app.providers.mock_provider import MockProvider
    from app.core import Message
    from datetime import datetime
    p = MockProvider()
    msgs = [Message(role="user", content="Hello", timestamp=datetime.now())]
    response = await p.generate_response(msgs)
    assert isinstance(response, str)
    assert len(response) > 0


@pytest.mark.asyncio
async def test_groq_provider_bad_key():
    from app.providers.groq_provider import GroqProvider
    p = GroqProvider("bad_key_xxxx")
    ok = await p.health_check()
    assert ok is False


@pytest.mark.asyncio
async def test_openai_compat_provider_unreachable():
    from app.providers.openai_compat_provider import OpenAICompatProvider
    p = OpenAICompatProvider("http://127.0.0.1:19999")  # nothing here
    ok = await p.health_check()
    assert ok is False


@pytest.mark.asyncio
async def test_anthropic_provider_bad_key():
    from app.providers.anthropic_provider import AnthropicProvider
    p = AnthropicProvider("sk-ant-bad")
    ok = await p.health_check()
    assert ok is False


@pytest.mark.asyncio
async def test_reset_provider():
    from app.providers import reset_provider, get_provider
    reset_provider()
    p = await get_provider()
    assert p is not None
    assert hasattr(p, "name")
