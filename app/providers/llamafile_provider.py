"""
llamafile provider — single-file model runner.

llamafile packages a model + llama.cpp into one executable that serves
an OpenAI-compatible API. No installation, no Ollama, just run the file.

Download models from: https://huggingface.co/Mozilla/Mistral-7B-Instruct-v0.2-llamafile
Run: ./mistral-7b-instruct-v0.2.Q4_K_M.llamafile --server --port 8080

Then set in .env:
  MODEL_PROVIDER=llamafile
  LLAMAFILE_URL=http://localhost:8080
  LLAMAFILE_MODEL=mistral-7b  (any string, used as model name in requests)
"""

import os
from typing import Optional, List

import aiohttp

from app.core import Message
from app.providers.base_provider import BaseProvider
from app.utils import logger

_LLAMAFILE_URL = os.getenv("LLAMAFILE_URL", "http://localhost:8080")
_LLAMAFILE_MODEL = os.getenv("LLAMAFILE_MODEL", "llamafile")


class LlamafileProvider(BaseProvider):
    """llamafile — OpenAI-compat local server from a single executable."""

    def __init__(self):
        super().__init__("llamafile")
        self.base_url = _LLAMAFILE_URL.rstrip("/")
        self.model = _LLAMAFILE_MODEL

    async def health_check(self) -> bool:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    f"{self.base_url}/v1/models",
                    timeout=aiohttp.ClientTimeout(total=3),
                ) as r:
                    return r.status == 200
        except Exception:
            return False

    async def generate_response(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=300),
                ) as r:
                    if r.status != 200:
                        text = await r.text()
                        raise RuntimeError(f"llamafile {r.status}: {text[:200]}")
                    data = await r.json()
                    return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"llamafile error: {e}")
            raise
