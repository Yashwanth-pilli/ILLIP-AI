"""
Model router — classifies task complexity, checks hardware, returns best model.

Small model (3b): routing, simple Q&A, short code, greetings, tool selection.
Large model (7b): deep reasoning, long code, analysis, multi-step planning.
"""

import re
from app.hardware.guard import read_hardware_state_async, HardwareState
from app.config import settings
from app.utils import logger

# Small = fast everyday model (full-GPU, snappy). Large = big-brain model for hard
# tasks. Prefer MoE for LARGE: a 20-30B MoE activates only ~3-5B params per token,
# so it thinks big but computes small — the only way a "big" model runs decently
# on a low-end GPU. Dense 14B+ is intentionally NOT here (too cramped on 8GB).
# Everyday driver = 7b: full-GPU, instant, always hot, holds persona. This is what
# keeps ILLIP responsive. The big MoE (gpt-oss:20b) is NOT the auto-default — on
# 8GB it can't stay hot alongside 7b, and its complex-pipeline TTFT is slow for
# routine chat. It's reserved for explicit "Deep Think" (force_large / model pick),
# where the user wants max intelligence and accepts the wait.
# Brain = ornith:9b (5.6GB, full-GPU, built for agentic coding + terminal work).
# Deep brain = gpt-oss:20b MoE (on-demand, 23 tok/s hybrid). qwen kept as fallback.
# Three tiers on 8GB:
#   CHAT  = qwen2.5:7b — fast small-talk (greetings, banter). ~3s, no reasoning overhead.
#   SMALL = ornith:9b  — the brain: real questions, code, agents (reasons first, ~6s).
#   LARGE = gpt-oss:20b MoE — deep/on-demand.
# qwen and ornith can't both stay hot on 8GB, so a chat<->work switch reloads once;
# worth it because pure small-talk stays instant and real work gets the smart model.
_CHAT_FAMILIES  = ["qwen2.5:7b", "qwen2.5:3b", "llama3.2:3b", "mistral:7b"]
_SMALL_FAMILIES = ["ornith:9b", "qwen2.5:7b", "llama3.1:8b", "mistral:7b"]
_LARGE_FAMILIES = ["gpt-oss:20b", "ornith:9b", "qwen2.5:7b"]
CHAT  = "qwen2.5:7b"
SMALL = "ornith:9b"
LARGE = "gpt-oss:20b"

def _detect_models() -> None:
    """Detect installed Ollama models and update CHAT/SMALL/LARGE globals dynamically."""
    global CHAT, SMALL, LARGE
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
    for fam, attr in ((_CHAT_FAMILIES, "CHAT"), (_SMALL_FAMILIES, "SMALL"), (_LARGE_FAMILIES, "LARGE")):
        for m in fam:
            match = next((i for i in models if i.startswith(m.split(":")[0])), None)
            if match:
                globals()[attr] = match
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

# Small-talk / banter → fast chat model (qwen). Kept tight so real questions
# still go to the brain (ornith). No code, no "how do I…", just casual chatter.
_CHAT = [
    r'^(hi|hello|hey+|yo+|sup|hiya|howdy|hola|namaste|wass?up|what\'?s up)\b',
    r'^(thanks?|thank you|thx|ty|ok(ay)?|k|cool|nice|great|awesome|got it|sure|fine|alright|right)[!?. ]*$',
    r'^(lol|lmao|haha+|hehe|nice one|good one|wow|omg|bruh|yay|nvm|nevermind)\b',
    r'\b(how are (you|u|ya)|how\'?s it going|how you doing|you good|wyd|what\'?s new)\b',
    r'\b(good (morning|afternoon|evening|night)|gm|gn)\b',
    r'\b(who are (you|u)|what\'?s your name|your name|introduce yourself)\b',
    r'\b(tell me a joke|say something funny|bored|entertain me)\b',
    r'^(bye|goodbye|see ya|cya|later|good ?bye|take care)[!?. ]*$',
]
_CHAT_RE = [re.compile(p, re.IGNORECASE) for p in _CHAT]

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
    # Work/complex intent ALWAYS wins over casual words ("hey, build me an app").
    if any(p.search(msg) for p in _COMPLEX_RE):
        return "complex"
    # Small-talk → fast chat model. Short + casual only.
    if len(msg) <= 60 and "```" not in msg and any(p.search(msg) for p in _CHAT_RE):
        return "chat"
    if any(p.search(msg) for p in _SIMPLE_RE):
        return "simple"
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

    # Step 1: pick by tier. Ornith is the brain and handles ALL real work,
    # including code — it's the coding specialist. gpt-oss:20b (LARGE) is NOT
    # auto-picked; it's reserved for explicit Deep Think (force_large / model pin),
    # honoured in Step 3. Auto-routing only ever chooses qwen (chat) or ornith.
    if complexity == "chat":
        ideal = CHAT           # fast small-talk on qwen
    else:
        ideal = SMALL          # ornith brain: simple, code, complex — everything real

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
        model_rank = {CHAT: 0, SMALL: 1, LARGE: 2}
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
