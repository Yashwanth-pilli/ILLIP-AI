# ILLIP AI — v3.1

**Your AI company, in your device.**

ILLIP AI is a portable, private, self-improving AI system that runs on your own hardware. It is not a chatbot. It is a full AI platform with agents, memory, knowledge graph, media generation, browser automation, workspace intelligence, and local model support — all offline-first, all under your control.

---

## Quick Start

**Easiest:** download the zip, extract it, and **double-click `setup.bat`**. It finds or installs Python and Ollama (asking your permission first), installs everything, picks the right AI model for your hardware, and puts a small cat 🐱 on your desktop. Click the cat — ILLIP starts and opens in your browser. Anything it can't do automatically, it explains step by step.

**Manual (developers):**

```powershell
# Install and set up
.\setup.ps1

# Start the app — serves the UI and API from one port
.\scripts\run_backend.ps1
```

| URL | What |
|---|---|
| `http://127.0.0.1:8000/` | The app (React UI) |
| `http://127.0.0.1:8000/docs` | Interactive API docs |
| `http://127.0.0.1:8000/api/health` | Health check |

Editing the frontend? Run `.\scripts\run_frontend.ps1` for a hot-reload Vite dev server on `:3000` (proxies to the backend on `:8000`).

---

## What ILLIP AI Can Do

### 27 Agents
Planner, Builder, Reviewer, Tester, Memory, Research, Code, Writer, Analyst, Summarizer, Translator, Scheduler, QA, Data, Email, CEO, Design, Content, SEO, CustomerSupport, Compliance, Finance, Travel, SkillBuilder, PluginReview, DigitalTwin, Integration.

Route any task to the right agent. Agents retry automatically on failure (exponential backoff).

### Memory System
- **Qdrant vector memory** — semantic search across all conversations. Falls back to SQLite FTS5 when Ollama is offline.
- **Memory Ball** — structured named memories (user, project, feedback, reference, fact). Auto-extracted from every conversation turn via LLM.
- **Knowledge Graph** — entity-relationship graph built automatically from conversations. Links people, projects, tools, concepts.

### Local Model Support
| Provider | How to use |
|---|---|
| Ollama | `ollama serve` — auto-detected |
| llamafile | Single executable, no install. Set `MODEL_PROVIDER=llamafile` |
| AirLLM | Layer-streaming for large models on low VRAM. Set `AIRLLM_MODEL=...` |
| OpenRouter | Set `OPENROUTER_API_KEY` |
| Groq | Set `GROQ_API_KEY` |
| Mock | Default — works with no setup |

**Model policy:** DeepSeek is blocked. Allowed families: Llama, Mistral, Phi, Gemma, Granite, Nemotron, Qwen.

### Media Generation
- **Image** — Stable Diffusion (A1111, Diffusers), Together AI. Local or cloud.
- **Video** — FramePack, CogVideoX, AnimateDiff, Replicate.

### Voice
- **Speech-to-text** — local Whisper (`pip install faster-whisper`). Runs on CPU or CUDA.
- **Text-to-speech** — Piper (local, offline) with gTTS fallback.
- Use the 🎤 mic button in the UI to speak instead of type.

### Browser Automation
Full Playwright-based browser agent. Shadow DOM support, task planning, retry logic. Chromium auto-installs on first use.

### Workspace Intelligence
- List all files in any directory
- Grep-style search across workspace
- Read files and extract relevant context for chat
- Named workspaces with stats and language breakdown

### Plugin Marketplace
- 12 community plugins ready to install: weather, exchange rates, IP geolocation, GitHub, Hacker News, Wikipedia, Open Library, country info, jokes, n8n webhooks, OpenRouter chat
- Browse: `GET /api/plugins/catalogue`
- Install: `POST /api/plugins/install/{name}`
- Add custom connectors via JSON spec

### Skills
- Install skill modules from GitHub URL, raw Python URL, or PyPI
- Skills register as LLM tools — agents call them automatically
- Built-in: `calculator`, `get_datetime`, `web_search`, `read_file`, `run_python`, `read_pdf`

### Agent SDK
Build your own agents:

```python
from app.agents.sdk import IllipAgent, register_agent

class MyAgent(IllipAgent):
    name = "my_agent"
    description = "Does cool things"

    async def process(self, task: str, context: dict = {}) -> str:
        return f"Done: {task}"

register_agent(MyAgent())
```

Registered agents appear in `GET /api/agents/sdk/list` and can be triggered via the event bus.

### Multi-Device Sync
- **Zip** — export/import `data/` as a zip file
- **Git** — push `data/` to a private git remote (`SYNC_GIT_REMOTE` in `.env`)
- **LAN** — discover other ILLIP instances on your local network and pull their data

```
GET  /api/sync/lan/info        — announce this instance
POST /api/sync/lan/scan        — find peers on subnet
POST /api/sync/lan/pull/{ip}   — pull + merge from peer
```

### Self-Update
```
POST /api/system/update/check    — compare local vs remote HEAD
POST /api/system/update/pull     — git pull origin main
POST /api/system/update/restart  — restart process in-place
```

### Automation
- **n8n** — workflow integration (set `N8N_URL` in `.env`)
- **Scheduler** — recurring jobs via cron expressions
- **Webhooks** — incoming webhook endpoints
- **SearXNG** — private local search (run `docker run -d -p 8888:8080 searxng/searxng`, set `SEARXNG_URL`)

### Governance
Approval gates for high-risk actions. Permission control, agent approval, security policy enforcement. `GET /api/governance/pending` to see pending approvals.

### Digital Twin
Tracks user preferences, workflows, tool usage, and productivity patterns over time. User-controlled, editable, removable.

### API Authentication
Optional. Set `ILLIP_API_KEYS=key1,key2` in `.env`. Unset = local single-user mode (no auth required).

---

## Configuration (`.env`)

```env
MODEL_PROVIDER=auto          # auto | ollama | llamafile | airllm | openrouter | groq | mock
OLLAMA_MODEL=llama3.2:3b
OLLAMA_BASE_URL=http://localhost:11434

OPENROUTER_API_KEY=          # optional cloud fallback
GROQ_API_KEY=                # optional cloud fallback

LLAMAFILE_URL=http://localhost:8080
AIRLLM_MODEL=                # e.g. meta-llama/Llama-2-7b-hf

SEARXNG_URL=http://localhost:8888
N8N_URL=http://localhost:5678
SYNC_GIT_REMOTE=             # private git repo for data sync

ILLIP_API_KEYS=              # leave empty for local single-user mode
WHISPER_MODEL=base           # tiny | base | small | medium | large
```

---

## Project Structure

```
app/
  agents/       27 agents + base class + SDK + event bus
  api/routes/   30+ FastAPI route modules
  providers/    Ollama, llamafile, AirLLM, OpenRouter, Groq, Mock
  services/     Memory (Qdrant+FTS5), Memory Ball, Knowledge Graph,
                Image gen, Video gen, Voice, Browser, Search, Workspace,
                Self-update, Digital twin, Scheduler, Telegram, Notion, GDrive
  skills/       Skill registry and installer
  plugins/      Plugin registry
  prompts/      System prompt and agent prompts
  twin/         Digital twin tracker and model
  hardware/     Hardware detection and context manager
frontend/       index.html + app.js + styles.css (no framework)
data/           Runtime data (memory, tasks, logs, images, videos)
tests/          Pytest suite
scripts/        PowerShell setup and run helpers
```

---

## Running Tests

```powershell
pytest -v
pytest tests/test_chat.py -v
pytest tests/test_agents.py -v
```

---

## Troubleshooting

**Backend won't start:**
```powershell
netstat -ano | findstr :8000   # check port conflict
.\scripts\setup.ps1            # reinstall deps
```

**No model responses:**
- Check `http://127.0.0.1:8000/api/health` — shows active provider
- Run `ollama serve` for local GPU mode
- Set `MODEL_PROVIDER=mock` to test without a model

**Voice STT not working:**
```powershell
pip install faster-whisper
```

**Browser agent fails:**
```powershell
playwright install chromium
```

---

## Docs

- [START_HERE.md](START_HERE.md) — first run guide
- [AGENTS.md](AGENTS.md) — agent system details
- [docs/architecture.md](docs/architecture.md) — system design
- [docs/integration_flow.md](docs/integration_flow.md) — request flow
- [PROJECT_ROADMAP.md](PROJECT_ROADMAP.md) — build phases

---

**Version:** 3.1 | **Status:** Phase 3+ complete | **Default provider:** auto (Ollama → llamafile → OpenRouter → Groq → Mock)
