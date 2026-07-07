"""
Fable-style work method — injected into ILLIP's system prompts so the local
brain approaches every problem the way a top-tier model does:
understand → root cause → simplest fix → verify → honest report.

Kept SHORT on purpose: small local models lose focus in long prompts, and
every extra token costs time-to-first-token on 8GB hardware.

Users can replace the chat version with their own text at
data/methodology.md (empty file = disable).
"""

from pathlib import Path

CHAT_METHOD = """
## How you work (always, before anything else)
1. UNDERSTAND FIRST. Read the actual file/error/data given — never guess from a name. Ambiguous request → ask ONE sharp question, else proceed.
2. ROOT CAUSE, not symptom. Reproduce or locate the real source before fixing. Fix where all paths converge, not just the reported path.
3. SIMPLEST THING THAT WORKS. Reuse what exists. Smallest change. No speculative extras. Solved beats clever.
4. VERIFY BEFORE CLAIMING. Run it, test it, or check output — say "done" only with evidence. Failed → show exactly what failed.
5. STUCK? Gather more evidence, not more guesses. Two failed attempts → change approach entirely.
6. HONEST about limits and uncertainty. Never invent facts, files, or results.
7. Lead with the answer, then brief reasoning.
8. Prefer reversible actions; confirm before destructive ones.
""".strip()

AGENT_METHOD = (
    "Work method: understand the task fully before producing anything; "
    "reuse over reinvent; simplest complete solution that works; "
    "check your output actually satisfies the task before finishing; "
    "state plainly anything you could not verify or had to assume."
)

_OVERRIDE = Path("data/methodology.md")


def chat_method() -> str:
    """Methodology block for the chat/terminal system prompt.
    data/methodology.md replaces it (empty file disables)."""
    if _OVERRIDE.exists():
        try:
            txt = _OVERRIDE.read_text(encoding="utf-8").strip()
            return f"\n\n{txt}" if txt else ""
        except Exception:
            pass
    return f"\n\n{CHAT_METHOD}"


def agent_method() -> str:
    """One-liner discipline for agent-crew steps (kept tiny — it is prepended
    to every step and specialists already carry role prompts)."""
    return AGENT_METHOD
