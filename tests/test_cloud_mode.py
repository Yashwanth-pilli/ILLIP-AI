"""Cloud mode: /cloud on routes through OmniRoute (OpenAI-compat) when configured."""
import os
import pytest

from app.providers import (
    set_cloud_override, clear_cloud_override, cloud_override_active, get_provider,
)


@pytest.fixture(autouse=True)
def _clean():
    clear_cloud_override()
    saved = os.environ.get("OPENAI_COMPAT_BASE_URL")
    yield
    clear_cloud_override()
    if saved is None:
        os.environ.pop("OPENAI_COMPAT_BASE_URL", None)
    else:
        os.environ["OPENAI_COMPAT_BASE_URL"] = saved


def test_cloud_off_without_config():
    os.environ.pop("OPENAI_COMPAT_BASE_URL", None)
    assert set_cloud_override() == "not_configured"
    assert cloud_override_active() is False


@pytest.mark.asyncio
async def test_cloud_on_switches_provider_when_configured():
    os.environ["OPENAI_COMPAT_BASE_URL"] = "http://localhost:20128/v1"
    assert set_cloud_override() == "ok"
    assert cloud_override_active() is True
    provider = await get_provider()
    assert provider.name == "openai_compat"


def test_clear_reverts_to_local():
    os.environ["OPENAI_COMPAT_BASE_URL"] = "http://localhost:20128/v1"
    set_cloud_override()
    clear_cloud_override()
    assert cloud_override_active() is False


def test_base_url_strips_trailing_v1():
    from app.providers.openai_compat_provider import OpenAICompatProvider
    # user includes /v1 (as OmniRoute docs show) — must not double up
    p = OpenAICompatProvider("http://localhost:20128/v1")
    assert p.base_url == "http://localhost:20128"
    assert p._chat_url() == "http://localhost:20128/v1/chat/completions"
    # and it still works without /v1
    p2 = OpenAICompatProvider("http://localhost:20128")
    assert p2._chat_url() == "http://localhost:20128/v1/chat/completions"


def test_aggregate_sse_joins_deltas():
    from app.providers.openai_compat_provider import OpenAICompatProvider
    sse = (
        'data: {"choices":[{"delta":{"content":"Hello"}}]}\n'
        'data: {"choices":[{"delta":{"content":" world"}}]}\n'
        'data: [DONE]\n'
    )
    assert OpenAICompatProvider._aggregate_sse(sse) == "Hello world"


def test_aggregate_sse_tools_assembles_call():
    from app.providers.openai_compat_provider import OpenAICompatProvider
    # tool_calls arrive split across SSE chunks (name first, args in pieces)
    sse = (
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"name":"web_search"}}]}}]}\n'
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\"q\\":"}}]}}]}\n'
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"\\"ai\\"}"}}]}}]}\n'
        'data: [DONE]\n'
    )
    content, calls = OpenAICompatProvider._aggregate_sse_tools(sse)
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "web_search"
    assert calls[0]["function"]["arguments"] == '{"q":"ai"}'
