"""
Chat endpoints
"""

import json
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse as _StreamingResponse
from pydantic import BaseModel
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


# ── Reply-style modes (/caveman, /ponytail) ──────────────────────────────────
class ModeRequest(BaseModel):
    mode: str
    enabled: bool


@router.get("/modes")
async def get_chat_modes():
    from app.services.chat_modes import get_modes, MODES
    state = get_modes()
    return {"modes": [
        {"name": k, "enabled": state.get(k, False), "description": MODES[k][0]}
        for k in MODES
    ]}


@router.post("/modes")
async def set_chat_mode(req: ModeRequest):
    from app.services.chat_modes import set_mode, MODES
    try:
        state = set_mode(req.mode, req.enabled)
    except KeyError:
        raise HTTPException(status_code=404,
                            detail=f"Unknown mode '{req.mode}'. Available: {', '.join(MODES)}")
    return {"modes": state}


class SharpenRequest(BaseModel):
    message: str
    rounds: int = 1
    ground: bool = True
    project_id: str = "default"


@router.post("/sharpen")
async def sharpen_message(req: SharpenRequest):
    """Answer with the active brain, then lift the answer via ILLIP's
    draft->critique->refine loop. Brain-agnostic: works with whatever provider
    is infused. Returns both the raw draft and the sharpened answer so the
    improvement is visible (and benchmarkable)."""
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    from app.services.sharpener import sharpen
    try:
        result = await sharpen(
            req.message,
            rounds=max(1, min(req.rounds, 3)),
            ground=req.ground,
            project_id=req.project_id,
        )
        return result.to_dict()
    except Exception as e:
        logger.error(f"Sharpen error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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

    # Cloud mode on → the real brain is OmniRoute, not the local model the router
    # nominally picked. Reflect that in the badge so it's honest.
    from app.providers import cloud_override_active
    if cloud_override_active():
        chosen_model = provider.model or "auto"
        routing["model"] = f"cloud: {chosen_model}"

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
        # Floor the context. The warmed cache can hold a tiny value (e.g. 2048,
        # left over from an earlier critical-pressure cap). System prompt + memory
        # + tool specs routinely hit ~5000 tokens, so trusting a stale small ctx
        # makes every request 400 then pay a reload. Floor to 8192 (what the Ghost
        # plan uses for ornith/qwen on this GPU anyway) unless genuinely critical.
        if routing["pressure"] != "critical":
            ctx_limit_use = max(ctx_limit_use, 8192)

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
            sys_content = system_prompt
            if memory_ctx:
                sys_content += f"\n\n{memory_ctx}"
            if search_ctx:
                sys_content += f"\n\n{search_ctx}"
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

        # Size num_ctx to FIT the actual prompt. A hardware "critical" cap can be
        # smaller than a prompt carrying web-search + memory (~3000+ tokens), which
        # makes Ollama 400 ("exceeds context size") and kills the answer mid-stream.
        # Estimate ~4 chars/token, add reply headroom, round up to a sane num_ctx.
        est_prompt = sum(len(m.content or "") for m in messages) // 4
        need = est_prompt + 1024  # room for the model's reply
        if need > ctx_limit_use:
            ctx_limit_use = 8192 if need > 4096 else 4096
            yield f"data: {json.dumps({'note': f'context resized to {ctx_limit_use} to fit the prompt'})}\n\n"

        registry = get_registry()
        tool_specs = registry.to_tool_specs()
        collected = []

        active_messages = list(messages)
        tool_findings = []  # (name, result) — folded into the fallback prompt as plain text
        run_tools = (not is_simple or request.force_tools or routing.get("needs_tools")) and tool_specs and hasattr(provider, "generate_with_tools")
        if run_tools:
            MAX_TOOL_ROUNDS = 3
            for _ in range(MAX_TOOL_ROUNDS):
                try:
                    content, tool_calls = await provider.generate_with_tools(
                        active_messages, tool_specs,
                        model=chosen_model, num_ctx=ctx_limit_use,
                    )
                except Exception as e:
                    logger.error(f"Tool phase failed: {e}")
                    yield f"data: {json.dumps({'error': str(e)[:300]})}\n\n"
                    content, tool_calls = "", []  # fall through to plain stream
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
                    tool_findings.append((call["name"], result))
                    yield f"data: {json.dumps({'tool_result': {'name': call['name'], 'result': result[:200]}})}\n\n"
                    active_messages.append(
                        Message(role="tool", content=result, timestamp=ts())
                    )

        if not collected:
            # Fallback to a plain stream. NEVER pass role="tool" messages here —
            # stream_response omits the tools field, and some model templates
            # (ornith) crash trying to render a bare tool message ("Unable to
            # generate parser for this template"). Fold real tool results into
            # a text block on the base messages instead, so the model answers
            # FROM the actual findings and can't fabricate a fake file/result.
            fallback_messages = list(messages)
            if tool_findings:
                findings_text = "\n\n".join(
                    f"[Tool '{name}' returned]:\n{result}" for name, result in tool_findings
                )
                # Fold findings into the LAST user message, not a trailing system
                # message. Ornith's chat template only accepts a system message at
                # the very start — a system message after the user turn crashes it
                # ("Unable to generate parser for this template"). Editing the user
                # turn keeps the standard system→user structure every template handles.
                for i in range(len(fallback_messages) - 1, -1, -1):
                    if fallback_messages[i].role == "user":
                        fallback_messages[i] = Message(
                            role="user",
                            content=(
                                fallback_messages[i].content
                                + "\n\n---\nTool results (answer using ONLY these — do not "
                                "invent files, paths, or contents beyond them):\n\n"
                                + findings_text
                            ),
                            timestamp=ts(),
                        )
                        break
            try:
                async for token in provider.stream_response(
                    fallback_messages, model=chosen_model, num_ctx=ctx_limit_use
                ):
                    collected.append(token)
                    yield f"data: {json.dumps({'token': token})}\n\n"
            except Exception as e:
                # Never die silently mid-answer — tell the user what happened.
                logger.error(f"Stream failed: {e}")
                warn = f"\n\n⚠️ Answer stopped: {str(e)[:180]}"
                collected.append(warn)
                yield f"data: {json.dumps({'token': warn})}\n\n"
                yield f"data: {json.dumps({'error': str(e)[:300]})}\n\n"

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
async def get_chat_history(limit: int = 50, project_id: str = "default"):
    """Get chat history"""
    try:
        chat_service = get_chat_service()
        history = chat_service.get_history(limit=limit, project_id=project_id)
        return {
            "messages": history,
            "count": len(history),
        }
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class MessageRef(BaseModel):
    role: str
    content: str
    project_id: str = "default"


@router.post("/message/delete")
async def delete_chat_message(ref: MessageRef):
    """Delete one message (the last one matching role+content) from history."""
    try:
        removed = get_chat_service().remove_message(ref.role, ref.content, ref.project_id)
        return {"removed": removed}
    except Exception as e:
        logger.error(f"Error deleting message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/message/rewind")
async def rewind_chat(ref: MessageRef):
    """Edit-and-resend support: drop the matching user message and everything
    after it. The client then sends the edited text as a fresh message."""
    try:
        count = get_chat_service().rewind_to(ref.content, ref.project_id)
        return {"removed": count}
    except Exception as e:
        logger.error(f"Error rewinding chat: {e}")
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
