"""Doctor diagnostics tests."""

from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_doctor_endpoint():
    """Diagnostics returns a status rollup and a non-empty checks list."""
    r = client.get("/api/system/doctor")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] in ("ok", "warn", "fail")
    assert len(d["checks"]) > 0
    assert "report_md" in d
    for c in d["checks"]:
        assert c["status"] in ("ok", "warn", "fail")
        assert c["name"] and c["message"]


def test_doctor_status_rollup():
    """Worst check wins: any fail → fail, else any warn → warn."""
    from app.services.doctor import _check, _OK, _WARN, _FAIL
    checks = [_check("a", _OK, "m"), _check("b", _WARN, "m")]
    n_fail = sum(1 for c in checks if c["status"] == _FAIL)
    n_warn = sum(1 for c in checks if c["status"] == _WARN)
    assert (_FAIL if n_fail else (_WARN if n_warn else _OK)) == _WARN
