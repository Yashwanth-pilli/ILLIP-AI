"""
Plugin API — create / list / delete user-defined connectors.

POST   /api/plugins/          — create or update plugin from JSON spec
GET    /api/plugins/          — list all plugins
GET    /api/plugins/{name}    — get one plugin spec
DELETE /api/plugins/{name}    — delete plugin
GET    /api/plugins/templates — example specs for common connector types
"""

from fastapi import APIRouter, HTTPException
from app.plugins.registry import save_plugin, delete_plugin, list_plugins, _plugins_dir
import json

router = APIRouter(prefix="/plugins", tags=["plugins"])

# ── Community catalogue — install with POST /api/plugins/install/{name} ──────
_CATALOGUE = [
    {
        "name": "weather_wttr",
        "display_name": "Weather (wttr.in)",
        "description": "Current weather for any city — free, no API key needed",
        "category": "utilities",
        "plugin_type": "http",
        "config": {"url": "https://wttr.in/{city}?format=3", "method": "GET", "headers": {}, "body_template": ""},
        "parameters": {"type": "object", "properties": {"city": {"type": "string", "description": "City name, e.g. London"}}, "required": ["city"]},
    },
    {
        "name": "exchange_rate",
        "display_name": "Exchange Rates (Frankfurter)",
        "description": "Currency exchange rates — free, no key needed",
        "category": "finance",
        "plugin_type": "http",
        "config": {"url": "https://api.frankfurter.app/latest?from={from_currency}&to={to_currency}", "method": "GET", "headers": {}, "body_template": ""},
        "parameters": {"type": "object", "properties": {"from_currency": {"type": "string", "description": "Source currency, e.g. USD"}, "to_currency": {"type": "string", "description": "Target currency, e.g. EUR"}}, "required": ["from_currency", "to_currency"]},
    },
    {
        "name": "ip_geolocation",
        "display_name": "IP Geolocation (ip-api)",
        "description": "Look up location info for any IP address — free, no key needed",
        "category": "utilities",
        "plugin_type": "http",
        "config": {"url": "http://ip-api.com/json/{ip}", "method": "GET", "headers": {}, "body_template": ""},
        "parameters": {"type": "object", "properties": {"ip": {"type": "string", "description": "IP address, e.g. 8.8.8.8"}}, "required": ["ip"]},
    },
    {
        "name": "github_repo",
        "display_name": "GitHub Repo Info",
        "description": "Get info about any GitHub repository — free, no key needed",
        "category": "developer",
        "plugin_type": "http",
        "config": {"url": "https://api.github.com/repos/{owner}/{repo}", "method": "GET", "headers": {"Accept": "application/vnd.github+json"}, "body_template": ""},
        "parameters": {"type": "object", "properties": {"owner": {"type": "string", "description": "GitHub username or org"}, "repo": {"type": "string", "description": "Repository name"}}, "required": ["owner", "repo"]},
    },
    {
        "name": "hacker_news_top",
        "display_name": "Hacker News Top Stories",
        "description": "Fetch top story IDs from Hacker News — free, no key needed",
        "category": "news",
        "plugin_type": "http",
        "config": {"url": "https://hacker-news.firebaseio.com/v0/topstories.json?limitToFirst=10&orderBy=%22$key%22", "method": "GET", "headers": {}, "body_template": ""},
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "open_library_search",
        "display_name": "Open Library Book Search",
        "description": "Search millions of books via Open Library — free, no key needed",
        "category": "research",
        "plugin_type": "http",
        "config": {"url": "https://openlibrary.org/search.json?q={query}&limit=5", "method": "GET", "headers": {}, "body_template": ""},
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Book title, author, or topic"}}, "required": ["query"]},
    },
    {
        "name": "open_meteo_weather",
        "display_name": "Open-Meteo Weather (Lat/Lon)",
        "description": "Accurate weather forecast by coordinates — free, no key needed",
        "category": "utilities",
        "plugin_type": "http",
        "config": {"url": "https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true", "method": "GET", "headers": {}, "body_template": ""},
        "parameters": {"type": "object", "properties": {"lat": {"type": "string", "description": "Latitude, e.g. 51.5"}, "lon": {"type": "string", "description": "Longitude, e.g. -0.12"}}, "required": ["lat", "lon"]},
    },
    {
        "name": "wikipedia_summary",
        "display_name": "Wikipedia Summary",
        "description": "Get Wikipedia article summary for any topic — free, no key needed",
        "category": "research",
        "plugin_type": "http",
        "config": {"url": "https://en.wikipedia.org/api/rest_v1/page/summary/{topic}", "method": "GET", "headers": {"Accept": "application/json"}, "body_template": ""},
        "parameters": {"type": "object", "properties": {"topic": {"type": "string", "description": "Wikipedia article title, e.g. Python_(programming_language)"}}, "required": ["topic"]},
    },
    {
        "name": "joke_api",
        "display_name": "Random Joke (JokeAPI)",
        "description": "Get a random programming joke — free, no key needed",
        "category": "fun",
        "plugin_type": "http",
        "config": {"url": "https://v2.jokeapi.dev/joke/Programming?type=single", "method": "GET", "headers": {}, "body_template": ""},
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "country_info",
        "display_name": "Country Info (RestCountries)",
        "description": "Detailed info about any country — free, no key needed",
        "category": "research",
        "plugin_type": "http",
        "config": {"url": "https://restcountries.com/v3.1/name/{country}", "method": "GET", "headers": {}, "body_template": ""},
        "parameters": {"type": "object", "properties": {"country": {"type": "string", "description": "Country name, e.g. India"}}, "required": ["country"]},
    },
    {
        "name": "n8n_webhook",
        "display_name": "n8n Webhook",
        "description": "Trigger any n8n workflow via webhook URL",
        "category": "automation",
        "plugin_type": "http",
        "config": {"url": "{webhook_url}", "method": "POST", "headers": {"Content-Type": "application/json"}, "body_template": '{"message": "{message}", "source": "illip"}'},
        "parameters": {"type": "object", "properties": {"webhook_url": {"type": "string", "description": "Your n8n webhook URL"}, "message": {"type": "string", "description": "Payload to send"}}, "required": ["webhook_url", "message"]},
    },
    {
        "name": "openrouter_chat",
        "display_name": "OpenRouter Chat",
        "description": "Call any model via OpenRouter API (needs OPENROUTER_API_KEY)",
        "category": "ai",
        "plugin_type": "http",
        "config": {"url": "https://openrouter.ai/api/v1/chat/completions", "method": "POST", "headers": {"Authorization": "Bearer YOUR_OPENROUTER_KEY", "Content-Type": "application/json"}, "body_template": '{"model": "mistralai/mistral-7b-instruct", "messages": [{"role": "user", "content": "{prompt}"}]}'},
        "parameters": {"type": "object", "properties": {"prompt": {"type": "string", "description": "Message to send to the model"}}, "required": ["prompt"]},
    },
]


@router.get("/catalogue")
async def get_catalogue(category: str = ""):
    """Browse community plugins. Filter by category if provided."""
    items = _CATALOGUE if not category else [p for p in _CATALOGUE if p.get("category") == category]
    categories = sorted({p["category"] for p in _CATALOGUE})
    return {"catalogue": items, "count": len(items), "categories": categories}


@router.post("/install/{name}")
async def install_from_catalogue(name: str):
    """Install a community plugin by name. Adds it to your local plugins."""
    spec = next((p for p in _CATALOGUE if p["name"] == name), None)
    if not spec:
        raise HTTPException(status_code=404, detail=f"'{name}' not in catalogue. GET /api/plugins/catalogue to browse.")
    path = save_plugin(spec)
    return {"status": "installed", "name": name, "display_name": spec["display_name"], "path": str(path)}


@router.get("/templates")
async def get_templates():
    """Example plugin specs the user can copy and fill in."""
    return {
        "templates": [
            {
                "name": "my_weather",
                "display_name": "Weather (wttr.in)",
                "description": "Get current weather for any city — free, no key needed",
                "plugin_type": "http",
                "config": {
                    "url": "https://wttr.in/{city}?format=3",
                    "method": "GET",
                    "headers": {},
                    "body_template": "",
                },
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "City name, e.g. London"}
                    },
                    "required": ["city"],
                },
            },
            {
                "name": "my_notion",
                "display_name": "Notion Search",
                "description": "Search your Notion workspace",
                "plugin_type": "http",
                "config": {
                    "url": "https://api.notion.com/v1/search",
                    "method": "POST",
                    "headers": {
                        "Authorization": "Bearer YOUR_NOTION_TOKEN",
                        "Notion-Version": "2022-06-28",
                        "Content-Type": "application/json",
                    },
                    "body_template": '{"query": "{query}"}',
                },
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "What to search for in Notion"}
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "my_webhook",
                "display_name": "Custom Webhook",
                "description": "POST data to any webhook URL (n8n, Zapier, etc.)",
                "plugin_type": "http",
                "config": {
                    "url": "https://your-webhook-url.com/hook",
                    "method": "POST",
                    "headers": {"Content-Type": "application/json"},
                    "body_template": '{"message": "{message}", "source": "illip"}',
                },
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "Message to send to webhook"}
                    },
                    "required": ["message"],
                },
            },
            {
                "name": "my_github_status",
                "display_name": "GitHub Repo Status",
                "description": "Get info about any GitHub repo",
                "plugin_type": "http",
                "config": {
                    "url": "https://api.github.com/repos/{owner}/{repo}",
                    "method": "GET",
                    "headers": {"Accept": "application/vnd.github+json"},
                    "body_template": "",
                },
                "parameters": {
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string", "description": "GitHub username or org"},
                        "repo":  {"type": "string", "description": "Repository name"},
                    },
                    "required": ["owner", "repo"],
                },
            },
        ]
    }


@router.get("/")
async def list_all_plugins():
    return {"plugins": list_plugins(), "count": len(list_plugins())}


@router.get("/{name}")
async def get_plugin(name: str):
    path = _plugins_dir() / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")
    return json.loads(path.read_text(encoding="utf-8"))


@router.post("/")
async def create_or_update_plugin(spec: dict):
    """
    Create or update a plugin. Spec must have: name, plugin_type, config, parameters.
    Immediately usable — no restart needed.
    """
    if not spec.get("name"):
        raise HTTPException(status_code=400, detail="spec.name required")
    if not spec.get("plugin_type"):
        spec["plugin_type"] = "http"
    path = save_plugin(spec)
    return {"status": "registered", "name": spec["name"], "path": str(path)}


@router.delete("/{name}")
async def remove_plugin(name: str):
    ok = delete_plugin(name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")
    return {"status": "deleted", "name": name}
