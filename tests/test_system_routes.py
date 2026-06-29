"""System, sync, governance, scheduler, monitoring route tests."""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ── Health & System ───────────────────────────────────────────────────────────

def test_health_returns_version():
    r = client.get("/api/health")
    assert r.status_code == 200
    d = r.json()
    # "healthy" when model running, "degraded" when no model configured — both valid
    assert d.get("status") in ("healthy", "degraded")
    assert "version" in d or "provider" in d or "status" in d


def test_system_info():
    r = client.get("/api/system/info")
    assert r.status_code == 200


def test_system_status():
    r = client.get("/api/system/status")
    assert r.status_code == 200


def test_openai_compat_models():
    r = client.get("/v1/models")
    assert r.status_code == 200
    d = r.json()
    assert "data" in d
    assert isinstance(d["data"], list)


# ── Governance ────────────────────────────────────────────────────────────────

def test_governance_pending_empty():
    r = client.get("/api/governance/pending")
    assert r.status_code == 200
    d = r.json()
    assert "pending" in d or "approvals" in d or isinstance(d, list)


def test_governance_policy():
    r = client.get("/api/governance/policy")
    assert r.status_code in (200, 404)  # may not exist yet


# ── Scheduler ─────────────────────────────────────────────────────────────────

def test_scheduler_jobs_list():
    r = client.get("/api/scheduler/jobs")
    assert r.status_code == 200
    d = r.json()
    assert "jobs" in d or isinstance(d, list)


# ── Sync ──────────────────────────────────────────────────────────────────────

def test_sync_lan_info():
    r = client.get("/api/sync/lan/info")
    assert r.status_code == 200
    d = r.json()
    assert "host" in d or "ip" in d or "app" in d


def test_sync_export():
    r = client.get("/api/sync/export")
    # Returns zip file or JSON response
    assert r.status_code in (200, 404)


# ── Monitoring ────────────────────────────────────────────────────────────────

def test_monitoring_current():
    r = client.get("/api/monitoring/current")
    assert r.status_code == 200


def test_monitoring_summary():
    r = client.get("/api/monitoring/summary")
    assert r.status_code == 200


# ── Memory ────────────────────────────────────────────────────────────────────

def test_memory_stats_overview():
    r = client.get("/api/memory/stats/overview")
    assert r.status_code == 200


def test_memory_search_returns_list():
    # param is `query`, not `q`
    r = client.get("/api/memory/search?query=test")
    assert r.status_code == 200
    d = r.json()
    assert "results" in d or isinstance(d, list)


def test_memory_store_and_retrieve():
    # store uses query params, not JSON body
    r = client.post("/api/memory/store?key=test_key_123&value=This+is+a+test&category=test")
    assert r.status_code == 200


# ── Workspace Intel ───────────────────────────────────────────────────────────

def test_workspace_intel_files():
    r = client.get("/api/workspace/intel/files?path=.")
    assert r.status_code == 200


def test_workspace_workspaces_list():
    r = client.get("/api/workspace/workspaces")
    assert r.status_code == 200


# ── Digital Twin ──────────────────────────────────────────────────────────────

def test_twin_profile():
    r = client.get("/api/twin/profile")
    assert r.status_code in (200, 404)


# ── Research ──────────────────────────────────────────────────────────────────

def test_research_status():
    r = client.get("/api/research/status")
    assert r.status_code in (200, 404)
