"""
Chat modes — user-toggleable reply styles injected into the system prompt.

  caveman  -> ultra-terse replies. Big win on a local model: fewer output
              tokens = visibly faster responses on 8GB-VRAM hardware.
  ponytail -> laziest-solution-that-works bias for code: stdlib before deps,
              one line before fifty, flags over-engineering.

Modes persist to data/chat_modes.json so they survive restarts, and are
global (not per-project) — a reply style is a user preference, not a
project property.
"""

import json
from pathlib import Path

from app.utils import logger

_STATE_PATH = Path(__file__).parent.parent.parent / "data" / "chat_modes.json"

# name -> (description shown in UI, system-prompt addendum)
MODES: dict[str, tuple[str, str]] = {
    "caveman": (
        "Ultra-terse replies — faster on local hardware",
        "REPLY STYLE — CAVEMAN MODE (user enabled): Be extremely terse. Drop "
        "articles, filler words, pleasantries and hedging. Sentence fragments are "
        "fine. Keep ALL technical substance: exact terms, numbers, code, error "
        "messages. Code blocks stay complete and normal. Drop caveman style for "
        "security warnings and irreversible-action confirmations — write those "
        "clearly and completely.",
    ),
    "ponytail": (
        "Simplest-solution bias — stdlib first, no over-engineering",
        "SOLUTION STYLE — PONYTAIL MODE (user enabled): Always give the laziest "
        "solution that actually works. Question whether the task needs to exist "
        "at all. Prefer the standard library over dependencies, native platform "
        "features over custom code, one line over fifty. When you see "
        "over-engineering in the user's code or plan, say so and show the "
        "shorter path. Never add speculative flexibility, abstraction layers, "
        "or config for needs that don't exist yet.",
    ),
}


def _load() -> dict[str, bool]:
    try:
        raw = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        return {k: bool(raw.get(k, False)) for k in MODES}
    except (OSError, ValueError):
        return {k: False for k in MODES}


def _save(state: dict[str, bool]) -> None:
    try:
        _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError as e:
        logger.error(f"chat_modes save failed: {e}")


def get_modes() -> dict[str, bool]:
    """Current on/off state of every mode."""
    return _load()


def set_mode(name: str, enabled: bool) -> dict[str, bool]:
    """Toggle a mode. Raises KeyError for unknown modes."""
    if name not in MODES:
        raise KeyError(name)
    state = _load()
    state[name] = enabled
    _save(state)
    logger.info(f"chat mode {name} -> {'on' if enabled else 'off'}")
    return state


def prompt_addendum() -> str:
    """Concatenated addenda for every enabled mode ('' when none active)."""
    state = _load()
    parts = [MODES[k][1] for k, on in state.items() if on and k in MODES]
    return ("\n\n" + "\n\n".join(parts)) if parts else ""


if __name__ == "__main__":
    # Self-check: toggle round-trips, addendum reflects state, unknown rejected.
    before = get_modes()
    try:
        s = set_mode("caveman", True)
        assert s["caveman"] is True
        assert "CAVEMAN" in prompt_addendum()
        s = set_mode("caveman", False)
        assert "CAVEMAN" not in prompt_addendum()
        try:
            set_mode("nope", True)
            raise AssertionError("unknown mode must raise")
        except KeyError:
            pass
    finally:
        for k, v in before.items():
            set_mode(k, v)
    print("chat_modes self-check ok")
