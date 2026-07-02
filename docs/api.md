# API Reference

## Overview

ILLIP AI exposes a REST API for chat, tasks, memory, agents, health, and system status.

Base URL:

```text
http://127.0.0.1:8000/api
```

Interactive docs:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Frontend Integration

The React UI in `frontend/src/api.js` calls this API directly with `fetch()`. If you change one of these public endpoints, update `frontend/src/api.js` and [docs/integration_flow.md](integration_flow.md) in the same change.

## Authentication

The starter scaffold does not require authentication. Add authentication before exposing the backend outside local development.

## Endpoints

### Health

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Check backend health |

### Chat

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/chat/` | Send a message and receive an assistant response |
| `GET` | `/chat/history` | Read recent chat history |
| `DELETE` | `/chat/history` | Clear chat history |

### Tasks

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/tasks/` | Create a task |
| `GET` | `/tasks/` | List tasks |
| `GET` | `/tasks/{task_id}` | Read one task |
| `PATCH` | `/tasks/{task_id}` | Update one task |
| `DELETE` | `/tasks/{task_id}` | Delete one task |
| `GET` | `/tasks/stats/overview` | Read task statistics |

### Memory

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/memory/store` | Store a memory entry |
| `GET` | `/memory/retrieve/{key}` | Retrieve a memory entry by key |
| `GET` | `/memory/search` | Search memory entries |
| `GET` | `/memory/all` | List memory entries |
| `DELETE` | `/memory/{entry_id}` | Delete a memory entry |
| `GET` | `/memory/stats/overview` | Read memory statistics |

### Agents

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/agents/` | List registered agents |
| `GET` | `/agents/{agent_type}` | Read one agent status |
| `POST` | `/agents/{agent_type}/execute` | Execute a task with an agent |

### System

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/system/status` | Read summary system status |
| `GET` | `/system/info` | Read detailed system information |
| `POST` | `/system/reset` | Development reset hook |

## Example Requests

Send a chat message:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/chat/" `
  -ContentType "application/json" `
  -Body '{"message":"Hello","include_memory":true}'
```

Create a task:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/tasks/" `
  -ContentType "application/json" `
  -Body '{"title":"Implement feature X","description":"Build the feature","agent_type":"builder","priority":1}'
```

Run the planner agent:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/agents/planner/execute?task_input=Plan%20a%20small%20feature"
```

Read system status:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/system/status"
```

## Error Handling

The API uses standard HTTP status codes:

- `200`: request succeeded
- `400`: request was invalid
- `404`: requested item was not found
- `500`: unexpected server error

Error responses include a `detail` field when FastAPI raises an HTTP error.
