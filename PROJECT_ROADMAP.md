# ILLIP AI — Project Roadmap

## Current Version: 3.1

---

## Phase 1: Foundation ✓ (Complete — v0.1.0)

- [x] FastAPI backend
- [x] HTML/CSS/JS chat interface
- [x] Agent framework (5 core agents)
- [x] SQLite memory
- [x] Task management
- [x] Mock LLM provider
- [x] Test suite (pytest)
- [x] Windows/Mac/Linux portability
- [x] Documentation scaffold

---

## Phase 2: Model Integration ✓ (Complete — v1.0)

- [x] Ollama integration (full)
- [x] Local model switching (MODEL_PROVIDER env)
- [x] Response streaming
- [x] OpenRouter cloud fallback
- [x] Groq cloud fallback
- [x] AirLLM (layer-streaming for large models on low VRAM)
- [x] llamafile provider (single-file model runner)
- [x] Model policy enforcement (DeepSeek blocked at factory level)
- [x] OpenAI-compatible API at /v1/* (Continue.dev, etc.)

---

## Phase 3: Enhanced Memory & Intelligence ✓ (Complete — v2.0)

- [x] Qdrant vector memory (local file storage)
- [x] SQLite FTS5 fallback when Ollama offline
- [x] Memory Ball — structured named memories (user/project/feedback/reference/fact)
- [x] LLM auto-extraction of memories from every chat turn
- [x] Knowledge Graph — entity-relationship graph, LLM triple extraction
- [x] Semantic search across all conversations
- [x] Long-term persistent memory across sessions
- [x] Self-update: check/pull/restart from GitHub

---

## Phase 4: Agents, Plugins, SDK ✓ (Complete — v3.0)

- [x] 27-agent registry (up from 5)
  - Core: Planner, Builder, Reviewer, Tester, Memory
  - Specialist: Research, Code, Writer, Analyst, Summarizer, Translator, Scheduler, QA, Data, Email
  - Expansion: CEO, Design, Content, SEO, CustomerSupport, Compliance, Finance, Travel, SkillBuilder, PluginReview, DigitalTwin, Integration
- [x] Publish/subscribe event bus (AgentMessage schema)
- [x] Retry/backoff on all agents (exponential: 1s, 2s)
- [x] Tool-call loop in base agent (up to 3 rounds per task)
- [x] Agent SDK — IllipAgent base class for third-party agents
- [x] Community plugin catalogue — 12 plugins, install-by-name
- [x] Skills system — install from URL/GitHub/PyPI, auto-registered as LLM tools
- [x] Skill Builder Agent — generates new ILLIP skills from task description
- [x] Plugin Review Agent — security-audits plugins before install

---

## Phase 4+: Extended Capabilities ✓ (Complete — v3.1)

- [x] Voice STT — local Whisper via faster-whisper (CPU + CUDA)
- [x] Voice TTS — Piper (local, offline) with gTTS fallback
- [x] Image generation — A1111, Diffusers, Together AI
- [x] Video generation — FramePack, CogVideoX, AnimateDiff, Replicate
- [x] Browser automation — Playwright, Shadow DOM, retry, task planning
- [x] Workspace intelligence — file listing, grep search, context extraction
- [x] LAN sync — subnet /24 scan, peer discovery, zip pull/merge
- [x] Zip export/import for offline data transfer
- [x] Git sync to private remote repo
- [x] Digital Twin — tracks preferences, workflows, productivity patterns
- [x] Governance — approval gates for high-risk actions
- [x] API key auth middleware (optional, off by default)
- [x] n8n workflow integration
- [x] Scheduler — recurring cron jobs
- [x] SearXNG private local search
- [x] Notion + Google Drive integration
- [x] Telegram bot (deferred — pending Oracle account)

---

## Phase 5: UI Completeness (In Progress)

- [ ] Workflows UI panel (visual workflow builder)
- [ ] Skills/Plugins dedicated UI panel (browse, install, manage)
- [ ] Governance controls UI panel (approve/reject pending actions)
- [ ] Mobile-friendly audit and responsive fixes
- [ ] Agent performance dashboard (task counts, latency, error rates)

---

## Phase 6: Revenue & Editions (Deferred — PDF §42)

- [ ] Free / Pro / Enterprise edition gating
- [ ] Stripe payment integration
- [ ] Usage metering
- [ ] Team multi-user support

Revenue structure intentionally deferred. Architecture already supports it (API key auth, governance, agent SDK provide the surface).

---

## Phase 7: Learning Loop (Planned)

- [ ] Fine-tune pipeline — collect approved exchanges as training data
- [ ] LoRA fine-tuning on local Llama
- [ ] Model quality metrics and regression detection
- [ ] Self-improvement benchmark tracking

---

## Deferred Items

| Item | Reason |
|---|---|
| Telegram bot | Waiting on Oracle Cloud account (ATM card needed for free tier) |
| Revenue/editions | Intentionally deferred per PDF §42 |
| Multi-user real-time collab | Out of scope (single-user, local-first) |
| Proprietary model support | Policy: open weights only |

---

**Version:** 3.1 | **Last Updated:** 2026-06-29 | **Status:** Phase 4+ complete, Phase 5 UI in progress
