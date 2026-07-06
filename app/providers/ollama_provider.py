"""
Ollama provider — uses /api/chat for proper multi-turn conversation.
"""

from typing import Optional, List
import aiohttp

from app.core import Message
from app.providers.base_provider import BaseProvider
from app.config import settings
from app.utils import logger


class OllamaProvider(BaseProvider):
    """Provider for Ollama local models."""

    def __init__(self):
        super().__init__("ollama")
        self.base_url = settings.ollama_base_url
        self.model = settings.ollama_model
        self.timeout = 300  # 5 min for large models
        self._ghost_plan = None  # cached GhostPlan

    async def _get_ghost_options(self, model: str, num_ctx: int) -> dict:
        """
        Ghost Engine options for INITIAL model load only.
        Called when model is not yet warmed in VRAM.
        Returns full options: num_gpu, num_thread, num_ctx, use_mmap, use_mlock.
        """
        try:
            from app.hardware.ghost_engine import calculate_plan
            from app.hardware.safety_monitor import get_pressure
            pressure = get_pressure()
            # Under critical pressure, cap context
            if pressure == "critical":
                num_ctx = min(num_ctx, 2048)
                logger.warning(f"GhostEngine: critical pressure — capping ctx to {num_ctx}")
            plan = await calculate_plan(model, requested_ctx=num_ctx, base_url=self.base_url)
            for w in plan.warnings:
                logger.warning(f"GhostEngine: {w}")
            return plan.ollama_options
        except Exception as e:
            logger.debug(f"GhostEngine unavailable: {e}")
            return {"num_ctx": num_ctx}

    async def health_check(self) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    return response.status == 200
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False

    async def generate_response(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        try:
            # Convert Message objects to Ollama chat format
            chat_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ]

            chosen_model = self.model
            num_ctx = kwargs.get("num_ctx", 8192)
            ghost_opts = await self._get_ghost_options(chosen_model, num_ctx)
            payload = {
                "model": chosen_model,
                "messages": chat_messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    **ghost_opts,
                },
            }
            if max_tokens:
                payload["options"]["num_predict"] = max_tokens

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Ollama API error {response.status}: {error_text}")
                        return f"Error: Ollama returned {response.status} — is the model downloaded? Run: ollama pull {self.model}"

                    data = await response.json()
                    content = data.get("message", {}).get("content", "").strip()
                    if not content:
                        return "Error: Empty response from Ollama"
                    return content

        except aiohttp.ClientConnectorError:
            return (
                "Error: Cannot connect to Ollama. "
                "Start it with: ollama serve"
            )
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            return f"Error: {str(e)}"

    async def stream_response(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        model: Optional[str] = None,
        num_ctx: int = 4096,
    ):
        """Async generator yielding token strings from Ollama streaming API."""
        chosen_model = model or self.model
        from app.hardware.speed_optimizer import get_warmed_ctx, mark_warmed, KEEP_ALIVE_SECONDS

        is_warmed = get_warmed_ctx(chosen_model, fallback=None) is not None

        if is_warmed:
            # Model already in VRAM — send minimal opts to avoid reload penalty (~30s)
            effective_ctx = get_warmed_ctx(chosen_model, fallback=num_ctx)
            opts = {
                "temperature": temperature,
                "num_ctx": effective_ctx,
                "keep_alive": KEEP_ALIVE_SECONDS,
            }
        else:
            # First load — use Ghost Engine for optimal GPU split + context
            ghost_opts    = await self._get_ghost_options(chosen_model, num_ctx)
            effective_ctx = ghost_opts.get("num_ctx", num_ctx)
            opts = {
                "temperature": temperature,
                "keep_alive": KEEP_ALIVE_SECONDS,
                **ghost_opts,
            }
            logger.info(
                f"GhostEngine initial load: {chosen_model} "
                f"gpu_layers={ghost_opts.get('num_gpu','?')} ctx={effective_ctx}"
            )
        chat_messages = [{"role": m.role, "content": m.content} for m in messages]
        payload = {
            "model": chosen_model,
            "messages": chat_messages,
            "stream": True,
            "options": opts,
        }
        import asyncio as _asyncio
        try:
            async with aiohttp.ClientSession() as session:
                for attempt in range(2):  # transient VRAM-swap / stale-warmed-ctx 400s: one retry
                    async with session.post(
                        f"{self.base_url}/api/chat",
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                    ) as resp:
                        if resp.status != 200:
                            error_text = await resp.text()
                            logger.error(f"Ollama stream error {resp.status} (attempt {attempt + 1}/2): {error_text}")
                            if attempt == 0:
                                if "exceed" in error_text.lower() and "context" in error_text.lower():
                                    # The cached "warmed" ctx was too small for this prompt (e.g. a
                                    # stray raw call previously loaded the model with Ollama's 2048
                                    # default). Drop the stale cache entry and force a fresh load
                                    # sized for the actual conversation instead of blind-retrying
                                    # the same too-small payload.
                                    logger.warning(
                                        f"Ollama: warmed ctx too small for {chosen_model} — forcing reload with larger ctx"
                                    )
                                    ghost_opts = await self._get_ghost_options(chosen_model, max(num_ctx, 8192))
                                    opts = {
                                        "temperature": temperature,
                                        "keep_alive": KEEP_ALIVE_SECONDS,
                                        **ghost_opts,
                                    }
                                    payload["options"] = opts
                                    effective_ctx = opts.get("num_ctx", num_ctx)
                                    is_warmed = False
                                else:
                                    await _asyncio.sleep(1.5)
                                continue
                            yield f"[Error {resp.status} from Ollama: {error_text[:200]}]"
                            return

                        first_token = True
                        import json
                        async for line in resp.content:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                data = json.loads(line)
                                token = data.get("message", {}).get("content", "")
                                if token:
                                    if first_token and not is_warmed:
                                        # Model loaded successfully — register in warmed dict
                                        mark_warmed(chosen_model, effective_ctx)
                                        first_token = False
                                    yield token
                                if data.get("done"):
                                    return
                            except Exception:
                                continue
                        return
        except aiohttp.ClientConnectorError:
            yield "[Error: Cannot connect to Ollama — run: ollama serve]"
        except Exception as e:
            yield f"[Error: {e}]"

    async def generate_with_tools(
        self,
        messages: List[Message],
        tools: list[dict],
        temperature: float = 0.7,
        model: Optional[str] = None,
        num_ctx: int = 8192,
    ) -> tuple[str, list[dict]]:
        """
        Send messages + tool specs. Returns (content, tool_calls).
        tool_calls: list of {name, arguments}
        Empty tool_calls means model answered directly in content.
        """
        chat_messages = [{"role": m.role, "content": m.content} for m in messages]
        payload = {
            "model": model or self.model,
            "messages": chat_messages,
            "tools": tools,
            "stream": False,
            "options": {"temperature": temperature, "num_ctx": num_ctx},
        }
        try:
            async with aiohttp.ClientSession() as session:
                data = None
                for attempt in range(2):
                    async with session.post(
                        f"{self.base_url}/api/chat",
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            break
                        error_text = await response.text()
                        logger.error(f"Ollama tool-call error {response.status} (attempt {attempt + 1}/2): {error_text}")
                        # Same stale-warmed-ctx self-heal as stream_response: the
                        # tool-call prompt (system + tool specs + memory) is often
                        # bigger than the model's warmed ctx. Bump ctx and retry once.
                        if attempt == 0 and "exceed" in error_text.lower() and "context" in error_text.lower():
                            import re as _re
                            m = _re.search(r'(\d+)\s*tokens?\)', error_text)
                            needed = int(m.group(1)) if m else num_ctx * 2
                            new_ctx = min(16384, max(num_ctx, needed) + 1024)
                            payload["options"]["num_ctx"] = new_ctx
                            logger.warning(f"Ollama tool-call: bumping ctx to {new_ctx} and retrying")
                            continue
                        return "", []
                if data is None:
                    return "", []
                msg = data.get("message", {})
                content = msg.get("content", "").strip()
                raw_calls = msg.get("tool_calls", [])
                tool_calls = [
                    {
                        "name": c["function"]["name"],
                        "arguments": c["function"].get("arguments", {}),
                    }
                    for c in raw_calls
                    if "function" in c
                ]
                return content, tool_calls
        except aiohttp.ClientConnectorError:
            return "", []
        except Exception as e:
            logger.error(f"generate_with_tools failed: {e}")
            return "", []

    async def list_models(self) -> list:
        """Return list of models available in Ollama."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
        return []
