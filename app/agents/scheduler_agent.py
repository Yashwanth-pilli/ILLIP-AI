"""
SchedulerAgent — asyncio-based recurring job runner.

Jobs: memory backup, knowledge graph cleanup, health snapshot.
Hardware-aware: skips heavy jobs when CPU/GPU stressed.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Callable, Awaitable
from uuid import uuid4

from app.utils import logger


@dataclass
class Job:
    id: str
    name: str
    interval_s: float
    fn: Callable[[], Awaitable[None]]
    last_run: float = 0.0
    run_count: int = 0
    last_error: str = ""
    enabled: bool = True
    skip_if_stressed: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "interval_s": self.interval_s,
            "last_run": self.last_run,
            "run_count": self.run_count,
            "last_error": self.last_error,
            "enabled": self.enabled,
            "skip_if_stressed": self.skip_if_stressed,
            "next_run_in": max(0, self.interval_s - (time.time() - self.last_run)) if self.last_run else 0,
        }


def _is_stressed() -> bool:
    """CPU > 85% or GPU mem > 90% → stressed."""
    try:
        import psutil
        if psutil.cpu_percent(interval=0.1) > 85:
            return True
    except Exception:
        pass
    try:
        import subprocess
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3
        )
        if r.returncode == 0:
            used, total = map(float, r.stdout.strip().split(","))
            if used / total > 0.90:
                return True
    except Exception:
        pass
    return False


class SchedulerAgent:
    name = "scheduler"

    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._running = False
        self._task: asyncio.Task | None = None

    def add_job(
        self,
        name: str,
        fn: Callable[[], Awaitable[None]],
        interval_s: float,
        skip_if_stressed: bool = False,
    ) -> str:
        jid = str(uuid4())
        self._jobs[jid] = Job(
            id=jid,
            name=name,
            interval_s=interval_s,
            fn=fn,
            skip_if_stressed=skip_if_stressed,
        )
        logger.info(f"Scheduler: job '{name}' added, interval={interval_s}s")
        return jid

    def remove_job(self, job_id: str) -> bool:
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False

    def set_enabled(self, job_id: str, enabled: bool) -> bool:
        if job_id in self._jobs:
            self._jobs[job_id].enabled = enabled
            return True
        return False

    def list_jobs(self) -> list[dict]:
        return [j.to_dict() for j in self._jobs.values()]

    async def run_job_now(self, job_id: str) -> bool:
        if job_id not in self._jobs:
            return False
        job = self._jobs[job_id]
        await self._exec(job)
        return True

    async def _exec(self, job: Job):
        try:
            await job.fn()
            job.last_run = time.time()
            job.run_count += 1
            job.last_error = ""
        except Exception as e:
            job.last_error = str(e)
            logger.warning(f"Scheduler job '{job.name}' failed: {e}")

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("SchedulerAgent started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    async def _loop(self):
        while self._running:
            now = time.time()
            stressed = _is_stressed()

            for job in list(self._jobs.values()):
                if not job.enabled:
                    continue
                if job.skip_if_stressed and stressed:
                    continue
                if now - job.last_run >= job.interval_s:
                    asyncio.create_task(self._exec(job))

            await asyncio.sleep(10)


# ── Built-in jobs ─────────────────────────────────────────────────────────────

async def _job_memory_backup():
    """Snapshot memory to data/backups/."""
    import json
    import datetime
    from pathlib import Path
    from app.services.memory_service import get_memory_service
    mem = get_memory_service()
    memories = await mem.list_all() if hasattr(mem, "list_all") else []
    out = Path("data/backups")
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    (out / f"memory_{stamp}.json").write_text(json.dumps(memories, indent=2))


async def _job_health_snapshot():
    """Write health metrics snapshot to data/health/."""
    import json
    import datetime
    from pathlib import Path
    try:
        import psutil
        snap = {
            "ts": datetime.datetime.now().isoformat(),
            "cpu_pct": psutil.cpu_percent(interval=0.5),
            "ram_pct": psutil.virtual_memory().percent,
            "disk_pct": psutil.disk_usage("/").percent,
        }
        out = Path("data/health")
        out.mkdir(parents=True, exist_ok=True)
        (out / "latest.json").write_text(json.dumps(snap))
    except Exception:
        pass


async def _job_kg_cleanup():
    """Remove orphaned knowledge graph nodes older than 7 days."""
    try:
        from app.services.knowledge_graph import get_kg
        kg = get_kg()
        if hasattr(kg, "cleanup_old_nodes"):
            await kg.cleanup_old_nodes(days=7)
    except Exception:
        pass


_scheduler: SchedulerAgent | None = None


def get_scheduler() -> SchedulerAgent:
    global _scheduler
    if _scheduler is None:
        _scheduler = SchedulerAgent()
        # Register default jobs
        _scheduler.add_job("memory_backup", _job_memory_backup, interval_s=3600)
        _scheduler.add_job("health_snapshot", _job_health_snapshot, interval_s=60)
        _scheduler.add_job("kg_cleanup", _job_kg_cleanup, interval_s=86400, skip_if_stressed=True)
    return _scheduler
