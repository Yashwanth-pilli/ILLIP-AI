"""
Tests for the release features: file_ops (move/copy), chat modes
(caveman/ponytail), gstack git helper, and guardian /getsafe.
"""

import os
import subprocess
from pathlib import Path

import pytest


# ── file_ops: move/copy with safety guards ───────────────────────────────────

@pytest.mark.asyncio
async def test_move_dry_run_does_not_move(tmp_path):
    from app.skills.builtin.file_ops_skill import MoveFileSkill
    src = tmp_path / "a.txt"; src.write_text("hi")
    dst = tmp_path / "sub"; dst.mkdir()
    r = await MoveFileSkill().execute(source=str(src), destination=str(dst))
    assert "PLAN" in r and src.exists(), "dry run must not move"


@pytest.mark.asyncio
async def test_move_real_and_verifies(tmp_path):
    from app.skills.builtin.file_ops_skill import MoveFileSkill
    src = tmp_path / "a.txt"; src.write_text("payload")
    dst = tmp_path / "sub"; dst.mkdir()
    r = await MoveFileSkill().execute(source=str(src), destination=str(dst), confirm=True)
    assert "MOVED" in r
    assert not src.exists()
    assert (dst / "a.txt").read_text() == "payload"


@pytest.mark.asyncio
async def test_move_refuses_system_path(tmp_path):
    from app.skills.builtin.file_ops_skill import MoveFileSkill
    sysroot = os.environ.get("SystemRoot", r"C:\Windows") if os.name == "nt" else "/etc"
    r = await MoveFileSkill().execute(source=sysroot, destination=str(tmp_path), confirm=True)
    assert "REFUSED" in r


@pytest.mark.asyncio
async def test_move_refuses_credential(tmp_path):
    from app.skills.builtin.file_ops_skill import MoveFileSkill
    env = tmp_path / ".env"; env.write_text("SECRET=1")
    r = await MoveFileSkill().execute(source=str(env), destination=str(tmp_path / "out"), confirm=True)
    assert "REFUSED" in r and env.exists()


@pytest.mark.asyncio
async def test_move_no_overwrite_without_flag(tmp_path):
    from app.skills.builtin.file_ops_skill import MoveFileSkill
    src = tmp_path / "a.txt"; src.write_text("new")
    existing = tmp_path / "dst"; existing.mkdir()
    (existing / "a.txt").write_text("old")
    r = await MoveFileSkill().execute(source=str(src), destination=str(existing), confirm=True)
    assert "already exists" in r and src.exists()


@pytest.mark.asyncio
async def test_copy_keeps_original(tmp_path):
    from app.skills.builtin.file_ops_skill import CopyFileSkill
    src = tmp_path / "a.txt"; src.write_text("keep")
    r = await CopyFileSkill().execute(source=str(src), destination=str(tmp_path / "b.txt"), confirm=True)
    assert "COPIED" in r and src.exists() and (tmp_path / "b.txt").read_text() == "keep"


# ── chat modes ────────────────────────────────────────────────────────────────

def test_chat_modes_toggle_and_addendum(tmp_path, monkeypatch):
    import app.services.chat_modes as cm
    monkeypatch.setattr(cm, "_STATE_PATH", tmp_path / "modes.json")
    assert cm.prompt_addendum() == ""
    cm.set_mode("caveman", True)
    assert "CAVEMAN" in cm.prompt_addendum()
    cm.set_mode("ponytail", True)
    add = cm.prompt_addendum()
    assert "CAVEMAN" in add and "PONYTAIL" in add
    cm.set_mode("caveman", False)
    assert "CAVEMAN" not in cm.prompt_addendum()


def test_chat_modes_unknown_raises(tmp_path, monkeypatch):
    import app.services.chat_modes as cm
    monkeypatch.setattr(cm, "_STATE_PATH", tmp_path / "modes.json")
    with pytest.raises(KeyError):
        cm.set_mode("bogus", True)


# ── gstack ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gstack_non_repo(tmp_path):
    from app.api.routes.gstack import gstack_report
    r = await gstack_report(str(tmp_path))
    assert "not a git repository" in r


@pytest.mark.asyncio
async def test_gstack_clean_repo(tmp_path):
    from app.api.routes.gstack import gstack_report
    try:
        subprocess.run(["git", "-C", str(tmp_path), "init"], check=True,
                       capture_output=True, timeout=15)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("git not available")
    r = await gstack_report(str(tmp_path))
    assert "gstack" in r and "clean" in r.lower()


# ── guardian getsafe ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_getsafe_empty_query():
    from app.services.file_guardian import get_safe_advice
    r = await get_safe_advice("")
    assert "download" in r.lower()


# ── gstack skill (agent-callable wrapper) ─────────────────────────────────────

@pytest.mark.asyncio
async def test_gstack_skill_wraps_report(tmp_path):
    from app.skills.builtin.gstack_skill import GstackSkill
    r = await GstackSkill().execute(path=str(tmp_path))
    assert "not a git repository" in r


def test_gstack_skill_registered():
    from app.skills.registry import get_registry
    assert get_registry().get("git_status") is not None


# ── download auto-watch ───────────────────────────────────────────────────────

def test_download_watch_primes_then_alerts(tmp_path, monkeypatch):
    import app.services.download_watch as dw
    # Point the watcher at a temp "Downloads" and reset its state.
    monkeypatch.setattr(dw, "_downloads_dir", lambda: tmp_path)
    monkeypatch.setattr(dw, "_seen", set())
    monkeypatch.setattr(dw, "_alerts", [])
    monkeypatch.setattr(dw, "_primed", False)
    monkeypatch.setattr(dw, "_SETTLE_SECONDS", 0)

    # A disguised executable: report.pdf.exe
    bad = tmp_path / "report.pdf.exe"
    bad.write_bytes(b"MZ\x00\x00fake")

    dw._scan_new_files()          # prime pass — records backlog, no alerts
    dw._primed = True
    primed_alerts = dw.drain_alerts()
    # Priming must never alert on the pre-existing backlog file.
    assert not any(a["file"] == "report.pdf.exe" for a in primed_alerts)

    # New risky file arrives after priming.
    bad2 = tmp_path / "invoice.pdf.exe"
    bad2.write_bytes(b"MZ\x00\x00fake")
    dw._scan_new_files()
    invoice = [a for a in dw.drain_alerts() if a["file"] == "invoice.pdf.exe"]
    assert invoice and invoice[0]["level"] == "danger"

    # Re-scanning must not re-alert the same file (it's now in _seen).
    dw._scan_new_files()
    assert not any(a["file"] == "invoice.pdf.exe" for a in dw.drain_alerts())


def test_download_watch_skips_partial(tmp_path, monkeypatch):
    import app.services.download_watch as dw
    monkeypatch.setattr(dw, "_downloads_dir", lambda: tmp_path)
    monkeypatch.setattr(dw, "_seen", set())
    monkeypatch.setattr(dw, "_alerts", [])
    monkeypatch.setattr(dw, "_primed", True)
    monkeypatch.setattr(dw, "_SETTLE_SECONDS", 0)
    part = tmp_path / "game.exe.crdownload"
    part.write_bytes(b"MZ\x00\x00 still downloading")
    dw._scan_new_files()
    assert dw.drain_alerts() == []   # partial download ignored
