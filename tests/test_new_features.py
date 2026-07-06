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
    sysroot = os.environ.get("SystemRoot", r"C:\Windows")
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
