"""Base class shared by all ILLIP AI agents."""

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any, List
from app.core import Message
from app.utils import logger, get_current_timestamp


_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    try:
        return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")
    except Exception:
        return ""


class BaseAgent(ABC):
    """Common execution wrapper for concrete agents."""

    def __init__(self, agent_type: str, name: str, prompt_file: Optional[str] = None):
        self.agent_type = agent_type
        self.name = name
        self.is_available = True
        self.task_count = 0
        self.last_activity = None
        self._system_prompt = _load_prompt(prompt_file) if prompt_file else ""

    async def _call_llm(self, task_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Call the LLM provider with tool-call loop. Agents can use any registered skill."""
        from app.providers import get_provider
        from app.skills.registry import get_registry

        messages: List[Message] = []
        ts = get_current_timestamp

        if self._system_prompt:
            messages.append(Message(role="system", content=self._system_prompt, timestamp=ts()))

        user_content = task_input
        if context:
            ctx_lines = "\n".join(f"- {k}: {v}" for k, v in context.items())
            user_content = f"{task_input}\n\nContext:\n{ctx_lines}"

        messages.append(Message(role="user", content=user_content, timestamp=ts()))

        provider = await get_provider()
        registry = get_registry()
        tool_specs = registry.to_tool_specs()

        # Tool-call loop — agent can invoke skills up to 3 rounds
        if tool_specs and hasattr(provider, "generate_with_tools"):
            for _ in range(3):
                content, tool_calls = await provider.generate_with_tools(
                    messages, tool_specs, temperature=0.7
                )
                if not tool_calls:
                    return content or ""
                # Execute tools, append results, continue
                messages.append(Message(role="assistant", content=content or "", timestamp=ts()))
                for call in tool_calls:
                    result = await registry.run(call["name"], call.get("arguments", {}))
                    logger.info(f"Agent {self.agent_type} used skill {call['name']}")
                    messages.append(Message(role="tool", content=result, timestamp=ts()))

        # Fallback: plain generate
        return await provider.safe_generate(messages=messages, temperature=0.7)

    @abstractmethod
    async def process(
        self,
        task_input: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        pass

    async def execute_task(
        self,
        task_input: str,
        context: Optional[Dict[str, Any]] = None,
        max_retries: int = 2,
    ) -> Dict[str, Any]:
        self.task_count += 1
        self.last_activity = get_current_timestamp()
        last_err: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                result = await self.process(task_input, context)
                return {
                    "status": "success",
                    "agent": self.agent_type,
                    "output": result,
                    "task_count": self.task_count,
                    "attempts": attempt + 1,
                }
            except Exception as e:
                last_err = e
                if attempt < max_retries:
                    wait = 2 ** attempt  # 1s, 2s
                    logger.warning(f"Agent {self.agent_type} attempt {attempt+1} failed ({e}), retrying in {wait}s")
                    await asyncio.sleep(wait)
        logger.error(f"Agent {self.agent_type} failed after {max_retries+1} attempts: {last_err}")
        return {
            "status": "error",
            "agent": self.agent_type,
            "error": str(last_err),
            "task_count": self.task_count,
            "attempts": max_retries + 1,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_type": self.agent_type,
            "name": self.name,
            "is_available": self.is_available,
            "task_count": self.task_count,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
        }
