"""
Generic OpenAI-compatible provider.

Works with ANY service that speaks the OpenAI chat-completions API:
  - DeepSeek API       (https://api.deepseek.com)
  - Together AI        (https://api.together.xyz)
  - vLLM               (http://localhost:8000)
  - LM Studio          (http://localhost:1234)
  - Text Generation UI (http://localhost:5000)
  - Mistral AI         (https://api.mistral.ai)
  - Perplexity AI      (https://api.perplexity.ai)
  - Any OpenAI-compat endpoint

Config (.env):
  OPENAI_COMPAT_BASE_URL=https://api.deepseek.com   # required
  OPENAI_COMPAT_API_KEY=sk-...                       # optional (if endpoint needs auth)
  OPENAI_COMPAT_MODEL=deepseek-chat                  # optional (defaults to first available)
"""

import json
import os
from typing import List, Optional

import aiohttp

from app.core import Message
from app.providers.base_provider import BaseProvider
from app.utils import logger


def _cfg() -> tuple[str, str, str]:
    url   = os.environ.get("OPENAI_COMPAT_BASE_URL", "").rstrip("/")
    key   = os.environ.get("OPENAI_COMPAT_API_KEY", "").strip()
    model = os.environ.get("OPENAI_COMPAT_MODEL", "").strip()
    return url, key, model


class OpenAICompatProvider(BaseProvider):
    """Generic OpenAI-compatible endpoint — use for any model, any service."""

    def __init__(self, base_url: str):
        super().__init__("openai_compat")
        # _chat_url()/_models_url() append "/v1/...", so the base must NOT end in
        # /v1. Strip it if the user included it (OmniRoute's docs show .../v1).
        base = base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3].rstrip("/")
        self.base_url = base
        _, self.api_key, self.model = _cfg()
        self.timeout = 120

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _chat_url(self) -> str:
        return f"{self.base_url}/v1/chat/completions"

    def _models_url(self) -> str:
        return f"{self.base_url}/v1/models"

    def _to_messages(self, messages: List[Message]) -> list:
        return [{"role": m.role if m.role != "tool" else "user", "content": m.content}
                for m in messages]

    async def _resolve_model(self) -> str:
        if self.model:
            return self.model
        # Ask the endpoint what models are available, pick the first
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    self._models_url(),
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as r:
                    if r.status == 200:
                        d = await r.json()
                        models = d.get("data") or d.get("models") or []
                        if models:
                            first = models[0].get("id") or models[0]
                            if isinstance(first, str):
                                self.model = first
                                return self.model
        except Exception:
            pass
        return "default"

    async def health_check(self) -> bool:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    self._models_url(),
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as r:
                    return r.status in (200, 401, 403)  # 401/403 = endpoint exists, auth needed
        except Exception:
            return False

    async def generate_response(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        model = kwargs.get("model") or await self._resolve_model()
        payload = {
            "model": model,
            "messages": self._to_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens or 2048,
            "stream": False,
        }
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    self._chat_url(),
                    json=payload,
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as r:
                    if r.status != 200:
                        return f"OpenAI-compat error {r.status}: {await r.text()}"
                    # Some gateways (e.g. OmniRoute) reply with an SSE stream even
                    # for stream:false — aggregate the deltas. Otherwise plain JSON.
                    ctype = r.headers.get("Content-Type", "")
                    if "text/event-stream" in ctype:
                        return self._aggregate_sse(await r.text())
                    d = await r.json(content_type=None)
                    return d["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f"OpenAI-compat error: {e}"

    @staticmethod
    def _aggregate_sse(text: str) -> str:
        """Join the content deltas from an OpenAI-style SSE response into one string."""
        out = []
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                break
            try:
                choice = json.loads(data)["choices"][0]
                tok = (choice.get("delta", {}) or {}).get("content") \
                    or (choice.get("message", {}) or {}).get("content") or ""
                if tok:
                    out.append(tok)
            except Exception:
                continue
        return "".join(out).strip()

    async def stream_response(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        model: Optional[str] = None,
        num_ctx: int = 4096,
    ):
        chosen = model or await self._resolve_model()
        payload = {
            "model": chosen,
            "messages": self._to_messages(messages),
            "temperature": temperature,
            "max_tokens": num_ctx,
            "stream": True,
        }
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    self._chat_url(),
                    json=payload,
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as resp:
                    if resp.status != 200:
                        yield f"[error {resp.status}]"
                        return
                    async for line in resp.content:
                        line = line.decode().strip()
                        if not line.startswith("data: "):
                            continue
                        data = line[6:]
                        if data == "[DONE]":
                            return
                        try:
                            chunk = json.loads(data)
                            token = chunk["choices"][0].get("delta", {}).get("content", "")
                            if token:
                                yield token
                        except Exception:
                            continue
        except Exception as e:
            yield f"[OpenAI-compat stream error: {e}]"

    async def generate_with_tools(
        self,
        messages: List[Message],
        tools: list,
        temperature: float = 0.7,
        model: Optional[str] = None,
        num_ctx: int = 4096,
    ) -> tuple[str, list]:
        chosen = model or await self._resolve_model()
        payload = {
            "model": chosen,
            "messages": self._to_messages(messages),
            "tools": tools,
            "tool_choice": "auto",
            "temperature": temperature,
            "max_tokens": num_ctx,
            "stream": False,
        }
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    self._chat_url(),
                    json=payload,
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"OpenAI-compat tool-call error {resp.status}: {await resp.text()}")
                        return "", []
                    # OmniRoute may reply SSE even for stream:false — handle both.
                    if "text/event-stream" in resp.headers.get("Content-Type", ""):
                        content, raw_calls = self._aggregate_sse_tools(await resp.text())
                    else:
                        msg = (await resp.json(content_type=None))["choices"][0]["message"]
                        content = msg.get("content") or ""
                        raw_calls = msg.get("tool_calls") or []
                    tool_calls = []
                    for c in raw_calls:
                        if c.get("type", "function") != "function":
                            continue
                        fn = c.get("function", {})
                        try:
                            args = json.loads(fn.get("arguments") or "{}")
                        except Exception:
                            args = {}
                        if fn.get("name"):
                            tool_calls.append({"name": fn["name"], "arguments": args})
                    return content.strip(), tool_calls
        except Exception as e:
            logger.error(f"OpenAI-compat tool-call failed: {e}")
            return "", []

    @staticmethod
    def _aggregate_sse_tools(text: str) -> tuple[str, list]:
        """Assemble content + tool_calls from an OpenAI-style SSE tool response."""
        content_parts: list = []
        calls: dict = {}  # index -> {id, function:{name, arguments}}
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                break
            try:
                choice = json.loads(data)["choices"][0]
            except Exception:
                continue
            delta = choice.get("delta", {}) or choice.get("message", {}) or {}
            if delta.get("content"):
                content_parts.append(delta["content"])
            for tc in (delta.get("tool_calls") or []):
                idx = tc.get("index", 0)
                slot = calls.setdefault(idx, {"type": "function", "function": {"name": "", "arguments": ""}})
                fn = tc.get("function", {})
                if fn.get("name"):
                    slot["function"]["name"] = fn["name"]
                if fn.get("arguments"):
                    slot["function"]["arguments"] += fn["arguments"]
        return "".join(content_parts), [calls[k] for k in sorted(calls)]
