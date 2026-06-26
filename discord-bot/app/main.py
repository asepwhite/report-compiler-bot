"""Discord bot for compiling project report PDFs from channel messages."""

import logging
import os
import sys
import json
import shutil
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import discord

# Add parent directory to path so `app` package can be imported when running
# `python app/main.py` directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .env file BEFORE importing app modules
# that read env vars at module level.
load_dotenv()

from app.report_agent import run_report_agent
from app.project_agent import run_project_agent
from app.intent_classifier import classify_intent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

logger = logging.getLogger(__name__)


def _get_tmp_base() -> Path:
    """Return the project-local temporary directory path."""
    return Path(__file__).parent.parent / "tmp"


def _cleanup_stale_tmp():
    """Remove any leftover temporary subdirectories from previous runs."""
    tmp_base = _get_tmp_base()
    if not tmp_base.exists():
        return
    for subdir in tmp_base.iterdir():
        if subdir.is_dir():
            try:
                shutil.rmtree(subdir)
                logger.info("Cleaned up stale temp directory: %s", subdir)
            except Exception:
                logger.warning("Failed to clean up stale temp directory: %s", subdir)


def _create_temp_dir(message_id: int) -> Path:
    """Create a unique temporary directory for a single report request."""
    tmp_base = _get_tmp_base()
    tmp_base.mkdir(parents=True, exist_ok=True)
    temp_dir = tmp_base / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{message_id}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def format_message_payload(message):
    """Format a Discord message into a JSON-serializable dict."""
    return {
        "message_id": message.id,
        "content": message.content,
        "timestamp": message.created_at.isoformat() if message.created_at else None,
        "author": {
            "id": message.author.id,
            "username": message.author.name,
            "display_name": message.author.display_name,
            "bot": message.author.bot,
        },
        "channel": {
            "id": message.channel.id,
            "name": message.channel.name,
            "type": str(message.channel.type),
        },
        "guild": {
            "id": message.guild.id,
            "name": message.guild.name,
        },
        "attachments": [
            {
                "id": att.id,
                "filename": att.filename,
                "url": att.url,
                "content_type": att.content_type,
            }
            for att in message.attachments
        ],
    }


def print_message(payload):
    """Pretty-print the message payload to the console."""
    print("=" * 60)
    print(f"[DISCORD MESSAGE RECEIVED] {datetime.now().isoformat()}")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print("=" * 60)


def _is_bot_mentioned(message, bot_user) -> bool:
    """Check if the bot was mentioned directly as a user or via a role."""
    # Direct user mention
    if bot_user in message.mentions:
        return True
    # Role mention — check if bot is a member of any mentioned role
    for role in message.role_mentions:
        if hasattr(bot_user, "roles") and role in bot_user.roles:
            return True
    return False


async def _handle_nl_command(message):
    """Handle any bot mention by classifying intent and delegating to the right agent."""
    temp_path = None
    ack_message = None

    try:
        # Classify intent first
        intent_result = classify_intent(message.content)

        if intent_result.intent == "greeting":
            await message.reply(
                "Halo! Ada yang bisa saya bantu? "
                "Saya bisa membantu pembuatan laporan atau manajemen data project."
            )
            return

        if intent_result.intent == "off_topic":
            await message.reply(
                "Maaf, saya hanya bisa membantu dengan pembuatan laporan atau manajemen data project. "
                "Ada yang bisa saya bantu?"
            )
            return

        if intent_result.intent == "project_crud":
            ack_message = await message.reply(
                "⏳ Sedang memproses data project, mohon tunggu..."
            )

            result = await run_project_agent(user_query=message.content)

            if result["type"] == "error":
                await ack_message.edit(content=f"❌ {result['message']}")
            else:
                await ack_message.edit(content=f"✅ {result['message']}")
            return

        # Default: report_request
        temp_path = _create_temp_dir(message.id)

        async def send_ack():
            nonlocal ack_message
            ack_message = await message.reply(
                "⏳ Sedang memproses laporan, mohon tunggu..."
            )

        result = await run_report_agent(
            channel=message.channel,
            user_query=message.content,
            temp_dir=temp_path,
            send_ack=send_ack,
        )

        if result["type"] == "off_topic":
            await message.reply(result["message"])
            return

        if result["type"] == "greeting":
            await message.reply(result["message"])
            return

        if result["type"] == "error":
            if ack_message:
                await ack_message.edit(content=f"❌ {result['message']}")
            else:
                await message.reply(result["message"])
            return

        if result["type"] == "report":
            files = [discord.File(path) for path in result["pdf_paths"]]
            await message.reply(files=files)
            if ack_message:
                await ack_message.edit(
                    content=f"✅ {len(result['pdf_paths'])} laporan berhasil dibuat!"
                )
            return

    except Exception as e:
        logger.exception("Unexpected error in NL command handler: %s", e)
        if ack_message:
            await ack_message.edit(
                content="Terjadi kesalahan. Silakan coba lagi nanti."
            )
        else:
            await message.reply(
                "Terjadi kesalahan. Silakan coba lagi nanti."
            )
    finally:
        if temp_path and temp_path.exists():
            try:
                shutil.rmtree(temp_path)
                logger.info("Cleaned up temp directory: %s", temp_path)
            except Exception:
                logger.warning("Failed to clean up temp directory: %s", temp_path)


def create_bot():
    """Create and configure the Discord bot instance."""
    intents = discord.Intents.default()
    intents.message_content = True

    bot = discord.Bot(intents=intents)

    @bot.event
    async def on_ready():
        """Triggered when the bot successfully connects to Discord."""
        _cleanup_stale_tmp()
        print(f"✅ Bot is online! Logged in as {bot.user} (ID: {bot.user.id})")

    @bot.event
    async def on_message(message):
        """
        Triggered when a message is received in any channel the bot can see.
        Skips messages from other bots to avoid loops.
        """
        if message.author.bot:
            return

        payload = format_message_payload(message)
        print_message(payload)

        # Check if the bot is mentioned (directly or via a role)
        if not _is_bot_mentioned(message, bot.user):
            return

        # Any mention triggers the agent
        await _handle_nl_command(message)

    return bot


if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN or DISCORD_BOT_TOKEN == "your_bot_token_here":
        print("❌ Error: DISCORD_BOT_TOKEN not set in .env file")
        exit(1)

    bot = create_bot()
    bot.run(DISCORD_BOT_TOKEN)
