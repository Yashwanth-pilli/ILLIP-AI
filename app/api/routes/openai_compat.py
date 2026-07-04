"""
OpenAI-compatible /v1/chat/completions endpoint.

Lets Continue.dev, curl, and any OpenAI SDK client use ILLIP AI as backend.
Streaming and non-streaming both supported.

Continue.dev config (~/.continue/config.json):
  {
    "models": [{
      "title": "ILLIP AI",
      "provider": "openai",
      "model": "illip",
      "apiBase": "http://localhost:8000/v1",
      "apiKey": "illip"
    }]
  }
"""

import json
import time
import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from app.core import Message
from app.providers import get_provider
from app.utils import logger, get_current_timestamp

router = APIRouter(prefix="/v1", tags=["openai-compat"])


class OAIMessage(BaseModel):
    role: str
    content: str


class OAIRequest(BaseModel):
    model: str = "illip"
    messages: list[OAIMessage]
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False


def _make_chunk(content: str, model: str, finish: bool = False) -> str:
    delta = {} if finish else {"role": "assistant", "content": content}
    chunk = {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": "stop" if finish else None}],
    }
    return f"data: {json.dumps(chunk)}\n\n"


@router.post("/chat/completions")
async def chat_completions(req: OAIRequest):
    provider = await get_provider()
    messages = [
        Message(role=m.role, content=m.content, timestamp=get_current_timestamp())
        for m in req.messages
    ]

    if req.stream:
        async def event_stream():
            try:
                # Generate full response then stream it token-by-token
                # (real token streaming needs provider-level support — added when Ollama stream is wired)
                response = await provider.safe_generate(
                    messages=messages,
                    temperature=req.temperature,
                    max_tokens=req.max_tokens,
                )
                # Stream word by word for a smooth UX
                words = response.split(" ")
                for i, word in enumerate(words):
                    token = word if i == 0 else " " + word
                    yield _make_chunk(token, req.model)
                yield _make_chunk("", req.model, finish=True)
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"OpenAI compat stream error: {e}")
                yield _make_chunk(f"Error: {e}", req.model, finish=True)
                yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    # Non-streaming
    try:
        response = await provider.safe_generate(
            messages=messages,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
    except Exception as e:
        logger.error(f"OpenAI compat error: {e}")
        response = f"Error: {e}"

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req.model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": response},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


@router.get("/models")
async def list_models():
    """OpenAI-style model list — Continue.dev calls this on startup."""
    return {
        "object": "list",
        "data": [
            {
                "id": "illip",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "illip",
            }
        ],
    }
