# Updating & Maintaining ILLIP — No AI Assistant Needed

Everything here works with just a terminal and the tools ILLIP already ships.

---

## 1. Getting updates (easiest → most manual)

### A. From inside ILLIP (safest)
The built-in updater snapshots the current version, pulls the new code,
smoke-tests it, and **rolls back automatically if the new version is broken**.

- Check: open `http://localhost:8000/docs` → `GET /api/system/update/check`
- Apply: `POST /api/system/update` (add `?restart=true` to restart after)

### B. From the terminal
```bat
cd E:\Projects\ILLIP_AI
git pull
.venv\Scripts\pip install -r requirements.txt
illip repair        :: restarts everything cleanly; rolls back if broken
```
Only needed extra step: if files under `frontend/src/` changed AND you want to
rebuild the UI yourself (normally `frontend/dist/` is already committed):
```bat
cd frontend && npm install && npm run build
```

### C. If an update breaks everything
```bat
illip repair
```
Say **y** when it offers "reset to origin/main". That restores the last
version that passed the automated tests. You cannot lose your chats/memory —
they live in `data/`, which updates never touch.

---

## 2. Changing things yourself (no code knowledge needed)

| What you want | Where | How |
|---|---|---|
| Settings (port, model, API keys, integrations) | `.env` | Edit with Notepad, restart ILLIP. Every option is listed with comments in `.env.example` |
| Which models the store offers | `data/model_catalog.json` | Copy the shape from `app/services/model_catalog.py` `DEFAULT_CATALOG`, adjust names/sizes. Your file fully replaces the built-in list |
| ILLIP's personality | chat: clear memory in the 🧿 Memory panel, then talk to it how you want it to be | Old chats teach it — clearing resets the persona |
| Default AI model | header dropdown, or `OLLAMA_MODEL=` in `.env` | — |
| How ILLIP thinks (work method) | `data/methodology.md` | Your text replaces the built-in Fable-style method (understand → root cause → simplest fix → verify). Empty file disables it |

---

## 3. Changing the code yourself (small edits)

The map — where things live:

```
app/
  api/routes/     each URL endpoint (chat.py, system.py, ...)
  services/       the actual logic (chat_service.py, doctor.py, ...)
  skills/builtin/ what agents can do (shell, files, search, ...)
  providers/      how ILLIP talks to Ollama / cloud models
  config.py       every setting, all read from .env
frontend/src/     the web UI (React) — components/panels/*.jsx
tests/            the safety net
docs/COMMANDS.md  every command explained
```

The safe edit loop (do this every time):

```bat
cd E:\Projects\ILLIP_AI
git add -A && git commit -m "before my change"   :: snapshot FIRST
:: ... edit files ...
.venv\Scripts\python -m pytest -q               :: all tests must pass
illip repair                                     :: clean restart, try it
git add -A && git commit -m "what I changed"    :: keep it
git push                                         :: GitHub runs tests again (CI)
```

Golden rules:
1. **Commit before experimenting.** A commit is a save point — `illip repair`
   can always take you back to one.
2. **`python -m pytest -q` after every change.** Green = safe. Red = the test
   name tells you what broke.
3. **Push only when green.** GitHub CI re-tests every push; `illip repair`
   treats the last pushed version as "known good", so never push red.
4. **Never edit inside `frontend/dist/`** — it's generated. Edit
   `frontend/src/` and run `npm run build`.
5. **`data/` is yours** (chats, memory, models config). Code updates never
   touch it, and it's never uploaded to GitHub.

---

## 4. Adding a new model you found (example: from Ollama library)

1. Find it on https://ollama.com/library — note the tag (e.g. `hermes3:8b`)
   and download size
2. Add an entry to `data/model_catalog.json` (or just run
   `ollama pull hermes3:8b` in a terminal)
3. It appears in the 🧠 Models panel — click to switch

---

## 5. When you're truly stuck

1. `illip repair` — fixes 90% of "it won't work"
2. `/doctor` in chat — names the exact problem
3. The error text + `git log --oneline -5` output is everything a helper
   (human or AI) needs to fix it fast
