"""
API key authentication middleware.

When ILLIP_API_KEYS is set in .env, all API endpoints require an API key.
Leave unset for local single-user mode (no auth).

Usage in .env:
  ILLIP_API_KEYS=key1,key2,key3

Clients pass key via:
  Authorization: Bearer <key>
  X-API-Key: <key>

Exempt paths (always open):
  /           (frontend)
  /docs /redoc /openapi.json
  /api/health
  /v1/models  (Continue.dev probes this without auth)
"""

import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

_EXEMPT_PREFIXES = ("/docs", "/redoc", "/openapi.json", "/data/", "/v1/models")
_EXEMPT_EXACT = {"/", "/api/health", "/api/health/"}

_keys: set[str] | None = None


def _get_keys() -> set[str] | None:
    global _keys
    if _keys is None:
        raw = os.environ.get("ILLIP_API_KEYS", "").strip()
        _keys = {k.strip() for k in raw.split(",") if k.strip()} if raw else set()
    return _keys or None  # None = auth disabled


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        keys = _get_keys()
        if keys is None:
            return await call_next(request)  # no auth configured

        path = request.url.path

        # Exempt static frontend (everything without /api or /v1 prefix)
        if not path.startswith("/api") and not path.startswith("/v1"):
            return await call_next(request)

        if path in _EXEMPT_EXACT:
            return await call_next(request)

        if any(path.startswith(p) for p in _EXEMPT_PREFIXES):
            return await call_next(request)

        # Extract key from headers
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            provided = auth[7:].strip()
        else:
            provided = request.headers.get("X-API-Key", "").strip()

        if provided not in keys:
            return JSONResponse(
                {"detail": "Invalid or missing API key. Set Authorization: Bearer <key>"},
                status_code=401,
            )

        return await call_next(request)
