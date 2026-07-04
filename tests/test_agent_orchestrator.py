"""Agent orchestrator tests — plan parsing + live-stream endpoint shape."""

from fastapi.testclient import TestClient
from app.main import app
from app.services.agent_orchestrator import parse_plan


client = TestClient(app)
_AVAIL = {"research", "builder", "reviewer", "code", "writer"}


def test_parse_plan_json():
    steps = parse_plan('[{"agent":"research","task":"find X"},{"agent":"coder","task":"write Y"}]', _AVAIL)
    assert len(steps) == 2
    assert steps[0]["agent"] == "research"
    assert steps[1]["agent"] == "code"  # "coder" aliased to code


def test_parse_plan_numbered_fallback():
    steps = parse_plan("1. [research] gather data\n2. build the thing", _AVAIL)
    assert steps[0]["agent"] == "research"
    assert len(steps) == 2


def test_parse_plan_always_returns_step():
    steps = parse_plan("garbage with no structure", _AVAIL)
    assert len(steps) >= 1


def test_agents_run_stream_events():
    """The SSE endpoint emits a plan and terminates with end."""
    with client.stream("GET", "/api/agents/run/stream", params={"task": "say hello"}) as r:
        assert r.status_code == 200
        types = []
        for line in r.iter_lines():
            if line and line.startswith("data: "):
                import json
                try:
                    types.append(json.loads(line[6:]).get("type"))
                except Exception:
                    pass
                if types and types[-1] == "end":
                    break
        assert "plan" in types
        assert "end" in types
