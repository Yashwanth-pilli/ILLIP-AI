"""OpenAI-compatible /v1 endpoint tests (Cursor / Continue.dev / Copilot-style clients)."""

from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_v1_models():
    r = client.get("/v1/models")
    assert r.status_code == 200
    assert r.json()["data"][0]["id"] == "illip"


def test_v1_chat_completion_nonstream():
    """Regression: endpoint used to 500 (missing await + Message timestamp)."""
    r = client.post("/v1/chat/completions", json={
        "model": "illip",
        "messages": [{"role": "user", "content": "hello"}],
        "stream": False,
    })
    assert r.status_code == 200
    d = r.json()
    assert d["object"] == "chat.completion"
    assert d["choices"][0]["message"]["role"] == "assistant"
    assert len(d["choices"][0]["message"]["content"]) > 0
