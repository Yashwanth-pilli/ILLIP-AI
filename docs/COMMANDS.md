# ILLIP Commands Reference

Everything you can type — in the terminal and in the chat. Keep this handy.

---

## 🖥️ Terminal commands

Type these in **any** terminal window (cmd / PowerShell). They work from any folder.

| Command | What it does | When to use it |
|---|---|---|
| `illip` | Starts the server (if not running) and opens the web app in your browser | Normal daily use |
| `illip repair` | **Emergency fix.** Kills a stuck server, restarts Ollama, smoke-tests the code, offers git rollback to the last CI-tested version if code is broken, reinstalls missing dependencies, restarts everything | ILLIP is frozen, won't start, or broke after a change. Works even when the app itself is dead |
| `illip code` | Opens a terminal coding agent in a **new window**, working in your current folder (like a local coding agent) | Serious coding/build work in a specific project folder |
| `illip code --continue` | Same, but resumes your last terminal conversation | Continue yesterday's coding session |
| `illip do "make X"` | Agent crew builds task X **in the current folder** — plans, writes files, verifies | Quick one-shot build where you are |
| `illip build "make X" --dir <folder>` | Same, but in a specific folder | Build somewhere else |
| `illip start` | Starts just the server in this window (options: `--host`, `--port`, `--reload`) | Development / server-only use |
| `illip status` | Shows whether the server and Ollama are up | Quick check |
| `illip version` | Shows the ILLIP version | — |

### The repair ladder (memorize this order)

1. Reply slow? → look at the **header badge**. `🟡 RAM 94% · close apps` = your PC is full, close browser tabs/apps
2. Something off but app opens? → type **`/doctor`** in chat (15 checks, names problems + fixes)
3. Ollama/model problem? → type **`/heal`** in chat (auto-fixes while app runs)
4. **App frozen or won't open?** → open a terminal → **`illip repair`**
5. Still broken? → the repair output shows the exact error — paste it to your assistant

---

## 💬 Chat slash commands

Type `/` in the chat box — a menu pops up (↑↓ to pick, Enter to accept, Esc to close).

### Agents & building
| Command | What it does |
|---|---|
| `/task <goal>` | Run a goal through the agent crew — planner splits it, specialists execute, files land in the workspace, live progress shown |
| `/loop <goal>` | Same, but loops: a QA reviewer judges the result and the crew retries (max 5×) until it passes |

### Ideas & guidance
| Command | What it does |
|---|---|
| `/idea <your idea>` | Analyzes any idea (any field): explains it, searches similar existing work, builds a 5–7 step plan into your Tasks, names skill gaps + budget tips, and timestamps the idea in your vault (proof you had it first) |
| `/stuck` | Looks at your tasks, workspace and vaulted ideas → tells you the ONE next step |
| `/opps` | Finds live opportunities (grants, contests, communities…) for your field |

### Safety
| Command | What it does |
|---|---|
| `/scan [path]` | Scans a downloaded file for malware signs (double extensions, disguised types, zip contents, Windows Defender). No path = newest download |
| `/getsafe <name>` | BEFORE downloading something: reputation check + safe-download steps |

### Modes & tools
| Command | What it does |
|---|---|
| `/caveman [off]` | Terse replies — faster on local hardware |
| `/ponytail [off]` | Simplest-solution mode — flags over-engineering |
| `/gstack [path]` | Read-only git report: branch, status, staged changes + a suggested commit message |
| `/ask <question>` | Perplexity-style live answer: keyless web search → reads the top pages → cited synthesis with source links. Inline in chat (the 🔬 Research panel does the same with streaming steps). No API key. |
| `/read <url>` | Keyless smart-read of any link: YouTube→transcript, GitHub→readme/file, Reddit→thread (often blocked), else clean article text. No API key. |
| `/skills [category]` | Browse the curated agent-skills directory (from awesome-agent-skills). Filter by category e.g. `/skills security`. Discovery only — links out. |
| `/sharpen <question>` | Answers, then the same brain self-critiques and refines the answer (draft→critique→refine). Brain-agnostic; shows whether the loop improved it. Benchmark: `python scripts/sharpen_bench.py` |

### Reminders
| Command | What it does |
|---|---|
| `/remind HH:MM <text>` | Daily reminder at that time |
| `/reminders` | List reminders |
| `/unremind <id>` | Delete one |

### Health & help
| Command | What it does |
|---|---|
| `/doctor` | Full diagnostics in an overlay — Ollama, models, GPU temp, RAM, disk, deps, battery |
| `/heal` (or `/repair`) | Auto-fix Ollama/model problems from inside the app |
| `/guide` (or `/help`, `/illip`) | Instant feature tour |
| `/game` | Open the arcade (fun while agents work) |

---

## 🖱️ Buttons worth knowing

| Where | Button | Does |
|---|---|---|
| Header | model dropdown | Pin a specific model (or 🤖 Auto) |
| Header | `↺ Refresh` | **Clears the conversation context** (not your saved history) |
| Header | 🗿 / 🐴 chips | Toggle caveman / ponytail modes |
| Header | badge (`🟢 46°C · Safe`) | Live safety — hover for details. Yellow RAM warning = close apps |
| Nav rail | 🧠 Models | Installed models (click to switch, 🗑️ to delete) + **Get Models store** (download sized-for-your-PC models) |
| Nav rail | 💬 Chats | All previous chats — nothing is ever lost, switch any time |
| Chat bar | ⚡ Force Large | Route this message to the big model (deep think) |
| Chat bar | 📎 | Upload anything — zips auto-extract, audio auto-transcribes, images go to the vision model |
| Message hover | ✏️ / 🗑️ / 🔁 | Edit-and-resend / delete / regenerate |

---

## 🌐 Connect other apps to ILLIP

ILLIP speaks the OpenAI API. In Cursor / Continue.dev / any OpenAI-compatible tool:

- **Base URL:** `http://localhost:8000/v1`
- **Model:** `illip`
- **API key:** `illip` (anything non-empty; real keys only if `ILLIP_API_KEYS` is set in `.env`)

---

*All configuration lives in `.env` (copy `.env.example`). The model catalog is editable at `data/model_catalog.json`. Nothing is hardcoded.*
