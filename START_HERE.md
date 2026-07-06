# Start Here

This guide gets ILLIP AI running and shows where to look first.

## What You Have

ILLIP AI is a local-first AI assistant platform:

- A FastAPI backend in `app/`
- A React (Vite) frontend in `frontend/src/`, built to `frontend/dist/` and served by the backend
- 27 agents, Ghost Engine hardware-aware model routing, memory, skills, plugins, scheduler, governance
- Local task, memory, chat, and log storage
- Tests and docs for the main flows

No cloud account is required for the default mock provider.

## First Run (easiest — no terminal needed)

Double-click **`setup.bat`** in the project root. It will:

1. Find or install Python (asks your permission first)
2. Install all dependencies
3. Find or install Ollama, look at your hardware, and download the right AI model (asks first — it's a few GB)
4. Put a small cat 🐱 on your desktop and screen

**Click the cat to start ILLIP.** Drag it anywhere; right-click it to quit.
If setup can't do something automatically, it explains exactly what to do, step by step.

## First Run (manual, for developers)

Open PowerShell in the project root:

```powershell
.\setup.ps1
```

The frontend is pre-built in `frontend/dist/`. To rebuild after changing `frontend/src/`:

```powershell
cd frontend; npm install; npm run build; cd ..
```

Start the backend — it serves the built frontend automatically:

```powershell
.\scripts\run_backend.ps1
```

Open the app:

```text
http://127.0.0.1:8000/
```

## Useful Local URLs

| URL | What it shows |
| --- | --- |
| `http://127.0.0.1:8000/` | The app (React UI) |
| `http://127.0.0.1:8000/docs` | Interactive API docs |
| `http://127.0.0.1:8000/redoc` | Alternate API docs |
| `http://127.0.0.1:8000/api/health` | Backend health check |

## Try These First

1. Send a chat message in the browser UI.
2. Open `http://127.0.0.1:8000/docs`.
3. Run `GET /api/agents/` from the API docs.
4. Run the test suite:

```powershell
pytest -v
```

## How The Pieces Connect

1. `frontend/dist/index.html` (built from `frontend/src/`) loads the React app.
2. `frontend/src/api.js` calls the backend API with `fetch()`.
3. FastAPI receives requests under `/api`.
4. Route modules in `app/api/routes/` call services in `app/services/`.
5. Services use agents, providers, SQLite, or JSON files as needed.
6. The backend returns JSON and React renders it.

Read [docs/integration_flow.md](docs/integration_flow.md) for the full request map.

## Files To Read First

- `frontend/src/App.jsx`: root component, state, and wiring
- `frontend/src/api.js`: browser-to-backend calls
- `app/main.py`: FastAPI application setup
- `app/api/__init__.py`: route registration
- `app/api/routes/chat.py`: chat endpoint example
- `app/services/model_service.py`: model and agent service entry points
- `app/agents/__init__.py`: agent registry
- `tests/test_chat.py`: simple API test pattern

## Safety Notes

- The default `mock` provider is safe for local learning and does not call an external model.
- Keep API route changes synchronized with `frontend/src/api.js` and the docs.
- The self-building workflow should stay behind review, tests, and approval gates.
- Do not store secrets in committed files. Use `.env` for local overrides.

## Common Issues

Backend will not start:

- Make sure setup completed successfully.
- Check whether port `8000` is already in use:

```powershell
netstat -ano | findstr :8000
```

Frontend cannot reach backend:

- Confirm the backend terminal is still running.
- Confirm `frontend/src/api.js` points to `http://127.0.0.1:8000/api` (it derives this from `window.location`, so it just works when served by the backend).
- If you edited `frontend/src/`, re-run `npm run build` inside `frontend/` — the backend serves the last build in `frontend/dist/`.
- Open browser dev tools with `F12` and check the Console tab.

Import errors:

- Re-run setup:

```powershell
.\scripts\setup.ps1
```

- Confirm Python can import the app from the project root:

```powershell
python -c "from app.main import app; print(app.title)"
```

## Development Commands

```powershell
.\scripts\dev_start.ps1       # Start backend and frontend helpers
.\scripts\run_backend.ps1     # Backend only
.\scripts\run_frontend.ps1    # Frontend only
pytest -v                     # Run tests
```

View recent logs:

```powershell
Get-Content .\data\logs\illip.log -Tail 50
```

## Next Reading

1. [docs/integration_flow.md](docs/integration_flow.md)
2. [docs/architecture.md](docs/architecture.md)
3. [AGENTS.md](AGENTS.md)
4. [docs/self_building_loop.md](docs/self_building_loop.md)
