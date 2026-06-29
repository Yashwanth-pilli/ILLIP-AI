"""
Hardware detector — reads CPU, RAM, GPU safely (read-only, no modifications).
Used to auto-select models and set resource limits.
"""

import subprocess
import platform
from dataclasses import dataclass, field
from typing import Optional
from app.utils import logger

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False


@dataclass
class HardwareInfo:
    cpu_cores: int = 0
    cpu_name: str = "Unknown"
    ram_gb: float = 0.0
    ram_available_gb: float = 0.0
    gpu_name: str = "Unknown"
    gpu_vram_gb: float = 0.0
    gpu_shared_vram_gb: float = 0.0   # Windows shared GPU memory (system RAM as virtual VRAM)
    os: str = platform.system()
    tier: int = 1  # 1=low, 2=mid, 3=good, 4=high-end
    recommended_model: str = "qwen2.5:3b"
    max_context: int = 4096
    safe_threads: int = 4
    warnings: list = field(default_factory=list)


def _get_gpu_info_nvidia() -> tuple[str, float]:
    """Query nvidia-smi for GPU name and VRAM. Returns (name, vram_gb)."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(",")
            name = parts[0].strip()
            vram_mib = float(parts[1].strip())
            return name, round(vram_mib / 1024, 1)
    except FileNotFoundError:
        pass  # nvidia-smi not installed — no NVIDIA GPU or driver
    except Exception as e:
        logger.debug(f"GPU detection failed: {e}")
    return "Unknown", 0.0


def _get_gpu_info_windows_wmi() -> tuple[str, float]:
    """Fallback GPU detection via wmic on Windows."""
    try:
        result = subprocess.run(
            ["wmic", "path", "win32_VideoController", "get", "Name,AdapterRAM", "/format:csv"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 3 and parts[1].isdigit():
                    vram_bytes = int(parts[1])
                    name = parts[2]
                    if vram_bytes > 0:
                        return name, round(vram_bytes / (1024 ** 3), 1)
    except Exception:
        pass
    return "Unknown", 0.0


def detect_hardware() -> HardwareInfo:
    info = HardwareInfo()

    # CPU + RAM via psutil
    if _PSUTIL_AVAILABLE:
        try:
            vm = psutil.virtual_memory()
            info.ram_gb = round(vm.total / (1024 ** 3), 1)
            info.ram_available_gb = round(vm.available / (1024 ** 3), 1)
            info.cpu_cores = psutil.cpu_count(logical=False) or psutil.cpu_count() or 2
        except Exception as e:
            logger.warning(f"psutil read failed: {e}")
    else:
        info.warnings.append("psutil not installed — RAM/CPU data unavailable. Run: pip install psutil")

    # GPU
    gpu_name, vram_gb = _get_gpu_info_nvidia()
    if gpu_name == "Unknown" and platform.system() == "Windows":
        gpu_name, vram_gb = _get_gpu_info_windows_wmi()
    info.gpu_name = gpu_name
    info.gpu_vram_gb = vram_gb

    # Windows Shared GPU Memory — NVIDIA driver lets GPU use system RAM as virtual VRAM.
    # Available on Windows + dedicated NVIDIA GPU. Cap at 8GB; treat as slow VRAM (3-5x penalty).
    if platform.system() == "Windows" and vram_gb > 0 and info.ram_available_gb > 4:
        info.gpu_shared_vram_gb = round(min(info.ram_available_gb * 0.4, 8.0), 1)

    # Determine tier
    # Tier 4: RTX-class GPU with 8GB+ VRAM
    # Tier 3: Good GPU (4-8GB VRAM) or lots of RAM (32GB+)
    # Tier 2: Mid (16GB RAM or 2-4GB GPU)
    # Tier 1: Low-end
    if vram_gb >= 8:
        info.tier = 4
    elif vram_gb >= 4 or info.ram_gb >= 32:
        info.tier = 3
    elif info.ram_gb >= 16:
        info.tier = 2
    else:
        info.tier = 1

    # Model and context recommendations (safe for each tier)
    tier_config = {
        4: ("qwen2.5:7b",  8192, max(1, info.cpu_cores - 2)),
        3: ("qwen2.5:7b",  8192, max(1, info.cpu_cores - 2)),
        2: ("qwen2.5:3b",  4096, max(1, (info.cpu_cores or 4) - 2)),
        1: ("qwen2.5:1.5b", 2048, 2),
    }
    info.recommended_model, info.max_context, info.safe_threads = tier_config[info.tier]

    # Safety warnings
    if info.ram_available_gb > 0 and info.ram_available_gb < 2:
        info.warnings.append("Very low free RAM (<2GB). Close other apps before running models.")
    if info.gpu_vram_gb == 0 and info.tier <= 2:
        info.warnings.append("No dedicated GPU detected. Models will run on CPU — expect slower responses.")

    logger.info(
        f"Hardware: tier={info.tier}, RAM={info.ram_gb}GB, "
        f"GPU={info.gpu_name} {info.gpu_vram_gb}GB VRAM, "
        f"recommended={info.recommended_model}"
    )
    return info


# Cache result — hardware doesn't change at runtime
_cached: Optional[HardwareInfo] = None


def get_hardware_info() -> HardwareInfo:
    global _cached
    if _cached is None:
        _cached = detect_hardware()
    return _cached
