"""
Reminders API — recurring instructions ("daily 09:00: one LeetCode problem, solve it").
Checked every ~60s by the SchedulerAgent (see app/services/reminder_service.py);
results land in the reminder's project chat history.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.reminder_service import (
    create_reminder, list_reminders, delete_reminder, run_now,
)

router = APIRouter(prefix="/reminders", tags=["reminders"])


class CreateReminderRequest(BaseModel):
    instruction: str
    time_of_day: str  # "HH:MM", 24-hour, local time
    project_id: str = "default"
    use_agent: bool = False


@router.get("/")
async def list_all_reminders():
    return {"reminders": list_reminders()}


@router.post("/")
async def create_new_reminder(req: CreateReminderRequest):
    if not req.instruction.strip():
        raise HTTPException(status_code=400, detail="instruction cannot be empty")
    try:
        reminder = create_reminder(
            req.instruction.strip(), req.time_of_day.strip(), req.project_id, req.use_agent
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="time_of_day must be 'HH:MM' (24-hour)")
    return {
        "reminder": reminder,
        "report_md": (
            f"⏰ **Reminder set** — every day at **{reminder['time_of_day']}**, "
            f"I'll run: \"{reminder['instruction']}\"\n\n"
            f"Result lands in this space's chat. Delete anytime with `/unremind {reminder['id']}`."
        ),
    }


@router.delete("/{reminder_id}")
async def delete_reminder_endpoint(reminder_id: str):
    if not delete_reminder(reminder_id):
        raise HTTPException(status_code=404, detail=f"Reminder '{reminder_id}' not found.")
    return {"status": "deleted", "id": reminder_id}


@router.post("/{reminder_id}/run")
async def run_reminder_now(reminder_id: str):
    try:
        result = await run_now(reminder_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"result": result, "report_md": result}
