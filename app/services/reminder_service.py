"""
Reminder service — user-defined recurring instructions ("daily 09:00: one LeetCode
problem, solve it"). Checked once a minute by the SchedulerAgent; due reminders run
through the normal chat pipeline (or the agent loop for coding/agentic tasks) and the
result lands in that reminder's project chat history, same as if the user had typed it.

Structure on disk: data/reminders.json — list of reminder dicts.
"""

import json
import os
import uuid
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.config import settings
from app.utils import logger, get_current_timestamp

_write_lock = threading.Lock()


def _path() -> Path:
    p = settings.get_data_path() / "reminders.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _read() -> list[dict]:
    p = _path()
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def _write(reminders: list[dict]) -> None:
    p = _path()
    payload = json.dumps(reminders, indent=2, ensure_ascii=False)
    tmp = p.with_suffix(p.suffix + f".tmp{os.getpid()}")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)


def create_reminder(
    instruction: str,
    time_of_day: str,
    project_id: str = "default",
    use_agent: bool = False,
) -> dict:
    """time_of_day: 'HH:MM' 24-hour, local time. use_agent: run through the
    code-agent loop (for coding/multi-step tasks) instead of a plain chat reply."""
    datetime.strptime(time_of_day, "%H:%M")  # raises ValueError if malformed
    reminder = {
        "id": str(uuid.uuid4())[:8],
        "instruction": instruction,
        "time_of_day": time_of_day,
        "project_id": project_id,
        "use_agent": use_agent,
        "enabled": True,
        "last_run_date": "",
        "created_at": get_current_timestamp().isoformat(),
    }
    with _write_lock:
        reminders = _read()
        reminders.append(reminder)
        _write(reminders)
    logger.info(f"Reminder created: {reminder['id']} '{instruction}' @ {time_of_day}")
    return reminder


def list_reminders() -> list[dict]:
    return _read()


def delete_reminder(reminder_id: str) -> bool:
    with _write_lock:
        reminders = _read()
        kept = [r for r in reminders if r["id"] != reminder_id]
        if len(kept) == len(reminders):
            return False
        _write(kept)
    logger.info(f"Reminder deleted: {reminder_id}")
    return True


def get_reminder(reminder_id: str) -> Optional[dict]:
    for r in _read():
        if r["id"] == reminder_id:
            return r
    return None


def _mark_ran(reminder_id: str, date_str: str) -> None:
    with _write_lock:
        reminders = _read()
        for r in reminders:
            if r["id"] == reminder_id:
                r["last_run_date"] = date_str
        _write(reminders)


async def _execute(reminder: dict) -> str:
    """Run the reminder's instruction, store result in its project's chat history."""
    from app.services.chat_service import get_chat_service
    from app.core import Message

    instruction = reminder["instruction"]
    project_id = reminder.get("project_id", "default")
    chat_service = get_chat_service()

    if reminder.get("use_agent"):
        from app.services.agent_orchestrator import run_task_loop_stream
        last_result = ""
        async for event in run_task_loop_stream(instruction):
            if event.get("type") == "final":
                last_result = event.get("result", "") or last_result
        result = last_result or "(agent loop produced no final result)"
        chat_service.append_message(
            Message(role="user", content=f"⏰ Reminder: {instruction}", timestamp=get_current_timestamp()),
            project_id,
        )
        chat_service.append_message(
            Message(role="assistant", content=result, timestamp=get_current_timestamp()),
            project_id,
        )
        return result
    else:
        return await chat_service.send_message(
            f"⏰ Reminder: {instruction}", project_id=project_id
        )


async def check_due_reminders() -> None:
    """Called every ~60s by SchedulerAgent. Runs any reminder whose time_of_day has
    arrived and hasn't already run today."""
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    now_hm = now.strftime("%H:%M")

    for reminder in _read():
        if not reminder.get("enabled", True):
            continue
        if reminder.get("last_run_date") == today:
            continue
        if reminder.get("time_of_day") != now_hm:
            continue
        _mark_ran(reminder["id"], today)  # mark first — a slow/failing run must not fire twice
        try:
            await _execute(reminder)
            logger.info(f"Reminder '{reminder['id']}' ran: {reminder['instruction'][:60]}")
        except Exception as e:
            logger.warning(f"Reminder '{reminder['id']}' failed: {e}")


async def run_now(reminder_id: str) -> str:
    """Manual trigger (testing / 'do it now' button) — does not affect last_run_date."""
    reminder = get_reminder(reminder_id)
    if not reminder:
        raise ValueError(f"Reminder '{reminder_id}' not found.")
    return await _execute(reminder)
