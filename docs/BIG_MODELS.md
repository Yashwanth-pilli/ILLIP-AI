# Running huge models (70B–120B) on a laptop — safely

Yes, ILLIP can run a 120B model on your 8GB laptop. It will not damage anything.
But be honest with yourself about speed: huge models on small GPUs are **correct,
not fast**. Here is exactly how it works and how to turn it on.

## Why it is safe (your hardware cannot be hurt)

Two independent guards, both already built in:

1. **Thermal governor** (`app/hardware/ghost_engine.py`, `safety_monitor.py`):
   ILLIP refuses to raise GPU load above **85°C** and drops to CPU. A background
   monitor reads GPU temp + VRAM every 5s and shrinks context under pressure.
   Sustained damage from heat is physically prevented.
2. **Layer streaming, not GPU-max**: a 120B model does not sit fully on the GPU.
   AirLLM streams one layer at a time from disk/RAM through the GPU. The GPU is
   busy in short bursts, not pinned at 100% for minutes — the opposite of the
   thermal-stress pattern that wears hardware. The bottleneck is disk/RAM, which
   is safe; a too-big model simply **fails the request**, it does not harm parts.

Battery note: heavy inference on battery is slow and drains fast. ILLIP's
`/doctor` warns you when you are on battery. For 70B+ work, **plug in** — not for
safety, for speed and so the run finishes.

## The three real options (pick by what you actually need)

| Goal | Model | How | Speed on RTX 4060 8GB |
|---|---|---|---|
| **Daily driver** (recommended) | `qwen2.5:7b` (default) | Ollama, full GPU | fast, real-time |
| **Best quality that is still usable** | `qwen2.5:14b` or `32b` Q4 | Ollama, Ghost Engine hybrid split | 3–10 tok/s |
| **Actually run 70B–120B** | HF model via AirLLM | layer streaming from disk | ~0.5 tok/s (minutes/answer) |

The honest recommendation: **14B–32B quantized** gets you ~90% of flagship quality
at usable speed. 120B at 0.5 tok/s is a real capability but a party trick for day-to-day.

## Enable a 70B–120B model (AirLLM)

AirLLM is already wired as a provider (`app/providers/airllm_provider.py`).

1. Install: `pip install airllm`
2. Free disk space: a 120B 4-bit model is **~60–70GB on disk**. Check with `/doctor`.
3. Set in `.env`:
   ```
   MODEL_PROVIDER=airllm
   AIRLLM_MODEL=<huggingface-id>        # e.g. a 70B/120B causal LM you have rights to
   AIRLLM_COMPRESSION=4bit              # 4bit keeps RAM/disk lower
   AIRLLM_MAX_TOKENS=512
   ```
4. Restart ILLIP. First run downloads weights (slow, one time).

Model policy still applies (no DeepSeek; Qwen/Llama/Mistral/Phi/Gemma/Granite/
Nemotron families). Qwen2.5-72B is a strong, allowed choice for the 70B tier.

## Why this beats "buy a bigger GPU"

The whole point of ILLIP is that hardware never fully blocks you. Weak laptop →
auto-downgrade to a small fast model. Strong laptop → bigger models on GPU. Need a
giant model once → AirLLM streams it from disk, slowly but really. Nobody is locked
out; the system adapts to the machine it is on.
