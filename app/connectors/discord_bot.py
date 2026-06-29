"""
Discord bot connector — optional, activates if DISCORD_BOT_TOKEN is set.

Commands:
  !illip <message>  → ILLIP chat
  !status           → system status
  !agents           → list agents
"""

import os
from app.utils import logger

_bot = None
_running = False

_DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")


def _chunk(text: str, size: int = 1900):
    """Split text into Discord-safe chunks."""
    for i in range(0, len(text), size):
        yield text[i:i + size]


async def start_discord_bot():
    global _bot, _running
    if not _DISCORD_TOKEN:
        logger.info("Discord: DISCORD_BOT_TOKEN not set, skipping")
        return
    try:
        import discord  # type: ignore
    except ImportError:
        logger.warning("Discord: discord.py not installed. pip install discord.py")
        return

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    _bot = client

    @client.event
    async def on_ready():
        logger.info(f"Discord bot ready: {client.user}")

    @client.event
    async def on_message(message):
        if message.author == client.user:
            return

        content = message.content.strip()

        if content.startswith("!illip "):
            user_input = content[7:].strip()
            if not user_input:
                await message.channel.send("Usage: `!illip <your message>`")
                return
            try:
                from app.services.chat_service import ChatService
                svc = ChatService()
                reply = await svc.chat(user_input, stream=False)
                text = reply if isinstance(reply, str) else str(reply)
                for chunk in _chunk(text):
                    await message.channel.send(chunk)
            except Exception as e:
                logger.error(f"Discord chat error: {e}")
                await message.channel.send(f"Error: {e}")

        elif content == "!status":
            try:
                import httpx
                from app.config import settings as _cfg
                _base = f"http://127.0.0.1:{_cfg.api_port}"
                async with httpx.AsyncClient() as hc:
                    r = await hc.get(f"{_base}/api/health", timeout=5)
                    data = r.json()
                await message.channel.send(f"```json\n{data}\n```")
            except Exception as e:
                await message.channel.send(f"Status check failed: {e}")

        elif content == "!agents":
            try:
                from app.agents import get_agent_registry
                reg = get_agent_registry()
                names = list(reg.list_agents().keys())
                await message.channel.send("**Agents:** " + ", ".join(names))
            except Exception as e:
                await message.channel.send(f"Error: {e}")

    _running = True
    try:
        await client.start(_DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Discord bot error: {e}")
        _running = False


async def stop_discord_bot():
    global _bot, _running
    if _bot:
        try:
            await _bot.close()
        except Exception as e:
            logger.error(f"Discord stop error: {e}")
    _running = False
    _bot = None


from app.connectors.base_connector import BaseConnector  # noqa: E402


class DiscordConnector(BaseConnector):
    name = "discord"
    description = "Discord bot — !illip, !status, !agents commands"
    required_env_vars = ["DISCORD_BOT_TOKEN"]

    async def start(self) -> bool:
        await start_discord_bot()
        return _running

    async def stop(self) -> None:
        await stop_discord_bot()

    def is_active(self) -> bool:
        return _running
