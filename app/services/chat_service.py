"""
Chat service — project-scoped multi-turn chat with persistent history.
"""

from pathlib import Path
from typing import Optional, List
from app.core import Message
from app.providers import get_provider
from app.utils import logger, get_current_timestamp
from app.services.project_service import (
    DEFAULT_PROJECT,
    history_load,
    history_append,
    history_clear,
    history_remove,
    history_rewind,
    ensure_default_project,
)

_SYSTEM_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "system_prompt.md"


def _load_system_prompt() -> str:
    try:
        base = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        base = "You are ILLIP, a local-first AI assistant."
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Fable-style work method (editable via data/methodology.md), then
    # user-toggled reply-style modes (/caveman, /ponytail).
    from app.services.methodology import chat_method
    from app.services.chat_modes import prompt_addendum
    return f"Current date and time: {now}\n\n{base}{chat_method()}{prompt_addendum()}"


class ChatService:
    """
    Project-scoped chat service.
    In-memory history is per-project; disk history persists across restarts.
    """

    def __init__(self):
        ensure_default_project()
        # In-memory cache: project_id -> list[Message]
        self._histories: dict[str, List[Message]] = {}

    def _get_history(self, project_id: str) -> List[Message]:
        if project_id not in self._histories:
            # Load persisted history from disk
            saved = history_load(project_id, limit=50)
            self._histories[project_id] = [
                Message(role=m["role"], content=m["content"],
                        timestamp=get_current_timestamp())
                for m in saved
            ]
        return self._histories[project_id]

    # Keep backward-compat property used by older routes
    @property
    def history(self) -> List[Message]:
        return self._get_history(DEFAULT_PROJECT)

    @history.setter
    def history(self, value: List[Message]):
        self._histories[DEFAULT_PROJECT] = value

    def _build_messages(self, project_id: str = DEFAULT_PROJECT) -> List[Message]:
        system_msg = Message(
            role="system",
            content=_load_system_prompt(),
            timestamp=get_current_timestamp(),
        )
        return [system_msg] + self._get_history(project_id)

    def append_message(self, msg: Message, project_id: str = DEFAULT_PROJECT) -> None:
        self._get_history(project_id).append(msg)
        history_append(project_id, msg.role, msg.content)

    def remove_message(self, role: str, content: str, project_id: str = DEFAULT_PROJECT) -> bool:
        """Delete the last matching message from memory + disk."""
        hist = self._get_history(project_id)
        for i in range(len(hist) - 1, -1, -1):
            if hist[i].role == role and hist[i].content == content:
                del hist[i]
                break
        return history_remove(project_id, role, content)

    def rewind_to(self, content: str, project_id: str = DEFAULT_PROJECT) -> int:
        """Edit-and-resend: drop the last user message matching content and
        everything after it, from memory + disk."""
        hist = self._get_history(project_id)
        for i in range(len(hist) - 1, -1, -1):
            if hist[i].role == "user" and hist[i].content == content:
                del hist[i:]
                break
        return history_rewind(project_id, content)

    async def send_message(
        self,
        user_message: str,
        include_memory: bool = True,
        project_id: str = DEFAULT_PROJECT,
    ) -> str:
        try:
            user_msg = Message(role="user", content=user_message,
                               timestamp=get_current_timestamp())
            self.append_message(user_msg, project_id)

            provider = await get_provider()
            response = await provider.safe_generate(
                messages=self._build_messages(project_id),
                temperature=0.7,
            )

            assistant_msg = Message(role="assistant", content=response,
                                    timestamp=get_current_timestamp())
            self.append_message(assistant_msg, project_id)
            logger.info(f"Chat processed (project={project_id})")
            return response
        except Exception as e:
            logger.error(f"Chat service error: {e}")
            return f"Error: {str(e)}"

    def get_history(self, limit: Optional[int] = None,
                    project_id: str = DEFAULT_PROJECT) -> List[dict]:
        h = self._get_history(project_id)
        if limit:
            h = h[-limit:]
        return [m.to_dict() for m in h]

    def clear_history(self, project_id: str = DEFAULT_PROJECT):
        self._histories[project_id] = []
        history_clear(project_id)
        logger.info(f"Chat history cleared (project={project_id})")

    def reload_system_prompt(self):
        pass  # system prompt loaded fresh on every _build_messages call


_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service


class _LLMClient:
    """Thin wrapper: agents call await llm.complete(prompt, system=None) -> str."""
    async def complete(self, prompt: str, system: str | None = None) -> str:
        provider = await get_provider()
        msgs: List[Message] = []
        if system:
            msgs.append(Message(role="system", content=system))
        msgs.append(Message(role="user", content=prompt))
        return await provider.safe_generate(messages=msgs, temperature=0.3)


def get_llm() -> _LLMClient:
    return _LLMClient()
