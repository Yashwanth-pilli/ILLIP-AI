"""Fable-style work method: injection + user override."""

from app.services.methodology import CHAT_METHOD, agent_method, chat_method


def test_chat_method_injected_into_system_prompt():
    from app.services.chat_service import _load_system_prompt
    p = _load_system_prompt()
    assert "ROOT CAUSE" in p and "VERIFY BEFORE CLAIMING" in p


def test_override_replaces_and_empty_disables(monkeypatch, tmp_path):
    import app.services.methodology as m
    f = tmp_path / "methodology.md"
    f.write_text("My custom method.", encoding="utf-8")
    monkeypatch.setattr(m, "_OVERRIDE", f)
    assert "My custom method." in chat_method()
    assert "ROOT CAUSE" not in chat_method()
    f.write_text("", encoding="utf-8")
    assert chat_method() == ""


def test_agent_method_is_short():
    # Prepended to EVERY crew step on 8GB hardware — must stay tiny.
    assert len(agent_method()) < 400
    assert "verify" in agent_method().lower()


def test_chat_method_stays_lean():
    # Long prompts slow TTFT on small local models — guard the budget.
    assert len(CHAT_METHOD.split()) < 220
