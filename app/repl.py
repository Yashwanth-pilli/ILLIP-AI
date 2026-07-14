"""
ILLIP terminal REPL — an interactive coding agent in your terminal, like a local
developer assistant. Type `illip` to chat; it streams replies live, runs tools (read
files, run shell/python) in the folder you launched from, and remembers the
conversation so `illip --continue` picks up where you left off.

No browser, no server — this talks straight to the local model.
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.core import Message
from app.utils import logger, get_current_timestamp


def _session_path() -> Path:
    d = settings.get_data_path() / "cli_sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d / "last.json"


def _save_session(history: list[dict]) -> None:
    try:
        _session_path().write_text(
            json.dumps({"saved": datetime.now().isoformat(), "history": history}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logger.debug(f"REPL session save failed: {e}")


def _load_session() -> list[dict]:
    p = _session_path()
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("history", [])
    except Exception:
        return []


def _p(text: str = "", end: str = "\n") -> None:
    """Print, tolerating a cp1252 console."""
    try:
        sys.stdout.write(text + end)
    except UnicodeEncodeError:
        sys.stdout.write(text.encode("ascii", "replace").decode() + end)
    sys.stdout.flush()


# Pure-ASCII cat + figlet logo — renders on any console (no box-drawing chars).
_LOGO = r"""
      /\_/\      _____ _      _      _____ _____
     ( o.o )    |_   _| |    | |    |_   _|  __ \
      > ^ <       | | | |    | |      | | | |__) |
     /     \      | | | |    | |      | | |  ___/
    (       )    _| |_| |____| |____ _| |_| |
     \__ __/    |_____|______|______|_____|_|
        v
"""


def _login_gate() -> bool:
    """If a local password is set (same one the browser uses), require it before
    the terminal agent opens. Keeps browser + terminal at parity."""
    from app.services import auth_local
    if not auth_local.is_enabled():
        return True
    import getpass
    for _ in range(3):
        try:
            pw = getpass.getpass("  ILLIP is locked — password: ")
        except (EOFError, KeyboardInterrupt):
            return False
        if auth_local.login(pw):
            _p("  unlocked.\n")
            return True
        _p("  wrong password.")
    _p("  too many tries. bye.")
    return False


async def _slash(user: str) -> bool:
    """Handle /ask, /read, /skills in the terminal — same features as the web UI.
    Returns True if it handled the input."""
    parts = user.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd == "/ask":
        if not arg:
            _p("  usage: /ask <question>")
            return True
        _p("  [searching the web + reading pages...]")
        from app.agents.research_agent import get_research_agent
        answer, sources = "", []
        try:
            async for step in get_research_agent().research(arg, depth="quick"):
                if step.type == "done":
                    answer = step.data.get("answer", "")
                    sources = step.data.get("sources", [])
                elif step.type == "error":
                    _p(f"  [error] {step.message}")
                    return True
        except Exception as e:
            _p(f"  [error] {e}")
            return True
        _p("illip > " + (answer or "(no answer)"))
        if sources:
            _p("\n  sources:")
            for i, s in enumerate(sources, 1):
                _p(f"   {i}. {(s.get('title') or s.get('url'))[:70]} - {s.get('url')}")
        _p("")
        return True

    if cmd == "/read":
        if not arg:
            _p("  usage: /read <url>")
            return True
        from app.services.readers import smart_read
        d = await smart_read(arg)
        if d.get("error") and not d.get("text"):
            _p(f"  [couldn't read] {d['error']}")
            return True
        _p(f"illip > [{d.get('source')}] {d.get('title') or d.get('url')}\n")
        _p((d.get("text") or "")[:4000])
        _p("")
        return True

    if cmd == "/skills":
        from app.services.skills_catalog import directory
        dr = directory(category=arg)
        _p(f"illip > agent skills ({dr['count']}/{dr['total']}) — categories: {', '.join(dr['categories'])}")
        for s in dr["skills"]:
            _p(f"   - {s['id']} [{s['category']}] — {s['description']}")
        _p(f"  filter: /skills <category>   source: {dr['source']}\n")
        return True

    return False


def _banner(launch_dir) -> None:
    """Big clear ILLIP cat + logo, then the working area below."""
    import os
    os.system("")  # enable ANSI colors on Windows 10+ (no-op elsewhere)
    C, DIM, R = "\033[36m", "\033[90m", "\033[0m"  # cyan, grey, reset
    _p(C + _LOGO + R)
    _p(DIM + "  your AI company — right here in your terminal" + R)
    _p(DIM + "  " + "-" * 52 + R)
    _p(f"  working in : {launch_dir}")
    _p(DIM + "  commands   : /ask <q>  /read <url>  /skills [cat]  /clear  /exit" + R)
    _p("")


async def _run(resume: bool) -> None:
    # Quiet internal logs — this is a clean interactive surface.
    import logging
    logging.getLogger("illip").setLevel(logging.WARNING)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    # Same login as the browser — if a password is set, gate the terminal too.
    if not _login_gate():
        return

    from app.providers import get_provider
    from app.skills.registry import get_registry
    from app.services.chat_service import _load_system_prompt
    from app.services.shell_service import set_cwd
    from app.services.router_service import route

    # Tools operate in the folder the user launched from — their project.
    launch_dir = Path.cwd()
    set_cwd(launch_dir)

    provider = await get_provider()
    registry = get_registry()
    tool_specs = registry.to_tool_specs()

    system_prompt = _load_system_prompt() + (
        f"\n\nYou are running in the user's terminal, working in: {launch_dir}. "
        "You can read files and run shell/python via tools. When you write code, "
        "put each file in a fenced block with its filename (```python:app.py)."
    )
    messages: list[Message] = [Message(role="system", content=system_prompt, timestamp=get_current_timestamp())]

    _banner(launch_dir)

    history = _load_session() if resume else []
    if resume and history:
        for h in history:
            messages.append(Message(role=h["role"], content=h["content"], timestamp=get_current_timestamp()))
        _p(f"  [resumed {len(history)} messages from your last session]\n")

    while True:
        try:
            user = input("you > ").strip()
        except (EOFError, KeyboardInterrupt):
            _p("\nbye")
            break
        if not user:
            continue
        low = user.lower()
        if low in ("/exit", "/quit", "exit", "quit"):
            _p("bye")
            break
        if low in ("/clear", "/reset"):
            messages = messages[:1]  # keep system
            history = []
            _save_session(history)
            _p("[conversation cleared]\n")
            continue
        # Web-UI parity commands: /ask, /read, /skills (not saved to chat history)
        if low.startswith(("/ask", "/read", "/skills")):
            if await _slash(user):
                continue

        messages.append(Message(role="user", content=user, timestamp=get_current_timestamp()))
        history.append({"role": "user", "content": user})

        try:
            routing = await route(user)
            model = routing["model"]
            ctx = max(routing.get("context_limit", 8192), 8192) if routing["pressure"] != "critical" else routing.get("context_limit", 2048)
        except Exception:
            model, ctx = getattr(provider, "model", None), 8192

        reply = await _answer(provider, registry, tool_specs, messages, model, ctx)

        messages.append(Message(role="assistant", content=reply, timestamp=get_current_timestamp()))
        history.append({"role": "assistant", "content": reply})
        _save_session(history)


async def _answer(provider, registry, tool_specs, messages, model, ctx) -> str:
    """One turn: run the tool loop if the model wants tools, then stream the reply.
    Mirrors the server chat path so terminal behaviour matches the web UI."""
    collected: list[str] = []
    tool_findings: list[tuple[str, str]] = []

    if tool_specs and hasattr(provider, "generate_with_tools"):
        active = list(messages)
        for _ in range(3):
            try:
                content, calls = await provider.generate_with_tools(active, tool_specs, model=model, num_ctx=ctx)
            except Exception as e:
                logger.debug(f"REPL tool step failed: {e}")
                break
            if not calls:
                if content:
                    _p("illip > " + content)
                    collected.append(content)
                break
            for c in calls:
                _p(f"  [tool] {c['name']}({json.dumps(c.get('arguments', {}))[:80]})")
                result = await registry.run(c["name"], c.get("arguments", {}))
                tool_findings.append((c["name"], result))
                _p(f"  [result] {result[:200]}")
                active.append(Message(role="assistant", content=content or "", timestamp=get_current_timestamp()))
                active.append(Message(role="tool", content=result, timestamp=get_current_timestamp()))

    if not collected:
        # Stream the final answer. Fold tool results into the last user message —
        # never pass role="tool" to stream_response (some templates crash on it).
        stream_msgs = [m for m in messages if m.role != "tool"]
        if tool_findings:
            findings = "\n\n".join(f"[Tool '{n}' returned]:\n{r}" for n, r in tool_findings)
            for i in range(len(stream_msgs) - 1, -1, -1):
                if stream_msgs[i].role == "user":
                    stream_msgs[i] = Message(
                        role="user",
                        content=stream_msgs[i].content + "\n\n---\nTool results (answer using only these):\n\n" + findings,
                        timestamp=get_current_timestamp(),
                    )
                    break
        _p("illip > ", end="")
        try:
            async for tok in provider.stream_response(stream_msgs, model=model, num_ctx=ctx):
                _p(tok, end="")
                collected.append(tok)
        except Exception as e:
            _p(f"[error: {e}]", end="")
        _p("")

    reply = "".join(collected).strip()
    # Save any fenced code blocks the model produced to real files in cwd.
    _write_code_blocks(reply)
    return reply


def _write_code_blocks(text: str) -> None:
    from app.services.agent_orchestrator import extract_and_write_files
    try:
        files = extract_and_write_files(text, Path.cwd())
        for f in files:
            _p(f"  [wrote] {f['name']} ({f['bytes']}b)")
    except Exception as e:
        logger.debug(f"REPL code-block write failed: {e}")


def run_repl(resume: bool = False) -> None:
    try:
        asyncio.run(_run(resume))
    except KeyboardInterrupt:
        _p("\nbye")


if __name__ == "__main__":
    # Self-check: session save/load round-trips.
    h = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"}]
    _save_session(h)
    assert _load_session() == h, "session round-trip failed"
    print("repl self-check ok")
