"""
Agent orchestrator — runs a task through the agent company with LIVE progress.

Flow: Planner breaks the goal into steps → each step runs on the best-fit agent →
every step streams as an event so the UI shows the crew thinking and working in
real time. Sequential pipeline (not a DAG) on purpose: simple, debuggable, and
each agent gets the accumulated results of the steps before it.

Public: async generator `run_task_stream(task)` yielding dict events:
  {type: plan|step_start|step_done|final|error, ...}
"""

import json
import re
import time
from pathlib import Path
from typing import AsyncGenerator, Optional

from app.agents import get_agent_registry
from app.services.shell_service import WS_ROOT, set_cwd
from app.utils import logger

# Default filename per language when the agent didn't name the file.
_LANG_DEFAULT = {
    "python": "main.py", "py": "main.py", "javascript": "script.js", "js": "script.js",
    "typescript": "script.ts", "ts": "script.ts", "html": "index.html", "css": "styles.css",
    "json": "data.json", "bash": "run.sh", "sh": "run.sh", "sql": "schema.sql",
    "jsx": "App.jsx", "tsx": "App.tsx", "yaml": "config.yaml", "yml": "config.yaml",
    "markdown": "README.md", "md": "README.md", "text": "notes.txt", "": "file.txt",
}
# Block fenced code with optional info string: ```lang  or  ```lang:filename
_CODE_RE = re.compile(r"```([^\n`]*)\n(.*?)```", re.DOTALL)
_FNAME_HINT = re.compile(r"(?:file|filename|save as|create)\s*[:=]?\s*[`\"']?([\w./-]+\.\w+)", re.I)


def _safe_name(name: str) -> str:
    name = name.strip().strip("`\"'").replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^\w.-]", "_", name)
    return name[:60] or "file.txt"


# Single-line snippets starting with these are shell COMMANDS to run, not files.
_SHELL_VERBS = {
    "python", "python3", "pip", "pip3", "npm", "npx", "node", "pytest", "cd", "ls",
    "git", "echo", "bash", "sh", "mkdir", "cat", "export", "set", "curl", "wget",
}


def _is_command_snippet(code: str, lang: str) -> bool:
    """True when a block is a command to run (python app.py), not a file to save.
    These are what produce junk run.sh / file.txt clutter."""
    lines = [l for l in code.strip().splitlines() if l.strip()]
    if len(lines) == 1:
        first = lines[0].strip().lstrip("$").strip().split()[0].lower()
        if first in _SHELL_VERBS or first.startswith("./"):
            return True
    if lang in ("bash", "sh", "shell", "console", "shellsession", "powershell") and len(lines) <= 2:
        return True
    return False


def _file_url(run_dir: Path, fname: str) -> str:
    """Served URL for a file in run_dir. WS_ROOT is served at /data/terminal, so
    the URL is that prefix + the run_dir's path relative to WS_ROOT."""
    try:
        rel = run_dir.resolve().relative_to(WS_ROOT.resolve())
        return f"/data/terminal/{rel.as_posix()}/{fname}"
    except Exception:
        return f"/data/terminal/agent_runs/{run_dir.name}/{fname}"


def extract_and_write_files(text: str, run_dir: Path, seen_hashes: set | None = None) -> list[dict]:
    """Pull fenced code blocks from agent output and write each to a real file.
    Filename comes from the info string (```py:app.py), a hint in the line just
    before the block, or a language default. `seen_hashes` (shared across steps)
    skips exact-duplicate content so agents repeating code don't spawn dupes.
    Returns [{name, lang, bytes, url}]."""
    import hashlib
    written: list[dict] = []
    seen: dict[str, int] = {}
    if seen_hashes is None:
        seen_hashes = set()
    for m in _CODE_RE.finditer(text):
        info = (m.group(1) or "").strip()
        code = m.group(2).strip("\n")
        if not code or len(code) < 15:
            continue
        lang, fname = info, ""
        if ":" in info:
            _lang_peek = info.split(":", 1)[0]
        else:
            _lang_peek = info
        # Skip command snippets (they belong in run_shell, not on disk)
        if _is_command_snippet(code, _lang_peek.strip().lower()):
            continue
        # Skip exact-duplicate content already written this run
        h = hashlib.md5(code.encode()).hexdigest()
        if h in seen_hashes:
            continue
        seen_hashes.add(h)
        lang, fname = info, ""
        if ":" in info:
            lang, fname = info.split(":", 1)
        lang = lang.strip().lower()
        # Look just before the block for an explicit filename mention
        if not fname:
            pre = text[max(0, m.start() - 120):m.start()]
            hint = _FNAME_HINT.search(pre)
            if hint:
                fname = hint.group(1)
        # Reject junk filenames (e.g. a function signature grabbed as a name):
        # must look like name.ext, else fall back to the language default.
        fname = fname.strip()
        if fname and not re.match(r"^[\w.-]+\.[A-Za-z0-9]{1,8}$", fname):
            fname = ""
        if not fname:
            fname = _LANG_DEFAULT.get(lang, f"file_{len(written)+1}.txt")
        fname = _safe_name(fname)
        try:
            run_dir.mkdir(parents=True, exist_ok=True)
            # De-dupe against BOTH this batch and files already on disk from
            # earlier steps, so nothing gets silently overwritten.
            fpath = run_dir / fname
            if fname in seen or fpath.exists():
                stem, dot, ext = fname.rpartition(".")
                n = 2
                while (run_dir / (f"{stem}_{n}.{ext}" if dot else f"{fname}_{n}")).exists() or \
                        (f"{stem}_{n}.{ext}" if dot else f"{fname}_{n}") in seen:
                    n += 1
                fname = f"{stem}_{n}.{ext}" if dot else f"{fname}_{n}"
                fpath = run_dir / fname
            seen[fname] = 1
            fpath.write_text(code, encoding="utf-8")
            written.append({"name": fname, "lang": lang or "text", "bytes": len(code.encode()),
                            "url": _file_url(run_dir, fname)})
        except Exception as e:
            logger.warning(f"Orchestrator file write failed ({fname}): {e}")
    return written

# Map loose role words the planner might emit → real registry agent types.
_ROLE_ALIASES = {
    "plan": "planner", "planning": "planner",
    "research": "research", "search": "research", "investigate": "research",
    "code": "code", "coder": "code", "developer": "code", "engineer": "code",
    "build": "builder", "builder": "builder", "implement": "builder", "write_code": "builder",
    "review": "reviewer", "reviewer": "reviewer", "audit": "reviewer",
    "test": "tester", "tester": "tester", "qa": "qa",
    "write": "writer", "writer": "writer", "content": "content", "copy": "writer",
    "analyze": "analyst", "analyst": "analyst", "data": "data",
    "summarize": "summarizer", "summary": "summarizer",
    "translate": "translator", "design": "design", "seo": "seo",
    "finance": "finance", "legal": "compliance", "compliance": "compliance",
    "ceo": "ceo", "strategy": "ceo", "memory": "memory",
}


def _resolve_agent(role: str, available: set) -> str:
    """Best-effort map a planner-named role to an installed agent type."""
    r = (role or "").strip().lower().replace(" ", "_")
    if r in available:
        return r
    if r in _ROLE_ALIASES and _ROLE_ALIASES[r] in available:
        return _ROLE_ALIASES[r]
    for key, val in _ROLE_ALIASES.items():
        if key in r and val in available:
            return val
    return "builder" if "builder" in available else next(iter(available))


def parse_plan(text: str, available: set) -> list[dict]:
    """Extract steps from the planner's output. Accepts a JSON array of
    {agent, task}, or falls back to parsing numbered/bulleted lines.
    Always returns at least one step so the pipeline never stalls."""
    # 1) Try a JSON array anywhere in the text
    m = re.search(r"\[\s*\{.*?\}\s*\]", text, re.DOTALL)
    if m:
        try:
            raw = json.loads(m.group(0))
            steps = []
            for item in raw:
                task = (item.get("task") or item.get("step") or item.get("description") or "").strip()
                if task:
                    steps.append({"agent": _resolve_agent(item.get("agent", ""), available), "task": task})
            if steps:
                return steps[:6]
        except Exception:
            pass
    # 2) Fallback: numbered / bulleted lines "1. do X" or "- do X"
    steps = []
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"^(?:\d+[.)]|[-*])\s+(.*)", line)
        if m and len(m.group(1)) > 4:
            task = m.group(1).strip()
            role = ""
            rm = re.match(r"\[([^\]]+)\]\s*(.*)", task)  # optional "[research] ..."
            if rm:
                role, task = rm.group(1), rm.group(2)
            steps.append({"agent": _resolve_agent(role, available), "task": task})
    if steps:
        return steps[:6]
    # 3) Last resort: single build step
    return [{"agent": "builder" if "builder" in available else next(iter(available)),
             "task": text.strip()[:500] or "Complete the task."}]


_PLAN_PROMPT = (
    "You are the Planner of an AI company. Break the user's goal into 2-4 concrete steps. "
    "Assign each step to ONE agent from this list: research, code, builder, reviewer, tester, "
    "writer, analyst, summarizer, design, finance, ceo.\n"
    "Reply with ONLY a JSON array, nothing else, like:\n"
    '[{"agent":"research","task":"..."},{"agent":"builder","task":"..."}]\n\n'
    "Goal: "
)


def _safe_dest_folder(dest: str) -> str:
    """Sanitize a user-chosen build folder name to a single safe segment kept
    inside the workspace (no path traversal, no drive letters)."""
    dest = (dest or "").strip().replace("\\", "/")
    dest = dest.split("/")[-1]                       # last segment only
    dest = re.sub(r"[^\w.\- ]", "", dest).strip()    # drop anything weird
    dest = dest.replace(" ", "_")[:64]
    return dest


async def run_task_stream(task: str, dest: str = "", out_dir: Path | None = None) -> AsyncGenerator[dict, None]:
    """Run `task` through Planner + agents, yielding live progress events.

    dest: user-chosen folder NAME, sandboxed to WS_ROOT/<dest>/ (web UI path).
    out_dir: absolute folder to build into, NO sandbox — CLI-only, where the
    user runs on their own machine against their own explicit folder. When set
    it wins over dest. Empty -> auto agent_runs/run_<ts>/."""
    registry = get_agent_registry()
    available = set(registry.get_available_agents())

    # Per-run workspace. Files the agents write and commands they run via
    # run_shell share the same folder.
    if out_dir is not None:
        run_dir = Path(out_dir).expanduser().resolve()
        run_id = run_dir.name
    else:
        safe_dest = _safe_dest_folder(dest)
        if safe_dest:
            run_id = safe_dest
            run_dir = WS_ROOT / safe_dest
        else:
            run_id = f"run_{int(time.time())}"
            run_dir = WS_ROOT / "agent_runs" / run_id
    set_cwd(run_dir)
    all_files: list[dict] = []
    seen_hashes: set = set()  # dedup identical code across ALL steps

    # ── 1. Plan ──────────────────────────────────────────────────────────────
    yield {"type": "step_start", "agent": "planner", "task": "Breaking the goal into steps…"}
    planner = registry.get_agent("planner")
    try:
        pres = await planner.execute_task(_PLAN_PROMPT + task)
        plan_text = pres.get("output", "") if pres.get("status") == "success" else ""
    except Exception as e:
        plan_text = ""
        logger.warning(f"Orchestrator planner failed: {e}")

    steps = parse_plan(plan_text, available)
    yield {"type": "plan", "steps": [{"agent": s["agent"], "task": s["task"]} for s in steps]}

    # ── 2. Execute steps sequentially, threading results forward ─────────────
    results: list[dict] = []
    context: dict = {"goal": task}
    for i, step in enumerate(steps, 1):
        agent_type = step["agent"]
        agent = registry.get_agent(agent_type)
        if not agent:
            agent_type = "builder"
            agent = registry.get_agent(agent_type)
        yield {"type": "step_start", "agent": agent_type, "idx": i, "total": len(steps),
               "task": step["task"]}
        step_task = step["task"]
        # Nudge code-producing agents to emit COMPLETE, named files we can save.
        if agent_type in ("code", "builder", "design", "tester"):
            step_task += (
                "\n\nWrite COMPLETE, runnable code. Put each file in its own fenced block "
                "with the filename in the info string, e.g. ```python:app.py or ```html:index.html. "
                "No placeholders or TODOs. CREATE FILES ONLY with these fenced blocks — they are "
                "saved to disk automatically. Do NOT use shell to write files (no `cat > f << EOF`, "
                "no `echo > f`): the shell here is Windows cmd and heredocs fail."
            )
        # Tester/builder can actually run and verify via the shell.
        if agent_type in ("tester", "builder"):
            step_task += (
                "\n\nUse the run_shell tool ONLY to RUN and verify code (python file.py, pytest, "
                "node file.js, dir…), never to create files. The shell is Windows cmd. "
                "Report what the commands output."
            )
        try:
            res = await agent.execute_task(step_task, context=dict(context))
            out = res.get("output", "") if res.get("status") == "success" else f"(failed: {res.get('error')})"
        except Exception as e:
            out = f"(error: {e})"
            logger.warning(f"Orchestrator step {i} ({agent_type}) failed: {e}")
        results.append({"agent": agent_type, "task": step["task"], "output": out})
        # Feed this step's result into the next agent's context
        context[f"step_{i}_{agent_type}"] = out[:1200]

        # Save any real files this agent produced (code blocks → disk)
        new_files = extract_and_write_files(out, run_dir, seen_hashes)
        if new_files:
            all_files.extend(new_files)
            yield {"type": "files", "agent": agent_type, "files": new_files}

        yield {"type": "step_done", "agent": agent_type, "idx": i,
               "summary": (out[:220] + "…") if len(out) > 220 else out}

    # ── 3. Sweep the run dir for files created via run_shell (echo > f) too,
    #        so the manifest reflects everything on disk, not just code blocks.
    known = {f["name"] for f in all_files}
    if run_dir.is_dir():
        for p in sorted(run_dir.rglob("*")):
            if p.is_file() and p.name not in known:
                try:
                    all_files.append({"name": p.name, "lang": p.suffix.lstrip(".") or "text",
                                      "bytes": p.stat().st_size,
                                      "url": _file_url(run_dir, p.name)})
                except Exception:
                    pass

    # ── 4. Final combined answer + file manifest ─────────────────────────────
    final = "\n\n".join(f"**{r['agent'].title()}** — {r['task']}\n\n{r['output']}" for r in results)
    yield {"type": "final", "result": final, "steps_run": len(results),
           "files": all_files, "run_id": run_id}


# ═══════════════════════════════════════════════════════════════════════════
# Loop methodology — plan → act → check → retry until the goal is actually met
# ═══════════════════════════════════════════════════════════════════════════

_CHECK_PROMPT = (
    "You are a strict QA reviewer. Decide if the work output below actually satisfies "
    "the goal. Reply with ONLY a JSON object, nothing else:\n"
    '{"done": true/false, "feedback": "if not done: what exactly is missing or wrong, '
    'concrete and actionable. if done: empty string"}\n\n'
    "GOAL:\n{goal}\n\nWORK OUTPUT:\n{output}\n"
)


def parse_verdict(text: str) -> tuple[bool, str]:
    """Extract {done, feedback} from the checker's reply. Defaults to done=True on
    unparseable output so a flaky checker can't loop forever."""
    m = re.search(r"\{.*?\}", text, re.DOTALL)
    if m:
        try:
            d = json.loads(m.group(0))
            return bool(d.get("done", True)), str(d.get("feedback", ""))[:1000]
        except Exception:
            pass
    low = text.lower()
    if any(w in low for w in ("not done", "incomplete", "missing", "fails", "does not satisfy")):
        return False, text.strip()[:1000]
    return True, ""


async def run_task_loop_stream(task: str, max_loops: int = 3, dest: str = "") -> AsyncGenerator[dict, None]:
    """Agentic loop: run the crew, have a reviewer verdict the result against the
    goal, feed the feedback into a retry. Stops on done or max_loops.
    dest: user-chosen build folder, threaded to run_task_stream."""
    max_loops = max(1, min(int(max_loops), 5))
    registry = get_agent_registry()
    feedback = ""
    done = False
    loop_n = 0
    final_ev: Optional[dict] = None

    for loop_n in range(1, max_loops + 1):
        yield {"type": "loop_start", "loop": loop_n, "max": max_loops,
               "feedback": feedback}
        current = task if not feedback else (
            f"{task}\n\nA previous attempt was rejected by QA. "
            f"Fix these specific problems:\n{feedback}"
        )
        final_ev = None
        async for ev in run_task_stream(current, dest=dest):
            ev["loop"] = loop_n
            if ev.get("type") == "final":
                final_ev = ev
            yield ev

        result_text = (final_ev or {}).get("result", "")
        checker = registry.get_agent("reviewer") or registry.get_agent("qa") \
            or registry.get_agent("planner")
        try:
            cres = await checker.execute_task(
                _CHECK_PROMPT.replace("{goal}", task[:1500])
                             .replace("{output}", result_text[:4000])
            )
            verdict_text = cres.get("output", "") if cres.get("status") == "success" else ""
        except Exception as e:
            logger.warning(f"Loop checker failed: {e}")
            verdict_text = ""
        done, feedback = parse_verdict(verdict_text)
        yield {"type": "loop_check", "loop": loop_n, "done": done,
               "feedback": feedback}
        if done:
            break

    yield {"type": "loop_end", "loops_used": loop_n, "done": done}


if __name__ == "__main__":
    # ponytail self-check: the plan parser is the only tricky logic.
    av = {"research", "builder", "reviewer", "code"}
    j = parse_plan('junk [{"agent":"research","task":"find X"},{"agent":"coder","task":"write Y"}] tail', av)
    assert len(j) == 2 and j[0]["agent"] == "research" and j[1]["agent"] == "code", j
    n = parse_plan("1. [research] gather data\n2. build the thing", av)
    assert len(n) == 2 and n[0]["agent"] == "research", n
    f = parse_plan("just do it", av)
    assert len(f) == 1, f
    # Verdict parser self-check
    assert parse_verdict('{"done": true, "feedback": ""}') == (True, "")
    assert parse_verdict('blah {"done": false, "feedback": "missing tests"} blah') == (False, "missing tests")
    assert parse_verdict("The work is incomplete, missing the CSS")[0] is False
    assert parse_verdict("looks good to me")[0] is True
    assert parse_verdict("")[0] is True  # unparseable -> stop looping
    # File extraction self-check
    import tempfile
    d = Path(tempfile.mkdtemp())
    sample = 'Here it is:\n```python:app.py\nprint("hi there world")\n```\nand\n```html\n<h1>Hello</h1><p>world</p>\n```'
    files = extract_and_write_files(sample, d)
    assert len(files) == 2, files
    assert files[0]["name"] == "app.py", files
    assert (d / "app.py").read_text().strip() == 'print("hi there world")'
    assert files[1]["name"] == "index.html", files  # lang default
    # Command snippets are skipped; exact-dup content is skipped across calls.
    sh = "run it:\n```bash\npython app.py\n```\ndup:\n```python:app.py\nprint(\"hi there world\")\n```"
    hashes: set = set()
    f2 = extract_and_write_files(files_sample_hashes := sample, d, hashes)  # seeds hashes
    f3 = extract_and_write_files(sh, d, hashes)
    assert f3 == [], f3  # command snippet skipped + duplicate app.py skipped
    # Junk filename (function sig in info string) → falls back to lang default
    d2 = Path(tempfile.mkdtemp())
    jf = extract_and_write_files("```python: def add(a,b)\ndef add(a, b):\n    return a+b\n```", d2)
    assert jf and jf[0]["name"] == "main.py", jf  # not "def_add_a__b__"
    print("orchestrator parse + file self-check ok")
