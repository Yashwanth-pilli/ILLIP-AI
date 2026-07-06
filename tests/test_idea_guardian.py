"""Tests for Idea Journey vault + File Guardian heuristics (no LLM, no network)."""

import json
import zipfile

import pytest

from app.services import idea_journey
from app.services.file_guardian import collect_findings, _sha256


# ── Idea vault ────────────────────────────────────────────────────────────────

def test_vault_store_and_list(tmp_path, monkeypatch):
    monkeypatch.setattr(idea_journey, "_VAULT_DIR", tmp_path / "vault")
    entry = idea_journey.vault_store("solar-powered water purifier for villages", "p1")
    assert len(entry["sha256"]) == 64
    assert entry["timestamp"]
    entries = idea_journey.vault_list()
    assert len(entries) == 1
    assert entries[0]["idea"].startswith("solar-powered")


def test_extract_json_from_prose():
    raw = 'Sure! Here it is:\n```json\n{"field": "agritech", "queries": ["a", "b"]}\n```'
    data = idea_journey._extract_json(raw)
    assert data == {"field": "agritech", "queries": ["a", "b"]}
    assert idea_journey._extract_json("no json here") is None


# ── Guardian heuristics ───────────────────────────────────────────────────────

def test_double_extension_flagged(tmp_path):
    bad = tmp_path / "invoice.pdf.exe"
    bad.write_bytes(b"MZ" + b"\x00" * 64)
    findings, files = collect_findings(bad)
    assert len(files) == 1
    assert any(f["level"] == "danger" and "DOUBLE EXTENSION" in f["message"] for f in findings)


def test_disguised_executable_flagged(tmp_path):
    # Real MZ executable named like a video file.
    fake = tmp_path / "movie.mp4"
    fake.write_bytes(b"MZ" + b"\x00" * 64)
    findings, _ = collect_findings(fake)
    assert any(f["level"] == "danger" and "Windows executable" in f["message"] for f in findings)


def test_plain_exe_only_warns(tmp_path):
    installer = tmp_path / "setup.exe"
    installer.write_bytes(b"MZ" + b"\x00" * 64)
    findings, _ = collect_findings(installer)
    levels = {f["level"] for f in findings}
    assert "warn" in levels and "danger" not in levels


def test_clean_text_file_no_findings(tmp_path):
    ok = tmp_path / "notes.txt"
    ok.write_text("hello world")
    findings, _ = collect_findings(ok)
    assert findings == []


def test_zip_with_autorun_and_double_ext(tmp_path):
    z = tmp_path / "game_repack.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("autorun.inf", "[autorun]")
        zf.writestr("crack/keygen.jpg.exe", "MZ")
        zf.writestr("readme.txt", "install notes")
    findings, _ = collect_findings(z)
    msgs = " | ".join(f["message"] for f in findings)
    assert "autorun.inf" in msgs
    assert "keygen.jpg.exe" in msgs
    assert any(f["level"] == "danger" for f in findings)


def test_folder_scan(tmp_path):
    (tmp_path / "a.txt").write_text("fine")
    (tmp_path / "b.pdf.scr").write_bytes(b"MZ\x00")
    findings, files = collect_findings(tmp_path)
    assert len(files) == 2
    assert any(f["level"] == "danger" for f in findings)


def test_sha256(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"illip")
    import hashlib
    assert _sha256(f) == hashlib.sha256(b"illip").hexdigest()


# ── Routes registered ─────────────────────────────────────────────────────────

def test_routes_registered():
    from app.api.routes import idea, guardian
    idea_paths = {r.path for r in idea.router.routes}
    assert idea_paths == {"/idea/journey", "/idea/stuck", "/idea/opportunities", "/idea/vault"}
    guardian_paths = {r.path for r in guardian.router.routes}
    assert guardian_paths == {"/guardian/scan", "/guardian/getsafe"}
    # and both are wired into the api module (import side effect registers them)
    import app.api as api_module
    src = open(api_module.__file__, encoding="utf-8").read()
    assert "idea.router" in src and "guardian.router" in src


def test_scan_skill_registered():
    import app.skills  # noqa: F401 — registration side effect
    from app.skills.registry import get_registry
    assert get_registry().get("scan_file") is not None
