"""
Async pub/sub event bus — agents publish results, others subscribe.
Zero external deps. Pure asyncio queues.
"""

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine
import uuid

from app.utils import logger


@dataclass
class AgentMessage:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""
    origin_agent: str = "unknown"
    trace_id: str = ""
    priority: int = 5          # 1=highest, 10=lowest
    payload: Any = None
    schema_version: str = "1.0"
    timestamp: float = field(default_factory=lambda: __import__("time").time())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "topic": self.topic,
            "origin_agent": self.origin_agent,
            "trace_id": self.trace_id,
            "priority": self.priority,
            "payload": self.payload,
            "schema_version": self.schema_version,
            "timestamp": self.timestamp,
        }


Handler = Callable[[AgentMessage], Coroutine]


class AgentBus:
    """
    Lightweight asyncio pub/sub bus.
    Agents call publish() to emit, subscribe() to listen.
    """

    def __init__(self):
        self._subs: dict[str, list[Handler]] = defaultdict(list)
        self._queue: asyncio.Queue[AgentMessage] = asyncio.Queue()
        self._running = False
        self._task: asyncio.Task | None = None

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._subs[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Handler) -> None:
        self._subs[topic] = [h for h in self._subs[topic] if h is not handler]

    async def publish(self, msg: AgentMessage) -> None:
        await self._queue.put(msg)

    async def publish_sync(self, topic: str, payload: Any, origin: str = "system", trace_id: str = "") -> str:
        msg = AgentMessage(topic=topic, origin_agent=origin, trace_id=trace_id or str(uuid.uuid4()), payload=payload)
        await self.publish(msg)
        return msg.id

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._dispatch_loop())
        logger.info("AgentBus started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()

    async def _dispatch_loop(self) -> None:
        while self._running:
            try:
                msg = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            handlers = self._subs.get(msg.topic, []) + self._subs.get("*", [])
            if handlers:
                await asyncio.gather(
                    *[h(msg) for h in handlers],
                    return_exceptions=True,
                )
            self._queue.task_done()


_bus: AgentBus | None = None


def get_bus() -> AgentBus:
    global _bus
    if _bus is None:
        _bus = AgentBus()
    return _bus
