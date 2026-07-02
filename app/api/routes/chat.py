"""
Chat endpoints
"""

import json
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse as _StreamingResponse
from app.core import ChatRequest, ChatResponse, Message
from app.services import get_chat_service
from app.providers import get_provider
from app.utils import logger, get_current_timestamp


class StreamingResponse(_StreamingResponse):
    """Bypass anyio task group — crashes on Python 3.14 (current_task()=None)."""
    async def __call__(self, scope, receive, send):
        try:
            await self.stream_response(send)
        except OSError:
            from starlette.exceptions import ClientDisconnect
            raise ClientDisconnect()
        if self.background is not None:
            await self.background()

router = APIRouter(prefix="/chat", tags=["chat"])

_active_model: str = ""  # updated on each stream request

# Background task gate: track message count to rate-limit expensive background LLM tasks
_msg_count = 0


async def _reflexion_observe(question: str, response: str, base_url: str) -> None:
    """Fire-and-forget: score response quality, save high-quality patterns."""
    try:
        from app.agents.reflexion_agent import evaluate_response, _save_pattern
        score, reason = await evaluate_response(question, response, base_url)
        logger.info(f"Reflexion observe: score={score}/10 reason={reason!r}")
        _save_pattern(question, response, score, retry=False)
    except Exception as e:
        logger.debug(f"Reflexion observe error (non-critical): {e}")


async def _ball_extract(user_msg: str, assistant_msg: str) -> None:
    """Fire-and-forget: extract structured named memories from conversation turn."""
    try:
        from app.services.memory_ball import auto_extract
        await auto_extract(user_msg, assistant_msg)
    except Exception as e:
        logger.debug(f"Memory Ball extract (non-critical): {e}")


async def _kg_extract(user_msg: str, assistant_msg: str) -> None:
    """Fire-and-forget: extract knowledge graph triples from conversation turn."""
    try:
        from app.services.knowledge_graph import auto_extract
        await auto_extract(user_msg, assistant_msg)
    except Exception as e:
        logger.debug(f"KG extract (non-critical): {e}")


async def _learning_ingest(user_msg: str, assistant_msg: str) -> None:
    """Fire-and-forget: run chat exchange through swarm learning pipeline."""
    try:
        from app.learning.swarm import run_pipeline
        from app.learning.collector import save_approved_example
        example = {
            "source": "chat_auto",
            "messages": [
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": assistant_msg},
            ],
        }
        result = await run_pipeline(example)
        if result:
            save_approved_example(user_msg, assistant_msg, source="chat_auto")
    except Exception as e:
        logger.debug(f"Learning ingest failed (non-critical): {e}")


def get_active_model() -> str:
    from app.config import settings
    return _active_model or settings.ollama_model


@router.post("/", response_model=ChatResponse)
async def send_chat_message(request: ChatRequest) -> ChatResponse:
    try:
        if not request.message or not request.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")

        chat_service = get_chat_service()
        response = await chat_service.send_message(
            request.message,
            include_memory=request.include_memory
        )

        return ChatResponse(
            user_message=request.message,
            assistant_message=response,
            timestamp=get_current_timestamp()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def stream_chat_message(request: ChatRequest):
    """Stream chat response token-by-token via SSE with hardware-aware model routing."""
    global _active_model, _msg_count
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    from app.services.router_service import route
    from app.config import settings as _cfg

    # Route first — fast (regex + hardware read), no LLM
    routing = await route(request.message, ceiling_model=request.model)
    chosen_model = routing["model"]
    ctx_limit = routing["context_limit"]

    provider = await get_provider()
    # When Groq is active, replace Ollama model names with Groq model
    if hasattr(provider, 'model') and ":" in chosen_model:
        chosen_model = provider.model

    _active_model = chosen_model

    do_search = routing["needs_search"] or request.force_search
    project_id = request.project_id or "default"
    is_simple = routing["complexity"] == "simple"
    _msg_count += 1
    msg_n = _msg_count

    async def event_stream():
        # Yield routing immediately — user sees model + status with no delay
        yield f"data: {json.dumps({'routing': routing})}\n\n"

        # Heavy lifting runs here, inside the generator, after headers are sent
        from app.services.memory_qdrant import retrieve_memory, store_memory, format_memories_for_prompt
        from app.services.search_service import web_search, format_search_results
        from app.skills.registry import get_registry
        from app.hardware.context_manager import build_managed_context, managed_context_to_messages
        from app.utils import get_current_timestamp as ts
        from app.services.router_service import SMALL as _small_model
        from app.hardware.speed_optimizer import get_warmed_ctx
        from app.services.chat_service import _load_system_prompt

        chat_service = get_chat_service()
        ctx_limit_use = get_warmed_ctx(chosen_model, fallback=ctx_limit) if is_simple else ctx_limit

        # Run memory + optional search concurrently
        memories_task = asyncio.create_task(
            retrieve_memory(request.message, top_k=4, project_id=project_id)
        )
        search_task = asyncio.create_task(
            web_search(request.message, max_results=4)
        ) if do_search else None

        memories = await memories_task
        search_res = await search_task if search_task else []
        memory_ctx = format_memories_for_prompt(memories)
        search_ctx = format_search_results(search_res) if search_res else ""

        # Memory Ball context
        try:
            from app.services.memory_ball import search as ball_search, format_for_prompt as ball_fmt
            ball_hits = await asyncio.get_event_loop().run_in_executor(
                None, ball_search, request.message, None, 4
            )
            if ball_hits:
                ball_ctx = ball_fmt(ball_hits)
                memory_ctx = (memory_ctx + "\n\n" + ball_ctx).strip() if memory_ctx else ball_ctx
        except Exception:
            pass

        # Knowledge Graph context
        try:
            from app.services.knowledge_graph import search_nodes, format_for_prompt as kg_fmt
            loop = asyncio.get_event_loop()
            kg_nodes = await loop.run_in_executor(None, search_nodes, request.message, 3)
            if kg_nodes:
                kg_ctx = await loop.run_in_executor(None, kg_fmt, kg_nodes[0]["name"], 1)
                if kg_ctx:
                    memory_ctx = (memory_ctx + "\n\n" + kg_ctx).strip() if memory_ctx else kg_ctx
        except Exception:
            pass

        raw_history = chat_service._get_history(project_id)
        system_prompt = _load_system_prompt()

        if is_simple:
            recent = [{"role": m.role, "content": m.content} for m in raw_history[-8:]
                      if m.role in ("user", "assistant")]
            sys_content = system_prompt + (f"\n\n{memory_ctx}" if memory_ctx else "")
            messages = (
                [Message(role="system", content=sys_content, timestamp=ts())]
                + [Message(role=m["role"], content=m["content"], timestamp=ts()) for m in recent]
                + [Message(role="user", content=request.message, timestamp=ts())]
            )
        else:
            managed = await build_managed_context(
                full_history=raw_history,
                user_message=request.message,
                system_prompt=system_prompt,
                memory_ctx=memory_ctx,
                search_ctx=search_ctx,
                ollama_base_url=_cfg.ollama_base_url,
                small_model=_small_model,
            )
            messages = [
                Message(role=m["role"], content=m["content"], timestamp=ts())
                for m in managed_context_to_messages(managed)
            ]

        user_msg = Message(role="user", content=request.message, timestamp=ts())
        chat_service.append_message(user_msg, project_id)

        registry = get_registry()
        tool_specs = registry.to_tool_specs()
        collected = []

        active_messages = list(messages)
        run_tools = (not is_simple or request.force_tools) and tool_specs and hasattr(provider, "generate_with_tools")
        if run_tools:
            MAX_TOOL_ROUNDS = 3
            for _ in range(MAX_TOOL_ROUNDS):
                content, tool_calls = await provider.generate_with_tools(
                    active_messages, tool_specs,
                    model=chosen_model, num_ctx=ctx_limit_use,
                )
                if not tool_calls:
                    if content:
                        for word in content.split(" "):
                            token = word + " "
                            collected.append(token)
                            yield f"data: {json.dumps({'token': token})}\n\n"
                    break

                yield f"data: {json.dumps({'tool_calls': [c['name'] for c in tool_calls]})}\n\n"
                active_messages.append(
                    Message(role="assistant", content=content or "", timestamp=ts())
                )
                for call in tool_calls:
                    result = await registry.run(call["name"], call.get("arguments", {}))
                    yield f"data: {json.dumps({'tool_result': {'name': call['name'], 'result': result[:200]}})}\n\n"
                    active_messages.append(
                        Message(role="tool", content=result, timestamp=ts())
                    )
            else:
                active_messages = list(messages)

        if not collected:
            async for token in provider.stream_response(
                active_messages, model=chosen_model, num_ctx=ctx_limit_use
            ):
                collected.append(token)
                yield f"data: {json.dumps({'token': token})}\n\n"

        full = "".join(collected)
        chat_service.append_message(
            Message(role="assistant", content=full, timestamp=ts()), project_id
        )
        asyncio.create_task(
            store_memory(
                f"User: {request.message}\nAssistant: {full[:500]}",
                {"category": "chat", "complexity": routing["complexity"]},
                project_id=project_id,
            )
        )

        # Gate expensive background LLM tasks: every 5th message for extraction,
        # every 10th for learning — prevents background Ollama calls from blocking
        # the user's next request on the same instance.
        if msg_n % 5 == 0:
            asyncio.create_task(_ball_extract(request.message, full))
            asyncio.create_task(_kg_extract(request.message, full))
        if msg_n % 10 == 0:
            asyncio.create_task(_learning_ingest(request.message, full))
        # Reflexion intentionally disabled: it fires a full Ollama request after
        # every message and competes with the user's next query.

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/history")
async def get_chat_history(limit: int = 50):
    """Get chat history"""
    try:
        chat_service = get_chat_service()
        history = chat_service.get_history(limit=limit)
        return {
            "messages": history,
            "count": len(history),
        }
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/history")
async def clear_chat_history():
    """Clear all chat history"""
    try:
        chat_service = get_chat_service()
        chat_service.clear_history()
        return {"status": "cleared"}
    except Exception as e:
        logger.error(f"Error clearing history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
