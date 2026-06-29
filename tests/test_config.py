"""Config and environment variable tests — nothing hardcoded."""

import os
import pytest
from app.config import Settings


def test_all_defaults_are_safe():
    s = Settings()
    assert s.debug is False           # prod default
    assert s.model_provider == "auto"
    assert s.api_port == 8000
    assert s.illip_api_keys == ""     # auth off by default


def test_env_override_model_provider(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "groq")
    s = Settings()
    assert s.model_provider == "groq"


def test_env_override_api_host(monkeypatch):
    monkeypatch.setenv("API_HOST", "0.0.0.0")
    s = Settings()
    assert s.api_host == "0.0.0.0"


def test_env_override_debug(monkeypatch):
    monkeypatch.setenv("DEBUG", "true")
    s = Settings()
    assert s.debug is True


def test_cors_origins_star():
    s = Settings()
    s.cors_origins = "*"
    assert s.get_cors_origins() == ["*"]


def test_cors_origins_comma_list():
    s = Settings()
    s.cors_origins = "https://myapp.com,https://app2.com"
    origins = s.get_cors_origins()
    assert "https://myapp.com" in origins
    assert "https://app2.com" in origins
    assert len(origins) == 2


def test_anthropic_key_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    s = Settings()
    assert s.anthropic_api_key == "sk-ant-test"


def test_openai_compat_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPAT_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("OPENAI_COMPAT_MODEL", "deepseek-chat")
    s = Settings()
    assert s.openai_compat_base_url == "https://api.deepseek.com"
    assert s.openai_compat_model == "deepseek-chat"


def test_no_model_restriction():
    """Any model name must be accepted — no blocklist."""
    from app.providers import _make_provider
    # Just verify _check_model_policy does not exist
    import app.providers as pmod
    assert not hasattr(pmod, "_check_model_policy"), \
        "Model blocklist was re-introduced — remove it"
    assert not hasattr(pmod, "_MODEL_BLOCKLIST"), \
        "Model blocklist constant was re-introduced — remove it"


def test_ensure_directories():
    s = Settings()
    s.ensure_directories()
    assert s.get_data_path().exists()
    assert s.get_memory_path().exists()
    assert s.get_logs_path().exists()


def test_version():
    from app import __version__
    assert __version__ == "3.1.0"
