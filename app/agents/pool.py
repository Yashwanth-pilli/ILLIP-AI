"""
Parallel agent task pool.

Agents submit work via run() and get back a Future.
Multiple agents across multiple projects run concurrently — no blocking.

Usage:
    pool = get_pool()
    result = await pool.run("planner", planner_agent.plan, task="build X")
    # or fire-and-forget:
    await pool.spawn("memory", memory_agent.save, data=...)
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

from app.utils import logger


@dataclass
class AgentTask:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_name: str = ""
    status: str = "pending"     # pending | running | done | failed
    started_at: float | None = None
    finished_at: float | None = None
    result: Any = None
    error: str = ""
    trace_id: str = ""

    @property
    def duration_ms(self) -> float | None:
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at) * 1000
        return None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agent": self.agent_name,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "trace_id": self.trace_id,
        }


class AgentPool:
    """
    Runs agent coroutines in parallel asyncio tasks.
    Tracks all running tasks. No thread pool needed — pure async.
    """

    def __init__(self, max_concurrent: int = 20):
        self._tasks: dict[str, AgentTask] = {}
        self._max = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def run(
        self,
        agent_name: str,
        coro_fn: Callable[..., Coroutine],
        trace_id: str = "",
        **kwargs,
    ) -> Any:
        """Run coroutine and await result. Respects concurrency limit."""
        task_record = AgentTask(agent_name=agent_name, trace_id=trace_id or str(uuid.uuid4()))
        self._tasks[task_record.id] = task_record

        async with self._semaphore:
            task_record.status = "running"
            task_record.started_at = time.time()
            try:
                result = await coro_fn(**kwargs)
                task_record.result = result
                task_record.status = "done"
                return result
            except Exception as e:
                task_record.error = str(e)
                task_record.status = "failed"
                logger.error(f"AgentPool [{agent_name}] failed: {e}")
                raise
            finally:
                task_record.finished_at = time.time()

    async def spawn(
        self,
        agent_name: str,
        coro_fn: Callable[..., Coroutine],
        trace_id: str = "",
        **kwargs,
    ) -> str:
        """Fire-and-forget. Returns task_id immediately."""
        task_record = AgentTask(agent_name=agent_name, trace_id=trace_id or str(uuid.uuid4()))
        self._tasks[task_record.id] = task_record

        async def _run():
            async with self._semaphore:
                task_record.status = "running"
                task_record.started_at = time.time()
                try:
                    task_record.result = await coro_fn(**kwargs)
                    task_record.status = "done"
                except Exception as e:
                    task_record.error = str(e)
                    task_record.status = "failed"
                    logger.error(f"AgentPool spawn [{agent_name}] failed: {e}")
                finally:
                    task_record.finished_at = time.time()

        asyncio.create_task(_run())
        return task_record.id

    async def run_parallel(
        self,
        jobs: list[tuple[str, Callable, dict]],
        trace_id: str = "",
    ) -> list[Any]:
        """
        Run multiple (agent_name, coro_fn, kwargs) jobs in parallel.
        Returns list of results in same order. Exceptions returned, not raised.
        """
        tid = trace_id or str(uuid.uuid4())
        coros = [self.run(name, fn, trace_id=tid, **kw) for name, fn, kw in jobs]
        return await asyncio.gather(*coros, return_exceptions=True)

    def get_task(self, task_id: str) -> AgentTask | None:
        return self._tasks.get(task_id)

    def active_tasks(self) -> list[dict]:
        return [t.to_dict() for t in self._tasks.values() if t.status in ("pending", "running")]

    def all_tasks(self, limit: int = 50) -> list[dict]:
        recent = sorted(self._tasks.values(), key=lambda t: t.started_at or 0, reverse=True)
        return [t.to_dict() for t in recent[:limit]]

    def clear_done(self) -> int:
        done = [tid for tid, t in self._tasks.items() if t.status in ("done", "failed")]
        for tid in done:
            del self._tasks[tid]
        return len(done)


_pool: AgentPool | None = None


def get_pool() -> AgentPool:
    global _pool
    if _pool is None:
        _pool = AgentPool()
    return _pool
