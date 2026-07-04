"""Self-heal + heal endpoint tests."""

from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_heal_endpoint_healthy():
    """Heal returns a structured result and never errors on a healthy system."""
    r = client.post("/api/system/doctor/heal")
    assert r.status_code == 200
    d = r.json()
    assert "fixed" in d
    assert "message" in d
    assert isinstance(d["fixed"], list)


def test_action_ring_buffer_caps():
    from app.services.self_heal import _record, recent_actions, _actions
    _actions.clear()
    for i in range(30):
        _record(f"x{i}")
    assert len(recent_actions()) == 20
    assert recent_actions()[-1]["action"] == "x29"


def test_doctor_includes_heal_status():
    r = client.get("/api/system/doctor")
    assert r.status_code == 200
    assert "self-healing is active" in r.json()["report_md"].lower()
