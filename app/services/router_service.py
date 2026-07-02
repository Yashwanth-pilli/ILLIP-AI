"""
Model router — classifies task complexity, checks hardware, returns best model.

Small model (3b): routing, simple Q&A, short code, greetings, tool selection.
Large model (7b): deep reasoning, long code, analysis, multi-step planning.
"""

import re
from app.hardware.guard import read_hardware_state_async, HardwareState
from app.config import settings
from app.utils import logger

_SMALL_FAMILIES = ["qwen2.5:3b", "qwen2.5:1.5b", "phi3:mini", "gemma2:2b", "llama3.2:3b"]
_LARGE_FAMILIES = ["qwen2.5:7b", "qwen2.5:14b", "llama3.1:8b", "mistral:7b", "phi3:medium"]
SMALL = "qwen2.5:3b"
LARGE = "qwen2.5:7b"

def _detect_models() -> None:
    """Detect installed Ollama models and update SMALL/LARGE globals dynamically."""
    global SMALL, LARGE
    import subprocess, json
    try:
        r = subprocess.run(["ollama", "list", "--json"], capture_output=True, text=True, timeout=3)
        models = {m["name"] for m in (json.loads(r.stdout) if r.stdout.strip().startswith("[") else {}).get("models", [])} if r.returncode == 0 else set()
    except Exception:
        try:
            r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=3)
            models = {line.split()[0] for line in r.stdout.strip().splitlines()[1:] if line.strip()}
        except Exception:
            return
    for m in _SMALL_FAMILIES:
        if any(installed.startswith(m.split(":")[0]) for installed in models):
            SMALL = next(i for i in models if i.startswith(m.split(":")[0]))
            break
    for m in _LARGE_FAMILIES:
        if any(installed.startswith(m.split(":")[0]) for installed in models):
            LARGE = next(i for i in models if i.startswith(m.split(":")[0]))
            break

_detect_models()

# Patterns that signal complex tasks needing the large model
_COMPLEX = [
    r'\b(analyze|analyse|compare|evaluate|critique|examine in detail)\b',
    r'\b(write a complete|implement|design|build|create an? (app|system|module|class|api|tool|bot|script|scraper))\b',
    r'\b(plan|outline|architect|scaffold|structure|draft)\b.{5,}',
    r'\b(step[- ]by[- ]step|explain (why|how)|walk me through)\b',
    r'\b(debug|refactor|optimize|review (this )?(code|function|class))\b',
    r'\b(how (do|does|can|should|would) (i|you|we))\b.{10,}',
    r'\b(python|javascript|typescript|java|go|rust|sql|html|css)\b.{10,}',
    r'\b(code|function|class|method|api|endpoint|database|schema)\b.{10,}',
    r'```',
    r'\n.*\n.*\n',
]

_SIMPLE = [
    r'^(hi|hello|hey|yo|sup|what\'?s up)[!?.]?$',
    r'^(thanks?|thank you|ok|okay|cool|got it|sure)[!?.]?$',
]

# Patterns that trigger automatic web search
_NEEDS_SEARCH = [
    r'\b(latest|recent|current|today|yesterday|this week|this month|right now|live)\b',
    r'\b(news|headline|update|announcement|release|launch|breaking)\b',
    r'\b(20(2[4-9]|3\d))\b',                    # years 2024-2039 (current/future)
    r'\b(price|cost|rate|stock|crypto|weather|score|result|winner)\b',
    r'\b(who (is|are|was|were))\b',
    r'\bwhat (is|are) (?![\d\s+\-*/^().,]+\??\s*$)[a-zA-Z].{2,28}\?',  # "what is X?" but not math
    r'\b(search|find|look up|google|check online)\b',
    r'\b(github\.com|youtube\.com|twitter|reddit|instagram)\b',
    r'\bhow (much|many) .{1,40}\?',
    r'\bwhen (is|was|does|did) .{1,40}\?',
]

# Patterns that block search even if _NEEDS_SEARCH matches
_NO_SEARCH = [
    r'^[\d\s+\-*/^().,=]+[?]?\s*$',          # pure arithmetic: "2+2", "12*8?"
    r'\b(calculate|compute|solve|simplify)\b',
    r'\b(convert|how many .*(byte|kb|mb|gb|kg|lb|km|mile|inch|foot|feet|celsius|fahrenheit))',
]

_NO_SEARCH_RE = [re.compile(p, re.IGNORECASE) for p in _NO_SEARCH]

_COMPLEX_RE      = [re.compile(p, re.IGNORECASE) for p in _COMPLEX]
_SIMPLE_RE       = [re.compile(p, re.IGNORECASE) for p in _SIMPLE]
_SEARCH_RE       = [re.compile(p, re.IGNORECASE) for p in _NEEDS_SEARCH]


def _classify(message: str) -> str:
    msg = message.strip()
    if any(p.search(msg) for p in _SIMPLE_RE):
        return "simple"
    if any(p.search(msg) for p in _COMPLEX_RE):
        return "complex"
    if len(msg) > 300:
        return "complex"
    if len(msg) > 80:
        return "medium"
    return "simple"


def _should_search(message: str) -> bool:
    """Auto-detect if query needs live web search."""
    msg = message.strip()
    if any(p.search(msg) for p in _NO_SEARCH_RE):
        return False
    return any(p.search(msg) for p in _SEARCH_RE)


async def route(message: str, ceiling_model: str = None) -> dict:
    """
    ceiling_model = user's dropdown selection (max allowed model).
    Router can pick SMALLER than ceiling based on task + hardware.
    Router NEVER picks larger than ceiling.

    Returns:
        {
          "model": "qwen2.5:3b",
          "context_limit": 8192,
          "complexity": "simple",
          "pressure": "low",
          "reason": "...",
          "warning": ""   # non-empty when hardware is struggling
        }
    """
    hw = await read_hardware_state_async()
    complexity = _classify(message)
    warning = ""

    # Step 1: pick based on task complexity
    if complexity == "simple":
        ideal = SMALL
    else:  # medium or complex → large
        ideal = LARGE

    # Step 2: hardware guard — critical forces SMALL; high just warns (user's 4060 can handle it)
    if hw.pressure == "critical":
        model = SMALL
        reason = f"Hardware critical ({hw.reason}) — forced {SMALL}"
        warning = f"⚠️ System under heavy load ({hw.reason}). Switched to fast mode. Close other apps."
    else:
        model = ideal
        reason = f"{complexity} task → {ideal}"
        if hw.pressure == "high":
            warning = f"🔶 High system load detected. Consider closing other apps."

    # Step 3: if user explicitly pinned a model, honour it (unless hardware critical)
    if ceiling_model and hw.pressure != "critical":
        model_rank = {SMALL: 1, LARGE: 2, "qwen2.5:14b": 3}
        if model_rank.get(ceiling_model, 1) >= model_rank.get(model, 1):
            model = ceiling_model
            reason += f" (user pinned {ceiling_model})"

    from app.hardware.guard import get_safe_context_limit
    ctx = get_safe_context_limit(hw, requested=8192)
    needs_search = _should_search(message)

    logger.info(f"Router: complexity={complexity} pressure={hw.pressure} search={needs_search} -> {model}")

    return {
        "model": model,
        "context_limit": ctx,
        "complexity": complexity,
        "pressure": hw.pressure,
        "gpu_temp": hw.gpu_temp_c,
        "vram_percent": round(hw.vram_percent, 1),
        "ram_percent": hw.ram_percent,
        "reason": reason,
        "warning": warning,
        "needs_search": needs_search,
    }
