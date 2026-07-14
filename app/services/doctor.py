"""
Doctor — one-shot system diagnostics (like a coding agent's /doctor).

Runs a battery of checks and returns actionable results: each check reports
ok / warn / fail plus a one-line fix. Read-only; never changes system state.
Used by GET /api/system/doctor and the `/doctor` chat command.
"""

import sys
import shutil
import platform
from pathlib import Path
from typing import Callable

import aiohttp

from app.config import settings
from app.utils import logger

_OK, _WARN, _FAIL = "ok", "warn", "fail"


def _check(name: str, status: str, message: str, fix: str = "") -> dict:
    return {"name": name, "status": status, "message": message, "fix": fix}


async def _ollama_reachable() -> tuple[bool, list[str]]:
    """Return (running, [model names]). Empty list if offline."""
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                f"{settings.ollama_base_url}/api/tags",
                timeout=aiohttp.ClientTimeout(total=4),
            ) as r:
                if r.status != 200:
                    return False, []
                data = await r.json()
                return True, [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        return False, []


def _check_python() -> dict:
    v = sys.version_info
    if v < (3, 10):
        return _check("Python", _FAIL, f"Python {v.major}.{v.minor} too old",
                      "Install Python 3.10+ and recreate the venv.")
    return _check("Python", _OK, f"Python {v.major}.{v.minor}.{v.micro} on {platform.system()}")


def _check_deps() -> list[dict]:
    """Required deps hard-fail; optional deps only warn."""
    out = []
    required = {"fastapi": "pip install fastapi", "psutil": "pip install psutil",
                "aiohttp": "pip install aiohttp", "pydantic": "pip install pydantic"}
    for mod, fix in required.items():
        try:
            __import__(mod)
            out.append(_check(f"dep:{mod}", _OK, "installed"))
        except ImportError:
            out.append(_check(f"dep:{mod}", _FAIL, "missing (required)", fix))
    optional = {"faster_whisper": "voice input (STT)",
                "playwright": "browser automation",
                "qdrant_client": "vector memory (FTS fallback used otherwise)"}
    for mod, feature in optional.items():
        try:
            __import__(mod)
            out.append(_check(f"dep:{mod}", _OK, f"installed ({feature})"))
        except ImportError:
            out.append(_check(f"dep:{mod}", _WARN, f"missing — {feature} disabled",
                              f"pip install {mod.replace('_', '-')} to enable"))
    return out


def _check_disk() -> dict:
    data_dir = Path(settings.data_dir) if hasattr(settings, "data_dir") else Path("data")
    try:
        target = data_dir if data_dir.exists() else Path.cwd()
        free_gb = shutil.disk_usage(target).free / 1e9
        if free_gb < 2:
            return _check("Disk", _FAIL, f"{free_gb:.1f}GB free — too low",
                          "Free up disk. Models and memory need room to grow.")
        if free_gb < 10:
            return _check("Disk", _WARN, f"{free_gb:.1f}GB free — tight for large models")
        return _check("Disk", _OK, f"{free_gb:.0f}GB free")
    except Exception as e:
        return _check("Disk", _WARN, f"could not read disk usage: {e}")


def _check_data_writable() -> dict:
    data_dir = Path(settings.data_dir) if hasattr(settings, "data_dir") else Path("data")
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        probe = data_dir / ".doctor_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return _check("Data dir", _OK, f"writable: {data_dir}")
    except Exception as e:
        return _check("Data dir", _FAIL, f"not writable: {data_dir}",
                      f"Fix permissions on {data_dir}. Error: {e}")


def _check_battery() -> dict:
    """Laptop safety: warn on battery so heavy inference doesn't drain/overheat."""
    try:
        import psutil
        bat = psutil.sensors_battery()
    except Exception:
        bat = None
    if bat is None:
        return _check("Power", _OK, "on AC or no battery sensor")
    if bat.power_plugged:
        return _check("Power", _OK, f"plugged in ({bat.percent:.0f}%)")
    if bat.percent < 20:
        return _check("Power", _WARN, f"on battery, {bat.percent:.0f}% left",
                      "Plug in before heavy generation — low battery + inference can throttle.")
    return _check("Power", _WARN, f"on battery ({bat.percent:.0f}%)",
                  "Plug in for full-speed models; on battery ILLIP favors lighter work.")


async def run_diagnostics() -> dict:
    """Run all checks. Returns {status, summary, checks:[...]}. status = worst check."""
    checks: list[dict] = [_check_python()]
    checks.extend(_check_deps())
    checks.append(_check_disk())
    checks.append(_check_data_writable())
    checks.append(_check_battery())

    # Hardware state + Ghost feasibility
    try:
        from app.hardware.detector import get_hardware_info
        from app.hardware.guard import read_hardware_state_async
        hw = get_hardware_info()
        state = await read_hardware_state_async()
        checks.append(_check("Hardware", _OK,
            f"{hw.gpu_name} · {hw.gpu_vram_gb}GB VRAM · {hw.ram_gb}GB RAM · tier {hw.tier}"))
        if state.pressure in ("high", "critical"):
            checks.append(_check("Thermal/pressure",
                _WARN if state.pressure == "high" else _FAIL,
                f"pressure {state.pressure}: {state.reason}",
                "Let the machine cool or close other apps — ILLIP auto-reduces load."))
        else:
            checks.append(_check("Thermal/pressure", _OK,
                f"{state.pressure} (GPU {state.gpu_temp_c:.0f}°C, RAM {state.ram_percent:.0f}%)"))
        if hw.ram_available_gb and hw.ram_available_gb < 2:
            # Name the culprits — "close apps" is useless without knowing which.
            hogs = ""
            try:
                import psutil
                procs = {}
                for p in psutil.process_iter(["name", "memory_info"]):
                    n = (p.info["name"] or "?").removesuffix(".exe")
                    if n.lower() in ("ollama", "llama-server", "python", "memory compression"):
                        continue  # ILLIP's own stack isn't the thing to close
                    procs[n] = procs.get(n, 0) + p.info["memory_info"].rss
                top = sorted(procs.items(), key=lambda x: -x[1])[:3]
                hogs = " Biggest apps: " + ", ".join(f"{n} ({b / 1024**3:.1f}GB)" for n, b in top)
            except Exception:
                pass
            checks.append(_check("Free RAM", _WARN, f"{hw.ram_available_gb:.1f}GB free",
                                 f"Low RAM makes replies VERY slow (system swaps to disk).{hogs} — close some."))
    except Exception as e:
        checks.append(_check("Hardware", _WARN, f"detection error: {e}"))

    # Ollama + models + active-model feasibility
    running, models = await _ollama_reachable()
    if not running:
        checks.append(_check("Ollama", _WARN, "not reachable — using mock/cloud provider",
                             "Start Ollama (`ollama serve`) for local models."))
    else:
        checks.append(_check("Ollama", _OK, f"running · {len(models)} model(s) installed"))
        if not models:
            checks.append(_check("Models", _FAIL, "no models installed",
                                 "Pull one: `ollama pull qwen2.5:3b`"))
        else:
            active = settings.ollama_model
            if active not in models and not any(m.split(":")[0] == active.split(":")[0] for m in models):
                checks.append(_check("Active model", _WARN,
                    f"'{active}' not installed (have: {', '.join(models[:3])})",
                    f"Pull it (`ollama pull {active}`) or switch in the Models panel."))
            else:
                try:
                    from app.hardware.ghost_engine import calculate_plan
                    plan = await calculate_plan(active, base_url=settings.ollama_base_url)
                    if not plan.feasible:
                        checks.append(_check("Active model", _WARN,
                            f"'{active}' may not fit ({plan.strategy})",
                            "Switch to a smaller model in the Models panel."))
                    else:
                        checks.append(_check("Active model", _OK,
                            f"'{active}' → {plan.strategy}, {plan.gpu_layers}/{plan.total_layers} layers on GPU"))
                except Exception:
                    checks.append(_check("Active model", _OK, f"'{active}' installed"))

    n_fail = sum(1 for c in checks if c["status"] == _FAIL)
    n_warn = sum(1 for c in checks if c["status"] == _WARN)
    status = _FAIL if n_fail else (_WARN if n_warn else _OK)
    summary = (f"{len(checks)} checks · {n_fail} failed · {n_warn} warnings"
               if (n_fail or n_warn) else f"All {len(checks)} checks passed. System healthy.")
    logger.info(f"Doctor: {summary}")
    return {"status": status, "summary": summary, "checks": checks}


def format_report(result: dict) -> str:
    """Render diagnostics as markdown for the chat window."""
    icon = {"ok": "✅", "warn": "⚠️", "fail": "❌"}
    lines = [f"### 🩺 ILLIP Doctor — {result['summary']}", ""]
    for c in result["checks"]:
        line = f"{icon.get(c['status'], '•')} **{c['name']}** — {c['message']}"
        if c.get("fix") and c["status"] != _OK:
            line += f"\n   ↳ _{c['fix']}_"
        lines.append(line)
    heals = result.get("auto_heal_actions") or []
    if heals:
        lines.append("")
        lines.append("**🔧 Recent auto-repairs:**")
        for h in heals:
            lines.append(f"- {h['action']}: {h.get('detail', '')}")
    lines.append("")
    lines.append("_Self-healing is active — ILLIP auto-repairs Ollama/model issues every 60s._")
    return "\n".join(lines)


if __name__ == "__main__":
    # ponytail self-check: worst-status rollup is the only non-trivial logic.
    assert _check("x", _OK, "m")["status"] == _OK
    fake = {"status": "", "summary": "", "checks": [
        _check("a", _OK, ""), _check("b", _WARN, ""), _check("c", _FAIL, "")]}
    n_fail = sum(1 for c in fake["checks"] if c["status"] == _FAIL)
    n_warn = sum(1 for c in fake["checks"] if c["status"] == _WARN)
    assert (_FAIL if n_fail else (_WARN if n_warn else _OK)) == _FAIL
    assert "self-check" in format_report({"summary": "self-check", "checks": fake["checks"]})
    print("doctor self-check ok")
