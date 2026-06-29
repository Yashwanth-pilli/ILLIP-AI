"""
Ghost GPU Engine v2 — dynamic model optimizer.

Zero hardcoding. Queries Ollama /api/show for real architecture data.
Falls back to name-based estimation only when Ollama is offline.

Pipeline:
  1. get_model_profile()   — real params/quant/layers from Ollama
  2. calculate_plan()      — VRAM split: full_gpu / kv_offload / hybrid / cpu_only
  3. find_draft_model()    — pick smallest installed model for speculative decoding
  4. GhostPlan             — ollama_options dict ready to pass to /api/chat
"""

import re
import asyncio
import aiohttp
from dataclasses import dataclass, field
from typing import Optional
from app.utils import logger

# Safety buffers — never use all VRAM/RAM
_VRAM_SAFETY_GB = 1.0   # reserve for driver + OS
_RAM_SAFETY_GB  = 2.0   # reserve for OS
_TEMP_HARD_LIMIT = 85   # °C — refuse to increase load above this


@dataclass
class ModelProfile:
    name: str
    param_billions: float
    quantization: str          # e.g. "Q4_K_M"
    bits_per_param: float      # derived from quant
    num_layers: int
    vram_needed_gb: float      # model weights VRAM only
    source: str                # "ollama_live" | "name_estimate"
    hidden_size: int = 0       # embedding dim (from Ollama model_info)
    kv_heads: int = 0          # GQA KV head count


@dataclass
class GhostPlan:
    model: str
    strategy: str              # full_gpu | kv_offload | hybrid | cpu_only
    gpu_layers: int
    cpu_layers: int
    total_layers: int
    vram_used_gb: float
    ram_used_gb: float
    context_limit: int
    threads: int
    feasible: bool
    warnings: list[str] = field(default_factory=list)
    ollama_options: dict = field(default_factory=dict)
    draft_model: Optional[str] = None   # set if speculative decoding available


# Quantization → bits per weight
_QUANT_BITS: dict[str, float] = {
    "Q2_K":   2.5,  "Q3_K_S": 3.0,  "Q3_K_M": 3.35, "Q3_K_L": 3.5,
    "Q4_0":   4.0,  "Q4_K_S": 4.0,  "Q4_K_M": 4.5,  "Q4_1":   4.5,
    "Q5_0":   5.0,  "Q5_K_S": 5.0,  "Q5_K_M": 5.5,  "Q5_1":   5.0,
    "Q6_K":   6.0,  "Q8_0":   8.0,
    "F16":   16.0,  "FP16":  16.0,
    "F32":   32.0,  "BF16":  16.0,
}


async def get_model_profile(model: str, base_url: str = "http://localhost:11434") -> ModelProfile:
    """
    Query Ollama /api/show for real model architecture.
    Falls back to name-based estimation if Ollama unreachable.
    """
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"{base_url}/api/show",
                json={"name": model},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                if resp.status != 200:
                    raise ValueError(f"Ollama /api/show returned {resp.status}")
                data = await resp.json()

        details    = data.get("details", {})
        model_info = data.get("model_info", {})

        # Exact param count from general.parameter_count (most accurate)
        exact_params = model_info.get("general.parameter_count")
        if exact_params:
            param_b = round(int(exact_params) / 1e9, 3)
        else:
            param_str = details.get("parameter_size", "") or ""
            m = re.search(r"([\d.]+)\s*[Bb]", param_str)
            param_b = float(m.group(1)) if m else _estimate_params_from_name(model)

        # Quantization
        quant = details.get("quantization_level", "") or "Q4_K_M"
        bits  = _QUANT_BITS.get(quant, 4.5)

        # Layer count — Ollama stores as "{arch}.block_count" (e.g. qwen2.block_count)
        num_layers = 0
        for key, val in model_info.items():
            if key.endswith(".block_count"):
                try:
                    num_layers = int(val)
                    break
                except Exception:
                    pass
        if not num_layers:
            num_layers = _estimate_layers(param_b)

        # Hidden size for accurate KV cache calc — "{arch}.embedding_length"
        hidden_size = 0
        for key, val in model_info.items():
            if key.endswith(".embedding_length"):
                try:
                    hidden_size = int(val)
                    break
                except Exception:
                    pass

        # KV head count — "{arch}.attention.head_count_kv" (GQA support)
        kv_heads = 0
        for key, val in model_info.items():
            if key.endswith(".attention.head_count_kv"):
                try:
                    kv_heads = int(val)
                    break
                except Exception:
                    pass

        # Model weight VRAM (no KV cache here — calculated separately in calculate_plan)
        vram_gb = round(param_b * bits / 8 * 1.12, 2)

        return ModelProfile(
            name=model,
            param_billions=param_b,
            quantization=quant,
            bits_per_param=bits,
            num_layers=num_layers,
            vram_needed_gb=vram_gb,
            source="ollama_live",
            hidden_size=hidden_size or 0,
            kv_heads=kv_heads or 0,
        )

    except Exception as e:
        logger.debug(f"GhostEngine: /api/show failed for {model}: {e} — using name estimate")
        return _profile_from_name(model)


def _estimate_params_from_name(name: str) -> float:
    """Extract param count from model name e.g. qwen2.5:7b → 7.0"""
    m = re.search(r"(\d+(?:\.\d+)?)\s*[bB]", name)
    return float(m.group(1)) if m else 7.0


def _estimate_layers(param_b: float) -> int:
    """Estimate transformer layer count from param count (standard scaling)."""
    # Approximate: llama-style models scale layers roughly as param^0.45 * 5
    return max(16, int(param_b ** 0.45 * 5))


def _profile_from_name(model: str) -> ModelProfile:
    """Build ModelProfile from name alone — used when Ollama offline."""
    param_b    = _estimate_params_from_name(model)
    bits       = 4.5   # assume Q4_K_M — most common
    num_layers = _estimate_layers(param_b)
    vram_gb    = round(param_b * bits / 8 * 1.12, 2)
    return ModelProfile(
        name=model,
        param_billions=param_b,
        quantization="Q4_K_M (estimated)",
        bits_per_param=bits,
        num_layers=num_layers,
        vram_needed_gb=vram_gb,
        source="name_estimate",
    )


async def list_installed_models(base_url: str = "http://localhost:11434") -> list[dict]:
    """
    Returns list of installed models with name + size info.
    Each dict: {name, size_gb, param_billions (estimated)}
    """
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                f"{base_url}/api/tags",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
        models = []
        for m in data.get("models", []):
            name    = m.get("name", "")
            size_b  = m.get("size", 0)
            size_gb = round(size_b / 1e9, 2)
            param_b = _estimate_params_from_name(name)
            models.append({"name": name, "size_gb": size_gb, "param_billions": param_b})
        return sorted(models, key=lambda x: x["param_billions"])
    except Exception:
        return []


async def find_draft_model(
    target_model: str,
    base_url: str = "http://localhost:11434",
) -> Optional[str]:
    """
    Find the best draft model for speculative decoding.
    Rules:
    - Must be smaller than target (ideally <30% of target params)
    - Must be different model
    - Returns None if target is already small or no good draft exists
    """
    target_params = _estimate_params_from_name(target_model)
    if target_params < 7.0:
        return None   # target already small, speculation not worth it

    installed = await list_installed_models(base_url)
    candidates = [
        m for m in installed
        if m["name"] != target_model
        and m["param_billions"] <= target_params * 0.3   # <30% of target size
        and m["param_billions"] >= 1.0                   # at least 1B (too tiny = bad drafts)
    ]
    if not candidates:
        return None
    # Pick largest of the candidates (best draft quality while still fast)
    return max(candidates, key=lambda x: x["param_billions"])["name"]


async def calculate_plan(
    model: str,
    requested_ctx: int = 8192,
    base_url: str = "http://localhost:11434",
) -> GhostPlan:
    """
    Main entry point. Returns GhostPlan with ollama_options ready for /api/chat.
    Works for any model on any hardware — no hardcoding.
    """
    from app.hardware.guard import read_hardware_state_async
    from app.hardware.detector import get_hardware_info

    hw_state  = await read_hardware_state_async()
    hw        = get_hardware_info()
    profile   = await get_model_profile(model, base_url)

    warnings: list[str] = []

    if profile.source == "name_estimate":
        warnings.append(
            f"Ollama offline — using name-based estimate for {model}. "
            "Start Ollama for accurate planning."
        )

    # Safety: refuse to increase GPU load if already hot
    if hw_state.gpu_temp_c >= _TEMP_HARD_LIMIT:
        warnings.append(
            f"GPU at {hw_state.gpu_temp_c}°C — forcing CPU-only to prevent damage."
        )
        return _cpu_only_plan(profile, hw, requested_ctx, warnings)

    avail_vram_gb = max(0.0, (hw.gpu_vram_gb or 0.0) - _VRAM_SAFETY_GB)
    # Windows Shared GPU Memory: system RAM exposed as virtual VRAM by NVIDIA driver.
    # Use 50% of it (slower than dedicated VRAM) as extra headroom for layer placement.
    shared_vram_gb = getattr(hw, "gpu_shared_vram_gb", 0.0) * 0.5
    avail_vram_effective = avail_vram_gb + shared_vram_gb
    avail_ram_gb  = max(0.0, (hw.ram_available_gb or 4.0) - _RAM_SAFETY_GB)
    safe_threads  = max(2, (hw.cpu_cores or 4) - 2)

    # KV cache VRAM cost — accurate when Ollama provides hidden_size + kv_heads
    # Formula: 2(K+V) × kv_heads × head_dim × seq_len × 2bytes(fp16) × layers
    if profile.hidden_size > 0 and profile.kv_heads > 0:
        # Real values from model_info (GQA-aware)
        # head_dim = hidden_size / total_attn_heads — approximated as hidden/16 default
        # Since we have kv_heads, use: KV size = 2 × kv_heads × (hidden/kv_heads) × 2
        # = 2 × hidden_size × 2 / (total_heads/kv_heads) ... simplest: 2 × kv_heads × head_dim × 2
        # head_dim not directly available, estimate as hidden_size / max(kv_heads * 4, 16)
        estimated_total_heads = max(profile.kv_heads * 4, 8)
        head_dim = profile.hidden_size // estimated_total_heads
        kv_per_token_per_layer_bytes = 2 * profile.kv_heads * head_dim * 2
    elif profile.hidden_size > 0:
        # Have hidden size but not kv_heads — use full MHA estimate
        kv_per_token_per_layer_bytes = 2 * profile.hidden_size * 2
    else:
        # Fallback: rough estimate from param count (less accurate)
        params_m    = profile.param_billions * 1000
        hidden_dim  = int(64 * (params_m ** 0.4))   # conservative estimate
        kv_per_token_per_layer_bytes = 2 * hidden_dim * 2

    kv_total_gb = (
        requested_ctx * profile.num_layers * kv_per_token_per_layer_bytes / 1e9
    )

    # ── Strategy 1: Full GPU (model + KV fit in dedicated VRAM) ──
    if profile.vram_needed_gb + kv_total_gb <= avail_vram_gb:
        strategy   = "full_gpu"
        gpu_layers = profile.num_layers
        cpu_layers = 0
        vram_used  = profile.vram_needed_gb + kv_total_gb
        ram_used   = 0.1
        context    = requested_ctx
        kv_offload = False

    # ── Strategy 2: KV offload (model fits in dedicated VRAM but KV doesn't) ──
    elif profile.vram_needed_gb <= avail_vram_gb:
        strategy   = "kv_offload"
        gpu_layers = profile.num_layers
        cpu_layers = 0
        vram_used  = profile.vram_needed_gb
        ram_used   = kv_total_gb
        kv_offload = True
        # Max context = how many tokens fit in available RAM
        max_ctx_by_ram = int(
            avail_ram_gb * 1e9
            / (profile.num_layers * kv_per_token_per_layer_bytes)
        ) if profile.num_layers > 0 else requested_ctx
        context = min(requested_ctx, max(512, max_ctx_by_ram))
        if context < requested_ctx:
            warnings.append(
                f"KV cache needs {kv_total_gb:.1f}GB RAM — context reduced to {context}. "
                "Close other apps for more."
            )
        else:
            warnings.append("KV cache offloaded to CPU RAM. Slightly slower but model stays on GPU.")

    # ── Strategy 3: Hybrid split — uses dedicated + shared VRAM if available ──
    elif avail_vram_effective > 0.5:
        strategy        = "hybrid"
        vram_per_layer  = profile.vram_needed_gb / profile.num_layers
        gpu_layers      = max(1, int(avail_vram_effective / vram_per_layer))
        cpu_layers      = profile.num_layers - gpu_layers
        vram_used       = gpu_layers * vram_per_layer
        ram_per_cpu_lay = vram_per_layer   # similar size
        ram_used        = cpu_layers * ram_per_cpu_lay + kv_total_gb
        kv_offload      = True

        if ram_used > avail_ram_gb:
            # Shrink context to fit in RAM
            ram_for_kv  = max(0.1, avail_ram_gb - cpu_layers * ram_per_cpu_lay)
            max_ctx_ram = int(
                ram_for_kv * 1e9
                / (profile.num_layers * kv_per_token_per_layer_bytes)
            ) if profile.num_layers > 0 else 512
            context  = max(512, min(requested_ctx, max_ctx_ram))
            ram_used = cpu_layers * ram_per_cpu_lay + (
                context * profile.num_layers * kv_per_token_per_layer_bytes / 1e9
            )
            warnings.append(
                f"RAM tight — context reduced to {context}. Close other apps."
            )
        else:
            context = requested_ctx

        gpu_pct = int(gpu_layers / profile.num_layers * 100)
        if shared_vram_gb > 0:
            warnings.append(
                f"Hybrid: {gpu_pct}% layers on GPU (using Windows shared VRAM), "
                f"{100-gpu_pct}% on CPU. Shared VRAM is slower than dedicated."
            )
        else:
            warnings.append(
                f"Hybrid: {gpu_pct}% layers on GPU, {100-gpu_pct}% on CPU. "
                f"Expect {100 - gpu_pct}% speed reduction vs full GPU."
            )

    # ── Strategy 4: CPU only ──
    else:
        return _cpu_only_plan(profile, hw, requested_ctx, warnings)

    feasible = ram_used <= avail_ram_gb or strategy in ("full_gpu", "kv_offload")
    if not feasible:
        warnings.append(
            f"Not enough RAM ({hw.ram_available_gb:.0f}GB free) for {model}. "
            f"Need ~{ram_used:.1f}GB. Use a smaller model."
        )

    # Ollama options — passed to /api/chat on FIRST load only
    ollama_options = {
        "num_gpu":    gpu_layers,
        "num_thread": safe_threads,
        "num_ctx":    context,
        "use_mmap":   True,
        # mlock: only lock if fits fully in GPU (no CPU layers competing for RAM)
        "use_mlock":  cpu_layers == 0 and ram_used < avail_ram_gb,
    }

    # Find draft model for speculative decoding (async, non-blocking)
    try:
        draft = await find_draft_model(model, base_url)
    except Exception:
        draft = None

    plan = GhostPlan(
        model=model,
        strategy=strategy,
        gpu_layers=gpu_layers,
        cpu_layers=cpu_layers,
        total_layers=profile.num_layers,
        vram_used_gb=round(vram_used, 2),
        ram_used_gb=round(ram_used, 2),
        context_limit=context,
        threads=safe_threads,
        feasible=feasible,
        warnings=warnings,
        ollama_options=ollama_options,
        draft_model=draft,
    )

    logger.info(
        f"GhostEngine: {model} ({profile.param_billions}B {profile.quantization}) | "
        f"strategy={strategy} | gpu={gpu_layers}/{profile.num_layers} layers | "
        f"VRAM={vram_used:.1f}GB | ctx={context}"
        + (f" | draft={draft}" if draft else "")
    )
    return plan


def _cpu_only_plan(profile: ModelProfile, hw, requested_ctx: int, warnings: list[str]) -> GhostPlan:
    safe_threads = max(2, (hw.cpu_cores or 4) - 2)
    warnings.append(
        "Running on CPU only. Expect slow responses (~1-3 tok/s). "
        "Consider a smaller/more quantized model."
    )
    return GhostPlan(
        model=profile.name,
        strategy="cpu_only",
        gpu_layers=0,
        cpu_layers=profile.num_layers,
        total_layers=profile.num_layers,
        vram_used_gb=0.0,
        ram_used_gb=profile.vram_needed_gb,
        context_limit=min(requested_ctx, 2048),
        threads=safe_threads,
        feasible=True,
        warnings=warnings,
        ollama_options={
            "num_gpu":    0,
            "num_thread": safe_threads,
            "num_ctx":    min(requested_ctx, 2048),
            "use_mmap":   True,
            "use_mlock":  False,
        },
        draft_model=None,
    )


async def recommend_model(base_url: str = "http://localhost:11434") -> Optional[str]:
    """
    From installed Ollama models, pick the best one current hardware can run fully on GPU.
    Falls back to largest hybrid-feasible model.
    No hardcoded model names — reads installed models dynamically.
    """
    from app.hardware.detector import get_hardware_info
    hw         = get_hardware_info()
    avail_vram = max(0.0, (hw.gpu_vram_gb or 0.0) - _VRAM_SAFETY_GB)
    avail_ram  = max(0.0, (hw.ram_available_gb or 4.0) - _RAM_SAFETY_GB)
    installed  = await list_installed_models(base_url)

    if not installed:
        return None

    # Prefer models that fit entirely in GPU VRAM
    for m in reversed(installed):   # largest first
        profile = await get_model_profile(m["name"], base_url)
        if profile.vram_needed_gb <= avail_vram:
            return m["name"]

    # Fall back: largest that fits in RAM for hybrid/CPU
    for m in reversed(installed):
        if m["size_gb"] <= avail_ram:
            return m["name"]

    return installed[0]["name"]   # smallest available
