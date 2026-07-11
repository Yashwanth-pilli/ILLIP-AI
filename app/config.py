"""
ILLIP AI configuration — all settings come from environment variables.
Copy .env.example to .env and fill in what you need. Nothing is hardcoded.
"""

import os
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env into os.environ so code that reads os.environ directly (the
# OpenAI-compat provider, cloud-mode override, etc.) sees it — pydantic only
# reads .env for its own Settings fields, not the process environment.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:
    pass


class Settings(BaseSettings):
    # ── Server ────────────────────────────────────────────────────────────────
    api_host: str = "127.0.0.1"   # set 0.0.0.0 to expose on LAN
    api_port: int = 8000
    debug: bool = False
    cors_origins: str = "*"       # comma-separated origins, or * for open

    # ── Model provider ────────────────────────────────────────────────────────
    # auto | ollama | openai_compat | anthropic | openrouter | groq | llamafile | airllm | mock
    model_provider: str = "auto"

    # Ollama — local models
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "ornith:9b"  # Ornith-9B brain (agentic coding); startup auto-downgrades if it won't fit
    ollama_embed_model: str = "nomic-embed-text"  # used for vector memory embeddings

    # Generic OpenAI-compatible endpoint
    # Use for: DeepSeek, vLLM, LM Studio, Together AI, Mistral, Perplexity, etc.
    openai_compat_base_url: str = ""
    openai_compat_api_key: str = ""
    openai_compat_model: str = ""

    # Anthropic Claude
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # OpenRouter
    openrouter_api_key: str = ""
    openrouter_model: str = "meta-llama/llama-3.1-8b-instruct:free"

    # Groq
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # llamafile
    llamafile_url: str = "http://localhost:8080"
    llamafile_model: str = ""

    # AirLLM — layer-streaming for large models on low VRAM
    airllm_model: str = ""

    # ── API auth (optional) ───────────────────────────────────────────────────
    # Leave empty for local single-user mode. Set to enable API key auth.
    illip_api_keys: str = ""

    # ── Integrations ──────────────────────────────────────────────────────────
    telegram_bot_token: str = ""
    telegram_allowed_users: str = ""

    notion_api_key: str = ""
    notion_db_id: str = ""

    discord_bot_token: str = ""

    slack_bot_token: str = ""
    slack_app_token: str = ""

    email_address: str = ""
    email_password: str = ""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = "whatsapp:+14155238886"

    n8n_base_url: str = "http://localhost:5678"
    n8n_api_key: str = ""

    telegram_storage_token: str = ""
    telegram_storage_chat_id: str = ""

    # ── Search ────────────────────────────────────────────────────────────────
    searxng_url: str = "http://localhost:8888"
    brave_api_key: str = ""

    # ── Voice ─────────────────────────────────────────────────────────────────
    whisper_model: str = "base"    # tiny | base | small | medium | large
    piper_voice: str = ""

    # ── Sync ──────────────────────────────────────────────────────────────────
    sync_git_remote: str = ""

    # ── Data paths ────────────────────────────────────────────────────────────
    database_url: str = "sqlite:///./data/illip.db"
    data_dir: str = "./data"
    memory_dir: str = "./data/memory"
    logs_dir: str = "./data/logs"
    tasks_dir: str = "./data/tasks"
    workspaces_dir: str = "./data/workspaces"
    snapshots_dir: str = "./data/snapshots"

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_file: str = "./data/logs/illip.log"

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value):
        if isinstance(value, str) and value.lower() == "release":
            return False
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="allow",
        protected_namespaces=(),
    )

    @property
    def project_root(self) -> Path:
        return Path(__file__).parent.parent

    def get_absolute_path(self, relative_path: str) -> Path:
        if Path(relative_path).is_absolute():
            return Path(relative_path)
        return self.project_root / relative_path

    def get_data_path(self) -> Path:
        return self.get_absolute_path(self.data_dir)

    def get_memory_path(self) -> Path:
        return self.get_absolute_path(self.memory_dir)

    def get_logs_path(self) -> Path:
        return self.get_absolute_path(self.logs_dir)

    def get_tasks_path(self) -> Path:
        return self.get_absolute_path(self.tasks_dir)

    def get_workspaces_path(self) -> Path:
        return self.get_absolute_path(self.workspaces_dir)

    def get_snapshots_path(self) -> Path:
        return self.get_absolute_path(self.snapshots_dir)

    def ensure_directories(self):
        for path in [
            self.get_data_path(),
            self.get_memory_path(),
            self.get_logs_path(),
            self.get_tasks_path(),
            self.get_workspaces_path(),
            self.get_snapshots_path(),
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def get_cors_origins(self) -> list:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
