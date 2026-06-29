"""Tests for all 27 registered agents."""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

ALL_AGENTS = [
    # Core pipeline
    ("planner",      "Planner Agent"),
    ("builder",      "Builder Agent"),
    ("reviewer",     "Reviewer Agent"),
    ("tester",       "Tester Agent"),
    ("memory",       "Memory Agent"),
    # Specialist
    ("research",     "Research Agent"),
    ("code",         "Code Agent"),
    ("writer",       "Writer Agent"),
    ("analyst",      "Analyst Agent"),
    ("summarizer",   "Summarizer Agent"),
    ("translator",   "Translator Agent"),
    ("scheduler",    "Scheduler Agent"),
    ("qa",           "QA Agent"),
    ("data",         "Data Agent"),
    ("email",        "Email Agent"),
    # Expansion
    ("ceo",          "CEO Agent"),
    ("design",       "Design Agent"),
    ("content",      "Content Agent"),
    ("seo",          "SEO Agent"),
    ("support",      "Customer Support Agent"),
    ("compliance",   "Compliance Agent"),
    ("finance",      "Finance Agent"),
    ("travel",       "Travel Agent"),
    ("skill_builder","Skill Builder Agent"),
    ("plugin_review","Plugin Review Agent"),
    ("digital_twin", "Digital Twin Agent"),
    ("integration",  "Integration Agent"),
]


def test_agent_count():
    r = client.get("/api/agents/")
    assert r.status_code == 200
    data = r.json()
    assert data["total_available"] == 27, f"Expected 27 agents, got {data['total_available']}"


@pytest.mark.parametrize("agent_type,expected_name", ALL_AGENTS)
def test_agent_status(agent_type, expected_name):
    r = client.get(f"/api/agents/{agent_type}")
    assert r.status_code == 200, f"{agent_type}: {r.text}"
    d = r.json()
    assert d["agent_type"] == agent_type
    assert d["name"] == expected_name
    assert d["is_available"] is True


@pytest.mark.parametrize("agent_type,_", ALL_AGENTS[:5])  # core 5 — avoid timeout on all 27
def test_agent_execute(agent_type, _):
    r = client.post(f"/api/agents/{agent_type}/execute?task_input=Hello+test")
    assert r.status_code == 200, f"{agent_type}: {r.text}"
    d = r.json()
    assert "status" in d
    assert "output" in d or "error" in d


def test_sdk_list():
    r = client.get("/api/agents/sdk/list")
    assert r.status_code == 200
    d = r.json()
    assert "agents" in d
    assert isinstance(d["agents"], list)


def test_agent_not_found():
    r = client.get("/api/agents/nonexistent_xyz")
    assert r.status_code == 404
