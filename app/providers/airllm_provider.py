"""
AirLLM provider — runs large models (13B-70B) on low VRAM by streaming layers.

Splits model into chunks that fit in available VRAM. No quantization needed.
On RTX 4060 8GB: runs Llama-70B at ~0.5 tok/s (slow but works).

Install: pip install airllm
Models: any HuggingFace causal LM (Llama, Mistral, Qwen, etc.)
Set AIRLLM_MODEL in .env to the HuggingFace model ID.

Ghost Engine picks this backend when model is too large for full GPU load
and no Ollama quantized version is available.
"""

import asyncio
import os
from typing import Optional, List

from app.core import Message
from app.providers.base_provider import BaseProvider
from app.utils import logger

_AIRLLM_MODEL = os.getenv("AIRLLM_MODEL", "")
_MAX_NEW_TOKENS = int(os.getenv("AIRLLM_MAX_TOKENS", "512"))
_COMPRESSION = os.getenv("AIRLLM_COMPRESSION", "")  # "" | "4bit" | "8bit"


class AirLLMProvider(BaseProvider):
    """AirLLM — layer-streaming inference for oversized models."""

    def __init__(self):
        super().__init__("airllm")
        self._model = None
        self._tokenizer = None
        self._model_id = _AIRLLM_MODEL

    def _load(self):
        if self._model is not None:
            return
        if not self._model_id:
            raise RuntimeError("AIRLLM_MODEL not set in .env")

        try:
            from airllm import AutoModel
        except ImportError:
            raise RuntimeError("AirLLM not installed. Run: pip install airllm")

        logger.info(f"AirLLM: loading {self._model_id} (compression={_COMPRESSION or 'none'})")
        kwargs = {}
        if _COMPRESSION in ("4bit", "8bit"):
            kwargs["compression"] = _COMPRESSION

        self._model = AutoModel.from_pretrained(self._model_id, **kwargs)
        logger.info("AirLLM: model loaded")

    async def health_check(self) -> bool:
        if not _AIRLLM_MODEL:
            return False
        try:
            import airllm  # noqa
            return True
        except ImportError:
            return False

    async def generate_response(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._generate_sync, messages, temperature, max_tokens)

    def _generate_sync(
        self,
        messages: List[Message],
        temperature: float,
        max_tokens: Optional[int],
    ) -> str:
        self._load()

        # Build prompt — simple chat template
        prompt = ""
        for m in messages:
            if m.role == "system":
                prompt += f"<|system|>\n{m.content}\n"
            elif m.role == "user":
                prompt += f"<|user|>\n{m.content}\n"
            elif m.role == "assistant":
                prompt += f"<|assistant|>\n{m.content}\n"
        prompt += "<|assistant|>\n"

        n_tokens = max_tokens or _MAX_NEW_TOKENS

        try:
            input_tokens = self._model.tokenizer(
                prompt,
                return_tensors="pt",
                return_attention_mask=False,
                truncation=True,
                max_length=2048,
                padding=False,
            )
            out = self._model.generate(
                **input_tokens,
                max_new_tokens=n_tokens,
                temperature=temperature,
                do_sample=temperature > 0,
            )
            # Decode only newly generated tokens
            gen_ids = out[0][input_tokens["input_ids"].shape[1]:]
            return self._model.tokenizer.decode(gen_ids, skip_special_tokens=True).strip()
        except Exception as e:
            logger.error(f"AirLLM generate failed: {e}")
            return f"AirLLM error: {e}"
