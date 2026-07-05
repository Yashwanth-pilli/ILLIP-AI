"""
ILLIP AI — Telegram bridge.

Use your phone to chat with your local ILLIP while it runs on your laptop.
The bot calls ILLIP's own API at localhost — no data leaves your machine except
the Telegram message exchange.

Setup:
  1. Message @BotFather on Telegram → /newbot → copy token
  2. Add to .env:  TELEGRAM_BOT_TOKEN=your_token_here
  3. Start ILLIP normally — bot starts automatically
  4. Message the bot → first user becomes owner (auto-whitelisted)

Security:
  - Only whitelisted Telegram user IDs can send messages
  - First user to /start becomes owner (saved to data/telegram_owner.txt)
  - Owner can add others via /allow <user_id>

Commands:
  /start    — welcome + register as owner (first time)
  /status   — ILLIP system status
  /refresh  — flush stuck context (like !refresh in browser)
  /project  — show/switch active project
  /skills   — list available skills
  /help     — command list
  Regular messages → routed to ILLIP chat, response streamed back
  Voice messages → Whisper STT → ILLIP chat → text reply
"""

import asyncio
import json
import tempfile
import os
from pathlib import Path
from app.utils import logger
from app.config import settings

_app = None        # telegram Application instance
_running = False
_OWNER_FILE = None


def _owner_file() -> Path:
    p = settings.get_data_path() / "telegram_owner.txt"
    return p


def _load_allowed() -> set[int]:
    allowed: set[int] = set()
    # From config
    raw = settings.telegram_allowed_users.strip()
    if raw:
        for uid in raw.split(","):
            uid = uid.strip()
            if uid.isdigit():
                allowed.add(int(uid))
    # From owner file
    f = _owner_file()
    if f.exists():
        for line in f.read_text().splitlines():
            line = line.strip()
            if line.isdigit():
                allowed.add(int(line))
    return allowed


def _save_owner(user_id: int) -> None:
    f = _owner_file()
    existing = set()
    if f.exists():
        for line in f.read_text().splitlines():
            if line.strip().isdigit():
                existing.add(line.strip())
    existing.add(str(user_id))
    f.write_text("\n".join(sorted(existing)))


_allowed_users: set[int] = set()


def _is_allowed(user_id: int) -> bool:
    return len(_allowed_users) == 0 or user_id in _allowed_users


# ── ILLIP API helpers ─────────────────────────────────────────────────────────

async def _illip_chat(message: str, project_id: str = "default", force_tools: bool = False,
                      force_search: bool = False) -> str:
    """Send message to ILLIP, collect full streamed response."""
    import aiohttp
    url = f"http://127.0.0.1:{settings.api_port}/api/chat/stream"
    payload = {
        "message": message,
        "include_memory": True,
        "project_id": project_id,
        "force_tools": force_tools,
        "force_search": force_search,
    }
    collected = []
    tool_results = []
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=180)) as resp:
                if resp.status != 200:
                    return f"ILLIP error {resp.status}"
                async for line in resp.content:
                    line = line.decode().strip()
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        parsed = json.loads(data)
                        if "token" in parsed:
                            collected.append(parsed["token"])
                        elif "tool_result" in parsed:
                            tr = parsed["tool_result"]
                            tool_results.append(f"[{tr['name']}]: {tr['result'][:300]}")
                    except Exception:
                        pass
        reply = "".join(collected).strip()
        if tool_results and not reply:
            reply = "\n".join(tool_results)
        return reply or "(no response)"
    except Exception as e:
        return f"Connection error: {e}"


async def _illip_stream_to_message(message: str, tg_message, project_id: str = "default",
                                   force_search: bool = False) -> str:
    """Stream ILLIP response and progressively edit a Telegram message — no freeze."""
    import aiohttp
    import time
    url = f"http://127.0.0.1:{settings.api_port}/api/chat/stream"
    payload = {
        "message": message,
        "include_memory": True,
        "project_id": project_id,
        "force_tools": True,
        "force_search": force_search,
    }
    collected = []
    last_edit = time.monotonic()
    EDIT_INTERVAL = 2.5  # seconds between edits (Telegram rate limit: 1 edit/sec per message)

    async def _try_edit(text: str):
        try:
            await tg_message.edit_text(text[:4000] or "...")
        except Exception:
            pass

    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=180)) as resp:
                if resp.status != 200:
                    await _try_edit(f"ILLIP error {resp.status}")
                    return f"ILLIP error {resp.status}"
                async for line in resp.content:
                    line = line.decode().strip()
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        parsed = json.loads(data)
                        if "token" in parsed:
                            collected.append(parsed["token"])
                            now = time.monotonic()
                            if now - last_edit >= EDIT_INTERVAL and collected:
                                await _try_edit("".join(collected))
                                last_edit = now
                    except Exception:
                        pass
    except Exception as e:
        await _try_edit(f"Connection error: {e}")
        return f"Connection error: {e}"

    reply = "".join(collected).strip() or "(no response)"
    await _try_edit(reply)
    return reply


async def _illip_run_skill(skill_name: str, **kwargs) -> str:
    """Directly invoke an ILLIP skill by name."""
    import aiohttp
    url = f"http://127.0.0.1:{settings.api_port}/api/skills/{skill_name}/run"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json={"args": kwargs}, timeout=aiohttp.ClientTimeout(total=60)) as r:
                if r.status == 200:
                    d = await r.json()
                    return d.get("result", str(d))
                return f"Skill error {r.status}: {await r.text()}"
    except Exception as e:
        return f"Skill call failed: {e}"


async def _illip_status() -> str:
    import aiohttp
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                f"http://127.0.0.1:{settings.api_port}/api/system/status",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as r:
                d = await r.json()
                return (
                    f"ILLIP AI Status\n"
                    f"Model: {d.get('active_model','?')}\n"
                    f"Uptime: {int(d.get('uptime_seconds',0)//60)}m\n"
                    f"Memory: {d.get('memory_count',0)} entries\n"
                    f"Tasks: {d.get('task_count',0)}"
                )
    except Exception as e:
        return f"Status unavailable: {e}"


async def _illip_refresh() -> str:
    import aiohttp
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"http://127.0.0.1:{settings.api_port}/api/system/refresh",
                json={},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r:
                d = await r.json()
                return f"Refreshed: {', '.join(d.get('cleared', []))}\nAll data preserved."
    except Exception as e:
        return f"Refresh failed: {e}"


async def _illip_skills() -> str:
    import aiohttp
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                f"http://127.0.0.1:{settings.api_port}/api/skills/",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as r:
                d = await r.json()
                skills = d.get("skills", [])
                return "Skills:\n" + "\n".join(f"• {s['name']}: {s.get('description','')[:60]}" for s in skills)
    except Exception as e:
        return f"Skills unavailable: {e}"


async def _transcribe_voice(file_bytes: bytes, filename: str) -> str:
    """Send voice bytes to ILLIP STT endpoint."""
    import aiohttp
    form = aiohttp.FormData()
    form.add_field("file", file_bytes, filename=filename, content_type="audio/ogg")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"http://127.0.0.1:{settings.api_port}/api/voice/transcribe",
                data=form,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as r:
                if r.status != 200:
                    return ""
                d = await r.json()
                return d.get("text", "")
    except Exception as e:
        logger.warning(f"Telegram STT error: {e}")
        return ""


# ── Handlers ──────────────────────────────────────────────────────────────────

def _tg_escape(text: str) -> str:
    """Escape special Markdown chars for Telegram MarkdownV2."""
    for ch in r"\_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text


def _fmt_code(code: str, lang: str = "") -> str:
    """Wrap output in Telegram code block."""
    return f"```{lang}\n{code[:3800]}\n```"


async def _cmd_start(update, context):
    user_id = update.effective_user.id
    logger.info(f"Telegram /start from user_id={user_id}")
    if not _allowed_users or user_id in _allowed_users:
        _allowed_users.add(user_id)
        _save_owner(user_id)
        logger.info(f"Telegram owner set: {user_id}")
        await update.message.reply_text(
            f"ILLIP AI connected! You are owner (ID: {user_id}).\n\n"
            "Commands:\n"
            "/image <prompt>  — generate image (free)\n"
            "/remember <text> — save to memory\n"
            "/recall <query>  — search memory\n"
            "/memories        — list all memories\n"
            "/run <code>      — execute Python\n"
            "/search <query>  — web search\n"
            "/calc <expr>     — calculator\n"
            "/agent <task>    — run AI agent on task\n"
            "/model [name]    — show or switch model\n"
            "/status          — system status\n"
            "/refresh         — reset stuck context\n"
            "/allow <id>      — add user\n"
            "/help            — this message\n\n"
            "Or just send any message to chat with ILLIP."
        )
    else:
        await update.message.reply_text("Access denied. Ask owner to run /allow <your_id>.")


async def _cmd_help(update, context):
    if not _is_allowed(update.effective_user.id):
        return
    await update.message.reply_text(
        "ILLIP AI Commands:\n\n"
        "EXECUTION:\n"
        "/run <code>     — run Python code\n"
        "/search <query> — web search\n"
        "/calc <expr>    — math expression\n"
        "/agent <task>   — AI agent completes task\n\n"
        "SYSTEM:\n"
        "/model [name]   — show or switch model\n"
        "/status         — system status\n"
        "/refresh        — reset stuck context\n"
        "/skills         — list skills\n"
        "/allow <id>     — add user (owner only)\n\n"
        "Or send any text/voice message to chat with ILLIP."
    )


async def _cmd_status(update, context):
    if not _is_allowed(update.effective_user.id):
        return
    await update.message.reply_text(await _illip_status())


async def _cmd_refresh(update, context):
    if not _is_allowed(update.effective_user.id):
        return
    msg = await update.message.reply_text("Refreshing...")
    result = await _illip_refresh()
    await msg.edit_text(result)


async def _cmd_skills(update, context):
    if not _is_allowed(update.effective_user.id):
        return
    await update.message.reply_text(await _illip_skills())


async def _cmd_allow(update, context):
    """Owner adds another Telegram user ID to the whitelist."""
    user_id = update.effective_user.id
    # Only owner (first registered user) can add
    f = _owner_file()
    if f.exists():
        first_line = f.read_text().splitlines()
        owner_id = int(first_line[0]) if first_line else None
    else:
        owner_id = None

    if owner_id and user_id != owner_id:
        await update.message.reply_text("Only the owner can add users.")
        return

    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Usage: /allow <telegram_user_id>")
        return

    new_id = int(args[0])
    _allowed_users.add(new_id)
    _save_owner(new_id)
    await update.message.reply_text(f"User {new_id} added.")


async def _cmd_run(update, context):
    """Execute Python code via run_python skill."""
    if not _is_allowed(update.effective_user.id):
        return
    code = " ".join(context.args) if context.args else ""
    # Also grab multi-line code from message text after /run
    if not code:
        raw = update.message.text or ""
        code = raw[len("/run"):].strip()
    if not code:
        await update.message.reply_text("Usage: /run <python code>")
        return
    msg = await update.message.reply_text("Running...")
    result = await _illip_run_skill("run_python", code=code)
    try:
        await msg.edit_text(_fmt_code(result, ""), parse_mode="Markdown")
    except Exception:
        await msg.edit_text(result[:4000])


async def _cmd_search(update, context):
    """Web search via web_search skill."""
    if not _is_allowed(update.effective_user.id):
        return
    query = " ".join(context.args) if context.args else ""
    if not query:
        raw = update.message.text or ""
        query = raw[len("/search"):].strip()
    if not query:
        await update.message.reply_text("Usage: /search <query>")
        return
    msg = await update.message.reply_text("Searching...")
    result = await _illip_run_skill("web_search", query=query)
    try:
        await msg.edit_text(result[:4000], parse_mode="Markdown")
    except Exception:
        await msg.edit_text(result[:4000])


async def _cmd_remember(update, context):
    """Explicitly save something to Memory Ball: /remember [type] name | description | body"""
    if not _is_allowed(update.effective_user.id):
        return
    raw = update.message.text or ""
    text = raw[len("/remember"):].strip()
    if not text:
        await update.message.reply_text(
            "Usage: /remember <what to remember>\n"
            "Example: /remember I prefer short Python code over verbose Java-style\n\n"
            "Or with type: /remember [feedback] prefer-short | I prefer short code | User corrected me to use shorter code."
        )
        return

    from app.services.memory_ball import save_memory, auto_extract
    from app.providers import get_provider
    from app.core import Message

    # Quick extract via LLM
    msg = await update.message.reply_text("💾 Saving to memory...")
    try:
        saved = await auto_extract(text, "User explicitly asked to remember this.")
        if saved:
            await msg.edit_text(f"✅ Saved {saved} memory entry(s) to Memory Ball.")
        else:
            # Fallback: store as plain fact
            ok = save_memory(
                name=text[:40].lower().replace(" ", "-"),
                mem_type="fact",
                description=text[:100],
                body=text,
            )
            await msg.edit_text("✅ Saved to memory." if ok else "❌ Save failed.")
    except Exception as e:
        await msg.edit_text(f"Save error: {e}")


async def _cmd_recall(update, context):
    """Search Memory Ball: /recall <query>"""
    if not _is_allowed(update.effective_user.id):
        return
    query = " ".join(context.args) if context.args else ""
    if not query:
        raw = update.message.text or ""
        query = raw[len("/recall"):].strip()
    if not query:
        await update.message.reply_text("Usage: /recall <query>")
        return

    from app.services.memory_ball import search as ball_search
    results = ball_search(query, limit=5)
    if not results:
        await update.message.reply_text(f"No memories found for: {query}")
        return
    lines = [f"🧠 Memories for '{query}':\n"]
    for r in results:
        lines.append(f"[{r['type']}] *{r['name']}*\n{r.get('description','')}\n{r.get('body','')[:200]}\n")
    try:
        await update.message.reply_text("\n".join(lines)[:4000], parse_mode="Markdown")
    except Exception:
        await update.message.reply_text("\n".join(lines)[:4000])


async def _cmd_memories(update, context):
    """List all Memory Ball entries."""
    if not _is_allowed(update.effective_user.id):
        return
    from app.services.memory_ball import get_index_summary
    summary = get_index_summary()
    try:
        await update.message.reply_text(summary[:4000], parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(summary[:4000])


async def _cmd_kg(update, context):
    """/kg <entity> — show knowledge graph connections for an entity."""
    if not _is_allowed(update.effective_user.id):
        return
    query = " ".join(context.args) if context.args else ""
    if not query:
        raw = update.message.text or ""
        query = raw[len("/kg"):].strip()

    from app.services.knowledge_graph import stats, get_neighbors, search_nodes

    if not query or query == "stats":
        s = stats()
        await update.message.reply_text(
            f"🧠 Knowledge Graph\nNodes: {s['nodes']}\nEdges: {s['edges']}\n\n"
            "Usage: /kg <entity name>"
        )
        return

    result = get_neighbors(query, depth=2)
    if not result["center"]:
        # Try fuzzy
        hits = search_nodes(query, limit=5)
        if not hits:
            await update.message.reply_text(f"No entity found: '{query}'")
            return
        names = "\n".join(f"• {h['name']} ({h['type']})" for h in hits)
        await update.message.reply_text(f"Did you mean:\n{names}\n\nTry /kg <exact name>")
        return

    node_map = {n["id"]: n for n in result["nodes"]}
    center   = result["center"]
    lines    = [f"🔗 *{center['name']}* ({center['type']})\n"]
    for e in result["edges"][:15]:
        fn = node_map.get(e["from_id"], {}).get("name", e["from_id"])
        tn = node_map.get(e["to_id"],   {}).get("name", e["to_id"])
        lines.append(f"  {fn} —[{e['relation']}]→ {tn}")
    lines.append(f"\nTotal: {len(result['nodes'])} nodes, {len(result['edges'])} edges")
    try:
        await update.message.reply_text("\n".join(lines)[:4000], parse_mode="Markdown")
    except Exception:
        await update.message.reply_text("\n".join(lines)[:4000])


async def _cmd_image(update, context):
    """Generate image via Pollinations.ai — free, no API key needed."""
    if not _is_allowed(update.effective_user.id):
        return
    prompt = " ".join(context.args) if context.args else ""
    if not prompt:
        raw = update.message.text or ""
        prompt = raw[len("/image"):].strip()
    if not prompt:
        await update.message.reply_text("Usage: /image <description>\nExample: /image a cat on the moon")
        return

    msg = await update.message.reply_text("🎨 Generating...")
    import aiohttp, urllib.parse
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=768&height=768&nologo=true"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=60)) as r:
                if r.status != 200:
                    await msg.edit_text(f"Image gen failed: {r.status}")
                    return
                img_bytes = await r.read()
        await msg.delete()
        await update.message.reply_photo(img_bytes, caption=f"🎨 {prompt[:200]}")
    except Exception as e:
        await msg.edit_text(f"Image error: {e}")


async def _cmd_calc(update, context):
    """Calculator via calculator skill."""
    if not _is_allowed(update.effective_user.id):
        return
    expr = " ".join(context.args) if context.args else ""
    if not expr:
        raw = update.message.text or ""
        expr = raw[len("/calc"):].strip()
    if not expr:
        await update.message.reply_text("Usage: /calc <expression>")
        return
    result = await _illip_run_skill("calculator", expression=expr)
    await update.message.reply_text(f"{expr} = {result}")


async def _cmd_agent(update, context):
    """Spawn ILLIP as an agent to complete a task end-to-end."""
    if not _is_allowed(update.effective_user.id):
        return
    task = " ".join(context.args) if context.args else ""
    if not task:
        raw = update.message.text or ""
        task = raw[len("/agent"):].strip()
    if not task:
        await update.message.reply_text("Usage: /agent <task description>")
        return

    msg = await update.message.reply_text("Agent working on task...")
    chat_id = update.effective_chat.id

    async def keep_typing():
        for _ in range(60):
            await asyncio.sleep(4)
            try:
                await context.bot.send_chat_action(chat_id, "typing")
            except Exception:
                break

    typing_task = asyncio.create_task(keep_typing())
    try:
        # Use force_tools=True so agent uses all available skills
        agent_prompt = (
            f"You are an autonomous agent. Complete this task fully:\n{task}\n\n"
            "Use skills as needed. Show your work. End with a clear result summary."
        )
        reply = await asyncio.wait_for(
            _illip_chat(agent_prompt, force_tools=True),
            timeout=300,
        )
    except asyncio.TimeoutError:
        reply = "Agent timed out (5 min). Try a simpler task or /refresh."
    except Exception as e:
        reply = f"Agent error: {e}"
    finally:
        typing_task.cancel()

    await msg.delete()
    for chunk in _split_message(reply):
        try:
            await update.message.reply_text(chunk, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(chunk)


async def _cmd_model(update, context):
    """Show current model or switch to a new one."""
    if not _is_allowed(update.effective_user.id):
        return
    import aiohttp
    target = " ".join(context.args).strip() if context.args else ""
    base = f"http://127.0.0.1:{settings.api_port}"

    if not target:
        # Show current + available
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"{base}/api/system/models", timeout=aiohttp.ClientTimeout(total=15)) as r:
                    d = await r.json()
                    active = d.get("active", "?")
                    models = [m["name"] for m in d.get("models", [])]
                    lines = [f"Active: {active}", "", "Available:"]
                    for m in models:
                        mark = " <-- active" if m == active else ""
                        lines.append(f"  {m}{mark}")
                    lines.append("\nSwitch: /model <name>")
                    await update.message.reply_text("\n".join(lines))
        except Exception as e:
            await update.message.reply_text(f"Could not fetch models: {e}")
        return

    # Switch model
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"{base}/api/system/models/switch",
                json={"model": target},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r:
                if r.status == 200:
                    d = await r.json()
                    await update.message.reply_text(f"Switched to {d.get('model', target)}")
                else:
                    await update.message.reply_text(f"Switch failed: {await r.text()}")
    except Exception as e:
        await update.message.reply_text(f"Switch error: {e}")


def _is_gdrive_url(text: str) -> bool:
    return any(d in text for d in ("docs.google.com", "drive.google.com"))


async def _handle_text(update, context):
    if not _is_allowed(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return
    text = update.message.text.strip()
    if not text:
        return

    # Google Drive URL → ingest into memory
    if _is_gdrive_url(text):
        msg = await update.message.reply_text("📄 Reading file from Google Drive...")
        try:
            from app.services.gdrive_rag import ingest_url
            result = await ingest_url(text, project_id="default")
            if result["success"]:
                await msg.edit_text(
                    f"✅ Ingested {result['chunks']} chunks into memory.\n"
                    f"Preview: {result['preview'][:200]}\n\n"
                    "Now ask me anything about this document!"
                )
            else:
                await msg.edit_text(f"❌ {result['preview']}")
        except Exception as e:
            await msg.edit_text(f"Drive ingest error: {e}")
        return

    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id, "typing")

    # Send placeholder — will be edited progressively as tokens arrive (no freeze)
    placeholder = await update.message.reply_text("⏳")

    try:
        reply = await asyncio.wait_for(
            _illip_stream_to_message(text, placeholder, force_search=True),
            timeout=180,
        )
    except asyncio.TimeoutError:
        reply = "ILLIP took too long. Try /refresh and ask again."
        try:
            await placeholder.edit_text(reply)
        except Exception:
            pass
        return
    except Exception as e:
        reply = f"Error: {e}"
        try:
            await placeholder.edit_text(reply)
        except Exception:
            pass
        return

    # If reply is long, send overflow as extra messages (placeholder already has first 4000)
    if len(reply) > 4000:
        for chunk in _split_message(reply[4000:]):
            try:
                await update.message.reply_text(chunk, parse_mode="Markdown")
            except Exception:
                await update.message.reply_text(chunk)


async def _handle_photo(update, context):
    """Handle photo messages — analyze with vision model then optionally chat about it."""
    if not _is_allowed(update.effective_user.id):
        return
    # Caption becomes the prompt (e.g. "what's in this image?")
    caption = (update.message.caption or "Describe this image in detail.").strip()
    await context.bot.send_chat_action(update.effective_chat.id, "typing")
    msg = await update.message.reply_text("Analyzing image...")

    # Download largest photo size
    photo = update.message.photo[-1]
    tg_file = await context.bot.get_file(photo.file_id)
    img_bytes = await tg_file.download_as_bytearray()

    # Send to ILLIP vision endpoint
    import aiohttp
    form = aiohttp.FormData()
    form.add_field("file", bytes(img_bytes), filename="photo.jpg", content_type="image/jpeg")
    form.add_field("prompt", caption)

    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"http://127.0.0.1:{settings.api_port}/api/voice/vision/analyze",
                data=form,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as r:
                if r.status != 200:
                    await msg.edit_text(f"Vision error {r.status}: {await r.text()}")
                    return
                d = await r.json()
                description = d.get("description", "No description")

        # If caption was a real question (not default), also route through chat for a fuller answer
        if caption != "Describe this image in detail.":
            followup = f"I sent you an image. Here is what the vision model says about it:\n{description}\n\nNow answer: {caption}"
            await msg.edit_text("Thinking...")
            reply = await asyncio.wait_for(_illip_chat(followup, force_tools=False), timeout=120)
            for chunk in _split_message(reply):
                try:
                    await update.message.reply_text(chunk, parse_mode="Markdown")
                except Exception:
                    await update.message.reply_text(chunk)
            await msg.delete()
        else:
            for chunk in _split_message(description):
                try:
                    await msg.edit_text(chunk)
                except Exception:
                    await update.message.reply_text(chunk)

    except asyncio.TimeoutError:
        await msg.edit_text("Vision model took too long. Is llava-phi3 installed? Run: ollama pull llava-phi3")
    except Exception as e:
        await msg.edit_text(f"Vision error: {e}")


async def _handle_voice(update, context):
    if not _is_allowed(update.effective_user.id):
        return
    await context.bot.send_chat_action(update.effective_chat.id, "typing")
    # Download voice note
    voice = update.message.voice or update.message.audio
    if not voice:
        return
    tg_file = await context.bot.get_file(voice.file_id)
    file_bytes = await tg_file.download_as_bytearray()
    # Transcribe
    text = await _transcribe_voice(bytes(file_bytes), "voice.ogg")
    if not text:
        await update.message.reply_text("Could not transcribe audio. Try speaking more clearly.")
        return
    await update.message.reply_text(f"Heard: _{text}_", parse_mode="Markdown")
    # Chat
    await context.bot.send_chat_action(update.effective_chat.id, "typing")
    reply = await _illip_chat(text)
    for chunk in _split_message(reply):
        await update.message.reply_text(chunk, parse_mode="Markdown")


def _split_message(text: str, limit: int = 4000) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        chunks.append(text[:limit])
        text = text[limit:]
    return chunks


# ── Voice TTS ─────────────────────────────────────────────────────────────────

async def _cmd_speak(update, context):
    """/speak <text> — convert text to speech, send as voice note."""
    if not _is_allowed(update.effective_user.id):
        return
    text = " ".join(context.args).strip() if context.args else ""
    if not text:
        await update.message.reply_text("Usage: /speak <text>")
        return
    msg = await update.message.reply_text("🔊 Generating audio...")
    try:
        from app.services.voice_tts import speak
        audio_path = await speak(text)
        with open(audio_path, "rb") as f:
            await update.message.reply_voice(voice=f)
        await msg.delete()
        import os
        try:
            os.unlink(audio_path)
        except Exception:
            pass
    except RuntimeError as e:
        await msg.edit_text(f"❌ TTS failed: {e}")
    except Exception as e:
        logger.error(f"TTS command error: {e}")
        await msg.edit_text("❌ Voice generation failed.")


# ── Self-update ────────────────────────────────────────────────────────────────

async def _cmd_update(update, context):
    """/update — check and pull latest code from GitHub, then restart."""
    if not _is_allowed(update.effective_user.id):
        return
    msg = await update.message.reply_text("🔍 Checking for updates...")
    try:
        from app.services.self_update import check_update, safe_update, restart_server
        status = await check_update()
        if status["up_to_date"]:
            await msg.edit_text(
                f"✅ Already up to date.\nCommit: `{status['local']}`",
                parse_mode="Markdown",
            )
            return
        await msg.edit_text(
            f"⬇️ New version found!\nLocal: `{status['local']}`\nRemote: `{status['remote']}`\nPulling...",
            parse_mode="Markdown",
        )
        result = await safe_update()
        if not result["ok"]:
            await msg.edit_text(
                f"❌ Update broken — rolled back to `{result['old']}`.\n```\n{result['output'][:600]}\n```",
                parse_mode="Markdown",
            )
            return
        await msg.edit_text(
            f"✅ Updated `{result['old']}` → `{result['new']}`. Restarting...",
            parse_mode="Markdown",
        )
        await asyncio.sleep(1)
        restart_server()
    except Exception as e:
        logger.error(f"Self-update error: {e}")
        await msg.edit_text(f"❌ Update failed: {e}")


# ── Lifecycle ─────────────────────────────────────────────────────────────────

async def start_bot(token: str) -> None:
    global _app, _running, _allowed_users
    _allowed_users = _load_allowed()

    try:
        from telegram.ext import Application, CommandHandler, MessageHandler, filters
    except Exception as _tg_err:
        import traceback
        logger.error(f"Telegram import failed: {_tg_err}\n{traceback.format_exc()}")
        return
    _app = (
        Application.builder()
        .token(token)
        .build()
    )
    _app.add_handler(CommandHandler("start",   _cmd_start))
    _app.add_handler(CommandHandler("help",    _cmd_help))
    _app.add_handler(CommandHandler("status",  _cmd_status))
    _app.add_handler(CommandHandler("refresh", _cmd_refresh))
    _app.add_handler(CommandHandler("skills",  _cmd_skills))
    _app.add_handler(CommandHandler("allow",   _cmd_allow))
    _app.add_handler(CommandHandler("run",     _cmd_run))
    _app.add_handler(CommandHandler("search",  _cmd_search))
    _app.add_handler(CommandHandler("calc",    _cmd_calc))
    _app.add_handler(CommandHandler("image",    _cmd_image))
    _app.add_handler(CommandHandler("kg",       _cmd_kg))
    _app.add_handler(CommandHandler("remember", _cmd_remember))
    _app.add_handler(CommandHandler("recall",   _cmd_recall))
    _app.add_handler(CommandHandler("memories", _cmd_memories))
    _app.add_handler(CommandHandler("agent",   _cmd_agent))
    _app.add_handler(CommandHandler("model",   _cmd_model))
    _app.add_handler(CommandHandler("speak",   _cmd_speak))
    _app.add_handler(CommandHandler("update",  _cmd_update))
    _app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_text))
    _app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO,   _handle_voice))
    _app.add_handler(MessageHandler(filters.PHOTO,                   _handle_photo))

    _running = True
    logger.info("Telegram bot starting (polling)...")
    await _app.initialize()
    await _app.start()
    await _app.updater.start_polling(drop_pending_updates=False)
    logger.info("Telegram bot online")


async def stop_bot() -> None:
    global _running
    if _app and _running:
        _running = False
        try:
            if _app.updater.running:
                await _app.updater.stop()
        except Exception as e:
            logger.debug(f"Telegram updater stop (non-critical): {e}")
        try:
            await _app.stop()
            await _app.shutdown()
        except Exception as e:
            logger.debug(f"Telegram app stop (non-critical): {e}")
        logger.info("Telegram bot stopped")
