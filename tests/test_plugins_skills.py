"""Plugin marketplace and skills system tests."""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

CATALOGUE_PLUGINS = [
    "weather_wttr", "exchange_rate", "ip_geolocation", "github_repo",
    "hacker_news_top", "open_library_search", "open_meteo_weather",
    "wikipedia_summary", "joke_api", "country_info", "n8n_webhook",
    "openrouter_chat",
]

BUILTIN_SKILLS = [
    "calculator", "get_datetime", "web_search",
    "read_file", "run_python", "read_pdf",
]


# ── Plugins ──────────────────────────────────────────────────────────────────

def test_plugins_list():
    r = client.get("/api/plugins/")
    assert r.status_code == 200
    d = r.json()
    assert "plugins" in d


def test_catalogue_returns_all_12():
    r = client.get("/api/plugins/catalogue")
    assert r.status_code == 200
    d = r.json()
    assert "catalogue" in d
    assert len(d["catalogue"]) == 12


def test_catalogue_category_filter():
    r = client.get("/api/plugins/catalogue?category=data")
    assert r.status_code == 200
    d = r.json()
    assert "catalogue" in d


@pytest.mark.parametrize("plugin_name", CATALOGUE_PLUGINS)
def test_catalogue_contains_plugin(plugin_name):
    r = client.get("/api/plugins/catalogue")
    names = [p["name"] for p in r.json()["catalogue"]]
    assert plugin_name in names, f"{plugin_name} missing from catalogue"


def test_install_unknown_plugin_returns_404():
    r = client.post("/api/plugins/install/totally_fake_plugin_xyz")
    assert r.status_code == 404


# ── Skills ───────────────────────────────────────────────────────────────────

def test_skills_list():
    r = client.get("/api/skills/")
    assert r.status_code == 200
    d = r.json()
    assert "skills" in d
    assert len(d["skills"]) >= len(BUILTIN_SKILLS)


@pytest.mark.parametrize("skill_name", BUILTIN_SKILLS)
def test_builtin_skill_present(skill_name):
    r = client.get("/api/skills/")
    names = [s["name"] for s in r.json()["skills"]]
    assert skill_name in names, f"Built-in skill '{skill_name}' not registered"


def test_calculator_skill_run():
    r = client.post("/api/skills/calculator/run", json={"expression": "2 + 2"})
    assert r.status_code == 200
    d = r.json()
    assert "result" in d or "output" in d or "error" in d


def test_datetime_skill_run():
    r = client.post("/api/skills/get_datetime/run", json={})
    assert r.status_code == 200
