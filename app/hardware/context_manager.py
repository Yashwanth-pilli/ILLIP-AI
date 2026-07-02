"""
Context Manager — GTA-style streaming context.

Like GTA map: only active zone loads. Old zones compress to summary.
70B model only sees: system + summary + last 5 turns + current message.
Never overloaded. Never crashes. Always fast.

Pipeline:
  full history → [compressor] → summary + recent window → 70B
                               ^                          ^
                          3B does this fast          70B only sees this
"""

import asyncio
from dataclasses import dataclass
from app.utils import logger

# Token budget (approximate — 1 word ≈ 1.3 tokens)
# Sized for 8192 ctx window on RTX 4060 8GB with qwen2.5:7b
_BUDGET = {
    "system":   800,   # system prompt
    "summary":  600,   # compressed old history
    "memory":   400,   # Qdrant retrieved memories
    "search":  1000,   # web search results
    "history": 1500,   # last N raw turns
    "message": 2700,   # current user message — generous: may carry attached document text
}
TOTAL_SAFE_BUDGET = sum(_BUDGET.values())   # ~6000 tokens — fits 8192 ctx

# Keep last N turns raw; everything older gets summarized
_RAW_TURNS = 8


def _count_tokens(text: str) -> int:
    """Rough token count: words * 1.3."""
    return int(len(text.split()) * 1.3)


def _truncate(text: str, max_tokens: int) -> str:
    """Hard-truncate text to fit token budget."""
    words = text.split()
    limit = int(max_tokens / 1.3)
    if len(words) <= limit:
        return text
    return " ".join(words[:limit]) + " [...]"


@dataclass
class ManagedContext:
    system_prompt: str
    summary: str           # compressed old history
    recent_turns: list     # list of {role, content} — raw last N turns
    memory_ctx: str
    search_ctx: str
    user_message: str
    total_tokens: int
    was_compressed: bool


async def compress_history(
    turns: list[dict],          # list of {role, content}
    ollama_base_url: str,
    small_model: str = "qwen2.5:3b",
) -> str:
    """
    Use small model to summarize old conversation turns into a compact paragraph.
    This is the GTA zone-unload step — compress what's not in active view.
    """
    if not turns:
        return ""

    conversation_text = "\n".join(
        f"{t['role'].upper()}: {t['content'][:300]}"
        for t in turns
    )

    prompt = (
        "Summarize this conversation history in 3-5 sentences. "
        "Keep: key decisions, facts learned, user preferences, task context. "
        "Drop: pleasantries, repeated info, filler.\n\n"
        f"{conversation_text}"
    )

    try:
        import aiohttp
        payload = {
            "model": small_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.2, "num_ctx": 2048, "num_predict": 200},
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{ollama_base_url}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    summary = data.get("message", {}).get("content", "").strip()
                    logger.info(f"ContextManager: compressed {len(turns)} turns → {_count_tokens(summary)} tokens")
                    return summary
    except Exception as e:
        logger.debug(f"Compression failed (non-critical): {e}")

    # Fallback: just take first + last turn if compression fails
    if len(turns) >= 2:
        first = turns[0]["content"][:150]
        last = turns[-1]["content"][:150]
        return f"Earlier: {first} ... Later: {last}"
    return turns[0]["content"][:200] if turns else ""


async def build_managed_context(
    full_history: list,          # list of Message objects
    user_message: str,
    system_prompt: str,
    memory_ctx: str = "",
    search_ctx: str = "",
    ollama_base_url: str = "http://localhost:11434",
    small_model: str = "qwen2.5:3b",
    force_compress: bool = False,
) -> ManagedContext:
    """
    Build a token-budgeted context.
    Old turns get compressed by 3B, recent turns passed raw, everything fits.
    """
    # Convert Message objects to dicts
    turns = [{"role": m.role, "content": m.content} for m in full_history
             if m.role in ("user", "assistant")]

    # Check if compression needed
    total_raw = sum(_count_tokens(t["content"]) for t in turns)
    needs_compress = force_compress or total_raw > (_BUDGET["history"] + _BUDGET["summary"])

    summary = ""
    recent_turns = turns

    if needs_compress and len(turns) > _RAW_TURNS:
        old_turns   = turns[:-_RAW_TURNS]
        recent_turns = turns[-_RAW_TURNS:]
        summary = await compress_history(old_turns, ollama_base_url, small_model)
        was_compressed = True
    else:
        was_compressed = False

    # Apply token budgets
    summary     = _truncate(summary,     _BUDGET["summary"])
    memory_ctx  = _truncate(memory_ctx,  _BUDGET["memory"])
    search_ctx  = _truncate(search_ctx,  _BUDGET["search"])
    user_message = _truncate(user_message, _BUDGET["message"])

    # Truncate recent turns if still too long
    recent_budget = _BUDGET["history"]
    trimmed_turns = []
    for turn in reversed(recent_turns):
        cost = _count_tokens(turn["content"])
        if cost <= recent_budget:
            trimmed_turns.insert(0, turn)
            recent_budget -= cost
        else:
            # Truncate this turn to fit
            trimmed = _truncate(turn["content"], recent_budget)
            trimmed_turns.insert(0, {**turn, "content": trimmed})
            break

    total = (
        _count_tokens(system_prompt) +
        _count_tokens(summary) +
        _count_tokens(memory_ctx) +
        _count_tokens(search_ctx) +
        sum(_count_tokens(t["content"]) for t in trimmed_turns) +
        _count_tokens(user_message)
    )

    logger.info(
        f"ContextManager: {total} tokens total | "
        f"compressed={was_compressed} | turns={len(trimmed_turns)} raw"
    )

    return ManagedContext(
        system_prompt=system_prompt,
        summary=summary,
        recent_turns=trimmed_turns,
        memory_ctx=memory_ctx,
        search_ctx=search_ctx,
        user_message=user_message,
        total_tokens=total,
        was_compressed=was_compressed,
    )


def managed_context_to_messages(ctx: ManagedContext) -> list[dict]:
    """
    Convert ManagedContext → Ollama message list.
    Structure:
      [system] [summary injection] [recent turns] [user with memory+search]
    """
    messages = []

    # System prompt
    messages.append({"role": "system", "content": ctx.system_prompt})

    # Summary of old history (injected as assistant context)
    if ctx.summary:
        messages.append({
            "role": "system",
            "content": f"[Previous conversation summary]\n{ctx.summary}",
        })

    # Recent raw turns
    for turn in ctx.recent_turns:
        messages.append(turn)

    # Build enriched user message
    parts = []
    if ctx.memory_ctx:
        parts.append(ctx.memory_ctx)
    if ctx.search_ctx:
        parts.append(ctx.search_ctx)

    if parts:
        enriched = "\n\n".join(parts) + f"\n\n---\nUser: {ctx.user_message}"
    else:
        enriched = ctx.user_message

    messages.append({"role": "user", "content": enriched})
    return messages
