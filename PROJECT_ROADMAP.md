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

## Phase 5: UI Completeness ✓ (Complete — v3.1)

- [x] Workflows UI panel — scheduler jobs list, run/pause, + New modal with interval presets
- [x] Skills/Plugins dedicated UI panel (browse, install, manage)
- [x] Governance controls UI panel (approve/reject pending actions)
- [x] Mobile-friendly audit and responsive fixes (640px breakpoint, button grid)
- [x] Agent performance dashboard (task_count, last_activity, perf bar per agent)
- [x] PyPI packaging — `pip install illip-ai` → `illip start` CLI
- [x] Docker + docker-compose one-command deploy
- [x] All env vars configurable — nothing hardcoded
- [x] No model restrictions — DeepSeek, vLLM, LM Studio, any OpenAI-compat endpoint
- [x] Anthropic native SDK provider (Claude Sonnet, Opus, etc.)
- [x] 121 tests, 121 passing

---

## Phase 5.1: Chat UX Parity (Complete — 2026-07-04)

- [x] Chat history restored on load + project switch (no more blank/wiped chat)
- [x] Stop-generation button (AbortController on stream)
- [x] Code blocks: language header + copy button
- [x] Regenerate last response button
- [x] Frontend build clean (59 modules), 121 backend tests passing

---

## Phase 5.2: Doctor + Editor Integration (Complete — 2026-07-04)

- [x] `/doctor` diagnostics — `app/services/doctor.py`, `GET /api/system/doctor`,
      `/doctor` chat command. Checks Ollama, models, active-model Ghost feasibility,
      GPU temp/pressure, RAM, disk, data-dir writable, required+optional deps,
      **battery/AC (laptop safety warning)**.
- [x] Fixed `/v1/chat/completions` — was 500 on every call (missing `await get_provider()`
      + `Message` timestamp). Now works with Cursor / Continue.dev / any OpenAI-compatible
      editor. Point the editor at `http://localhost:8000/v1`, model `illip`, apiKey `illip`.
- [x] 125 backend tests passing (added doctor + v1 regression tests).

**Ghost Engine review:** already production-grade — real Ollama `/api/show` architecture
reads, GQA-aware KV cache sizing, 4 load strategies (full_gpu/kv_offload/hybrid/cpu_only),
Windows shared-VRAM headroom, temp hard-limit (85°C → CPU), VRAM/RAM safety buffers,
5s background safety monitor with pressure throttling. No hardware can damage the laptop:
it refuses to raise load when hot and auto-drops context under pressure.

---

## Phase 5.3: Artifacts + Hardware-Adaptive Default (Complete — 2026-07-04)

- [x] Artifacts pane — live HTML/SVG preview in a sandboxed iframe (`ArtifactPane.jsx`).
      `▶ Preview` button appears on html/svg/xml code blocks; Code/Preview toggle,
      open-in-new-tab. Sandbox: `allow-scripts` only, no same-origin (can't touch ILLIP).
      JSX/React artifacts skipped (needs in-browser Babel) — add when requested.
- [x] Default model → `qwen2.5:7b` (fits this RTX 4060: full_gpu, 28/28 layers, 5.6GB).
- [x] **Startup auto-select** (`app/main.py`) — if the configured model isn't installed
      or won't fit the hardware, ILLIP auto-switches to the best model the GPU/RAM can
      run. Makes it work on ANY laptop with zero config; weak machines auto-downgrade.
- [x] 125 tests passing.

---

## Phase 5.4: Self-Healing Doctor + Live Safety Badge (Complete — 2026-07-04)

- [x] **Self-healing doctor** (`app/services/self_heal.py`) — background loop every 60s +
      `POST /api/system/doctor/heal`. Auto-repairs, safe actions only:
      Ollama down → `ollama serve`; active model missing/unfit → switch to a fitting model;
      records last 20 actions. Started in `main.py` lifespan.
- [x] `/doctor` report now shows recent auto-repairs + "self-healing is active".
- [x] **Live safety badge** in header — 🟢 42°C · Safe, colour by pressure, hover shows
      "limit 85°C, auto-throttles". Fed by existing 5s `hwLive` poll. Hidden on mobile.
- [x] **Fixed blank-screen crash**: `marked` v12 `renderer.code` takes positional args
      `(code, infostring)`, not `{text,lang}` — old code threw on every code block and
      blanked the UI. Fixed + added `ErrorBoundary.jsx` so no render crash blanks the app.
- [x] Live thermal proof: 7b generation at 96% GPU = 51°C peak (limit 85°C). Safe.

---

## Phase 5.5: Toasts, Arcade, Polish, Persistence Fix (Complete — 2026-07-04)

- [x] **Data-loss fix (important):** `_write_json` in `project_service.py` was non-atomic —
      an interrupted/overlapping write (client disconnect mid-stream, server kill) left
      history.json truncated, then reads fell back to empty = lost chat. Now atomic
      (temp file + `os.replace` + fsync) with a process-wide write lock around
      read-modify-write in `history_append` / `memory_store`. Verified: 8 messages
      survive repeated server restarts.
- [x] **Auto-fixed toasts:** self-heal actions surface in the 5s `hwLive` poll
      (`heal_actions`); `Toasts.jsx` shows a heads-up when ILLIP repairs itself.
- [x] **`/game` arcade:** `GamesModal.jsx` + `games.js` — Neon Snake + 2048, self-contained,
      run in a sandboxed iframe. `/game` command + 🎮 Games button. Users can also ask the AI
      to build a game and hit ▶ Preview (same artifact iframe).
- [x] **UI polish:** aurora glow bg, message fade-in, brand neon breathe, safety-badge pulse,
      toast/arcade styling.
- [x] `ErrorBoundary.jsx` (from 5.4) means a UI crash shows a Reload button, never a blank screen.

**On GPU/CPU "equal split":** deliberately NOT forced. The GPU is far faster; the 7b model
fits it fully at ~51°C (measured), so all-GPU is both fastest and coolest. Ghost Engine
already splits to CPU only when a model won't fit VRAM (hybrid), and the 85°C governor
prevents strain on either. Forcing 50/50 would slow responses and heat the CPU.

---

## Phase 5.6: Arcade v2 + Chat Cleanup (Complete — 2026-07-04)

- [x] Rewrote games (`games.js`): Neon Snake (levels, rising speed, wall-wrap, swipe),
      2048 (win/lose detection, swipe), NEW Tic-Tac-Toe (3 difficulties, Hard = minimax
      unbeatable). All inline-JS syntax-verified.
- [x] **"Create your own game"** card in the arcade — user describes a game, ILLIP builds
      it via the local model and plays it in the sandboxed frame. Routes through the
      non-persisting `/v1` endpoint so it never clutters chat history.
- [x] Cleared test-message pollution from default project history (dev artifacts).
- [x] Visible UI upgrade: assistant replies now render as cards with a cyan accent
      (clearer, cleaner) alongside the existing aurora/glow polish.
- [x] 128 backend tests unchanged (this round was frontend-only).

---

## Phase 5.7: Personality, Rebrand, Model Tuning (Complete — 2026-07-04)

- [x] Rebrand: "ILLIP AI" → **ILLIP** everywhere (header, title, welcome, placeholder, system prompt).
- [x] Rewrote system prompt: funny/quirky/unfiltered personality, hard rule to never say
      "AI assistant", banned corporate voice. Fixed false "powered by Anthropic Claude" line.
- [x] **Root-caused the boring persona:** vector memory had 89 old chat turns ("I am an AI…",
      "How can I assist you today?") that were retrieved and fed back, training ILLIP to stay
      boring. Cleared FTS + Qdrant chat-memory (test junk). Persona now lands:
      "I'm ILLIP, your witty sidekick 😎".
- [x] Model tuning: router SMALL/LARGE = qwen2.5:7b (3b too weak for persona — deleted;
      14b too big for 8GB VRAM: ctx drops to 512, garbled — pulled but kept OFF auto-path).
      7b is the reliable sweet spot: full-GPU, fast, holds personality.
- [x] Funny rotating "working" status ("Firing up the neurons…", "Sipping imaginary coffee…").
- [x] Games: Tic-Tac-Toe now always plays perfect (minimax, no difficulty), stronger
      create-your-own game prompt for complex games.

### Honest status on the big remaining asks (need dedicated turns)
- **Agents actually executing with live thinking:** agents exist + run individually via
  `/agents/{type}/execute`, but chat does NOT orchestrate the Planner→Builder→… pipeline
  with streamed steps. Real build. Biggest-value next task.
- **Terminal (like Claude Code):** `code_executor` skill exists; a full terminal panel that
  runs shell commands is doable but needs a safety/confirm layer. Medium build.
- **Fully uncensored:** personality is now unfiltered/non-preachy (prompt-level). Genuine
  hard-harm refusals stay. A truly uncensored *model* would mean swapping to an abliterated
  local model — user's call.
- **Connect all platforms:** connectors exist (Discord/Slack/Telegram/WhatsApp/Notion/GDrive/
  n8n/email) but most need tokens + wiring per platform.
- **Better 3D/website generation:** limited by 7b quality on 8GB. Bigger model = 14b, which
  doesn't fit well here. This is a hardware ceiling, not a bug.

---

## Phase 5.8: MoE Big-Model Support + Speed Tuning (Complete — 2026-07-04)

- [x] Pulled **gpt-oss:20b** (MoE, ~3.6B active/token). Measured on RTX 4060 8GB:
      Ghost hybrid 15/24 layers, **23 tok/s** — a genuine 20B running well on 8GB.
      Deleted 14b (dense, didn't fit) + qwen2.5:3b.
- [x] DeepSeek allowed (no code block existed; policy note updated).
- [x] **Model strategy settled after measurement:** everyday = qwen2.5:7b (warm TTFT ~3s,
      35-42 tok/s, holds persona). MoE = on-demand "Deep Think" (header model pick /
      force_large). Single-MoE-for-everything was tested and REJECTED: on 8GB the complex
      pipeline gives 11-50s TTFT — too slow for routine chat. 7b-default + 20b-on-demand
      is the right UX.
- [x] Startup now background-pre-warms the heavy model **only if** it differs from the
      everyday model (skipped now that both are 7b) — avoids memory thrash on 8GB.
- [x] no-cache on index.html (prior fix) means users actually receive these updates.

### MoE reality (answer to "only load the needed part")
Sparse activation ALREADY does this at compute time — ~3.6B of 20B fire per token, which
is why it's 23 tok/s not ~5. All experts must stay in MEMORY (can't predict the next
expert), so the one-time load is unavoidable; keep_alive (1h) makes it load once. True
per-token expert offloading (llama.cpp --n-cpu-moe / ktransformers) is bleeding-edge and
not yet exposed by Ollama — a future upgrade.

---

## Phase 5.9: Agent Company with Live Thinking (Complete — 2026-07-04)

- [x] **Agent orchestration** (`app/services/agent_orchestrator.py`): Planner breaks a goal
      into 2-4 steps, assigns each to the best-fit agent, runs them sequentially threading
      results forward. Robust plan parser (JSON → numbered-lines → single-step fallback).
- [x] **Live SSE stream** `GET /api/agents/run/stream?task=` — emits step_start / plan /
      step_done / final / end. Verified end-to-end: "write a haiku and check it" →
      Writer → Reviewer, streamed live; produced real combined output.
- [x] **UI** (`AgentsRunPanel.jsx`): live panel showing each agent 🧠→⚙️working→✅done with
      the plan chips and final result. Trigger: `/task <goal>` command or the 🏢 Team button
      (runs your typed message through the crew).
- [x] Tests: parser + SSE endpoint (4 new). Full suite green.

This is the feature that makes ILLIP feel like an actual AI *company*, not one chatbot.

### Agents produce REAL files (2026-07-04)
- Code blocks in agent output are extracted and written to a per-run workspace
  `data/agent_runs/<run_id>/`, served at `/data/agent_runs/...` (view + download).
- Filename from info string (```python:app.py), a hint before the block, or a
  language default. Cross-step + same-batch de-dup (index.html → index_2.html) so
  nothing is silently overwritten. Trivial snippets (<15 chars) skipped.
- Code/builder/design/tester steps are nudged to emit complete, named files.
- UI: "📁 Files created" section in the agent panel with view/download links.
- Verified: `/task build a stopwatch` wrote real, downloadable index.html.

---

## Phase 5.10: Real Terminal (Complete — 2026-07-04)

- [x] `app/api/routes/terminal.py` — POST /run, GET /status. Runs real shell commands
      via `asyncio.create_subprocess_shell` with a 60s hard timeout.
- [x] **Safety**: scoped to `data/terminal/` workspace (cd cannot escape above it);
      destructive patterns (rm -rf /, mkfs, dd, shutdown, format, sudo, git push --force…)
      BLOCKED unless `confirm=true`; the UI shows a warning + confirm buttons first.
- [x] Persistent cwd across calls (built-in `cd` handled server-side), output capped
      (20k stdout / 8k stderr), `clear`/`cls` client-side.
- [x] **UI** (`TerminalPanel.jsx`): dark terminal with command history (↑/↓), colored
      stdout/stderr/warnings, live cwd, confirm dialog. Trigger: `/terminal` or ▶ Terminal button.
- [x] Verified: echo, cd-persistence (`python calc.py` → 42 from a subdir), danger-block,
      cd-escape-block, confirm-bypass all correct.

---

## Phase 5.11: ILLIP Uses the Terminal + Clean UI (Complete — 2026-07-04)

- [x] Extracted shell core into `app/services/shell_service.py` (workspace sandbox,
      danger filter, 60s timeout, persistent cwd). Both the /terminal API and agents
      route through it, so safety rules can't drift.
- [x] **`run_shell` skill** (`app/skills/builtin/shell_skill.py`) registered — agents can
      now run python/pytest/npm/git/ls etc. in their tool loop. Agents call WITHOUT
      confirm, so destructive commands are REFUSED (verified: `rm -rf /` → REFUSED,
      `python -c print(2**10)` → 1024). Tester/builder steps nudged to actually run+verify.
- [x] **Clean UI pass** — retuned palette from neon-cyberpunk to calm modern dark
      (soft charcoal, muted teal accent, hairline borders). Killed moving grid + scanlines
      + neon flicker/glows. Flat solid buttons, clean focus rings, roomier chat line-height,
      centered 820px reading column (Perplexity/ChatGPT-style), thin scrollbars.

---

## Phase 5.12: Agent File Output Cleanup + Zip Download (Complete — 2026-07-05)

- [x] **Killed junk dupes**: content-hash dedup across all steps (identical code written
      once), command-snippet skip (single-line `python app.py` / bash blocks no longer
      saved as run.sh/file.txt clutter). Junk went from ~10 files → ~2 per run.
- [x] **Disk sweep**: final manifest also picks up files agents made via run_shell
      (echo > file), so the panel/zip reflect everything on disk, not just fenced blocks.
- [x] **Download-as-zip**: `GET /api/agents/run/{run_id}/zip` (path-traversal guarded,
      404 on escape) → one .zip of the whole run. "⬇ Download all (.zip)" button in panel.
- [x] Verified: zip contains real files, dedup E2E clean, traversal blocked.

### Model landscape note (2026-06 releases, verified via web)
- **Ornith-1.0** (DeepReinforce, MIT) — agentic-coding model family, self-scaffolding,
  OpenAI-compatible + tool calling. **9B Dense fits 8GB** and is purpose-built for ILLIP's
  job (terminal/repo coding). Not on Ollama library yet → HF GGUF. CANDIDATE to pull.
- **GLM-5.2** (Z.ai/Zhipu, MIT) — 744B total / 40B active MoE, 1M ctx, top open model.
  **Too big for 8GB** (~400GB). Cloud-only (OpenRouter). Optional cloud fallback if the
  no-cloud stance ever relaxes.

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

**Version:** 3.1 | **Last Updated:** 2026-06-29 | **Status:** Phases 1–5 complete. Phase 6 (revenue) deferred. Phase 7 (learning loop) next.
