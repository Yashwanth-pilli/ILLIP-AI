"""
Idea Journey — take a raw idea and turn it into direction + action.

`/idea <your idea>`   -> explain, find similar work, step plan (into Tasks),
                         skill gaps, budget tips. Idea saved to a local vault
                         with SHA-256 + timestamp (proof-of-existence).
`/stuck [situation]`  -> reads your tasks + workspace, suggests the next step.
`/opps [about]`       -> live web search for opportunities that fit YOUR field
                         and stage — nothing hardcoded: the model decides what
                         kinds of opportunities (grants, internships, journals,
                         residencies, competitions...) fit the person.

Everything runs on the local model + free web search. No cloud accounts.
"""

import hashlib
import json
import re

from app.config import settings
from app.core import Message
from app.providers import get_provider
from app.services.search_service import web_search
from app.services.task_service import get_task_service
from app.utils import logger, get_current_timestamp

_VAULT_DIR = settings.get_data_path() / "idea_vault"


async def _llm(prompt: str, temperature: float = 0.4) -> str:
    provider = await get_provider()
    return await provider.generate_response(
        [Message(role="user", content=prompt, timestamp=get_current_timestamp())],
        temperature=temperature,
    )


def _extract_json(text: str) -> dict | None:
    """Small local models wrap JSON in prose/code fences — dig it out."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def vault_store(idea: str, project_id: str = "default") -> dict:
    """Proof-of-existence: hash + timestamp, stored locally. Never leaves the device."""
    _VAULT_DIR.mkdir(parents=True, exist_ok=True)
    ts = get_current_timestamp().isoformat()
    digest = hashlib.sha256(idea.encode("utf-8")).hexdigest()
    entry = {"sha256": digest, "timestamp": ts, "project_id": project_id, "idea": idea}
    (_VAULT_DIR / f"{ts.replace(':', '-')}_{digest[:12]}.json").write_text(
        json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")
    return entry


def vault_list() -> list[dict]:
    if not _VAULT_DIR.exists():
        return []
    out = []
    for p in sorted(_VAULT_DIR.glob("*.json"), reverse=True):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


def _latest_idea(project_id: str) -> str | None:
    for e in vault_list():
        if e.get("project_id") == project_id or project_id == "default":
            return e.get("idea")
    return None


async def analyze_idea(idea: str, project_id: str = "default") -> str:
    """One LLM analysis + web search for similar work + tasks + vault. Markdown report."""
    entry = vault_store(idea, project_id)

    raw = await _llm(
        "Analyze this idea for its owner. Reply with ONLY a JSON object, no prose:\n"
        '{"field": "the domain this idea belongs to (be specific, any field: tech, agriculture, art, medicine, cooking...)",\n'
        ' "explanation": "the idea explained back clearly in 3-4 sentences",\n'
        ' "applications": ["2-4 real-world uses"],\n'
        ' "steps": [{"title": "...", "description": "..."}]  (5-7 small concrete first steps, prototype-first, cheapest test first),\n'
        ' "skills_needed": ["skills the owner must have or learn"],\n'
        ' "budget_tips": ["2-4 ways to build this cheap/free: open-source tools, free tiers, student discounts"],\n'
        ' "search_queries": ["2 web search queries to find similar existing work/research"]}\n\n'
        f"IDEA: {idea}"
    )
    data = _extract_json(raw) or {}

    # Similar work — live search, field comes from the model, never hardcoded.
    similar_md = []
    for q in (data.get("search_queries") or [idea])[:2]:
        try:
            for r in await web_search(q, max_results=3):
                title = r.get("title", "").strip() or r.get("url", "")
                if title:
                    similar_md.append(f"- [{title}]({r.get('url', '')}) — {r.get('snippet', '')[:140]}")
        except Exception as e:
            logger.debug(f"idea similar-work search failed: {e}")

    # Steps land in the real Tasks panel.
    steps = data.get("steps") or []
    ts = get_task_service()
    for i, s in enumerate(steps):
        try:
            ts.create_task(title=s.get("title", f"Step {i+1}"),
                           description=s.get("description", ""), priority=len(steps) - i)
        except Exception as e:
            logger.debug(f"idea task create failed: {e}")

    lines = [f"# 💡 Idea Journey — {data.get('field', 'your idea')}", ""]
    if data.get("explanation"):
        lines += ["## Your idea, understood", data["explanation"], ""]
    elif not data:
        lines += ["## Analysis", raw.strip(), ""]  # model didn't give JSON — show its prose
    if data.get("applications"):
        lines += ["## Where it can be used", *[f"- {a}" for a in data["applications"]], ""]
    if similar_md:
        lines += ["## Similar work out there (learn from it, find your gap)", *similar_md[:6], ""]
    if steps:
        lines += [f"## Your first steps — added to the ✅ Tasks panel ({len(steps)} tasks)",
                  *[f"{i+1}. **{s.get('title','')}** — {s.get('description','')}" for i, s in enumerate(steps)], ""]
    if data.get("skills_needed"):
        lines += ["## Skills to have or learn", *[f"- {s}" for s in data["skills_needed"]], ""]
    if data.get("budget_tips"):
        lines += ["## Build it cheap", *[f"- {b}" for b in data["budget_tips"]], ""]
    lines += ["---",
              f"🔒 **Idea vaulted locally** — SHA-256 `{entry['sha256'][:16]}…` at {entry['timestamp']}. "
              "Proof this idea existed on your machine at this moment. It never leaves your device.",
              "", "Stuck later? Just type `/stuck`. Ready to grow? Type `/opps`."]
    return "\n".join(lines)


async def next_step(situation: str = "", project_id: str = "default") -> str:
    """Stuck mode: current tasks + workspace files + last idea -> one concrete next step."""
    ts = get_task_service()
    tasks = list(ts.tasks.values())[-15:]
    task_summary = "\n".join(f"- [{t['status']}] {t['title']}" for t in tasks) or "(no tasks yet)"

    ws = settings.get_workspaces_path()
    files = [p.name for p in ws.rglob("*") if p.is_file()][:30] if ws.exists() else []
    idea = _latest_idea(project_id) or "(no idea saved yet)"

    return await _llm(
        "You are a practical mentor. The user is STUCK on their project. "
        "Suggest exactly ONE concrete next step they can do today (plus a fallback if that's blocked), "
        "based on their real state below. Be specific, kind, and short. Markdown, "
        "start with heading '## Your next step'.\n\n"
        f"THEIR IDEA: {idea}\n\nTHEIR TASKS:\n{task_summary}\n\n"
        f"WORKSPACE FILES: {', '.join(files) or '(empty)'}\n\n"
        f"WHAT THEY SAY: {situation or '(they only said they are stuck)'}",
        temperature=0.5,
    )


async def find_opportunities(about: str = "", project_id: str = "default") -> str:
    """Live opportunity search. Field + opportunity types decided by the model
    from the user's own idea/description — nothing hardcoded."""
    context = about.strip() or _latest_idea(project_id)
    if not context:
        return ("Tell me your field or what you're building: `/opps organic farming in India` "
                "— or run `/idea <your idea>` first and I'll use that.")

    raw = await _llm(
        "A person wants real-world opportunities that fit THEM. Decide from their context what kinds fit: "
        "could be internships, jobs, grants, government schemes, fellowships, competitions, hackathons, "
        "residencies, exhibitions, journals, conferences, accelerators — whatever matches their field and stage. "
        "Do NOT assume they are a student or in tech.\n"
        "Reply ONLY JSON: {\"field\": \"...\", \"queries\": [\"4-5 web search queries, each targeting one "
        "opportunity type relevant to them, current year included where useful\"]}\n\n"
        f"THEIR CONTEXT: {context}"
    )
    data = _extract_json(raw) or {"field": context[:60], "queries": [f"{context[:80]} opportunities 2026"]}

    results_md = []
    for q in (data.get("queries") or [])[:5]:
        try:
            hits = await web_search(q, max_results=4)
        except Exception as e:
            logger.debug(f"opps search failed: {e}")
            continue
        if hits:
            results_md.append(f"### 🔎 {q}")
            for r in hits:
                title = r.get("title", "").strip() or r.get("url", "")
                results_md.append(f"- [{title}]({r.get('url', '')}) — {r.get('snippet', '')[:140]}")
            results_md.append("")

    if not results_md:
        return ("Web search returned nothing right now (offline?). Try again when online, "
                f"or search manually for: {', '.join(data.get('queries', []))}")

    header = [f"# 🌱 Opportunities — {data.get('field', 'your field')}", "",
              "Live results from the web (verify deadlines on the official pages):", ""]
    footer = ["---", "Want them tailored differently? `/opps <describe yourself>` — "
              "e.g. `/opps final-year mechanical engineering student in Hyderabad`."]
    return "\n".join(header + results_md + footer)
