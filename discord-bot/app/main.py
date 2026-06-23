"""Discord bot for compiling project report PDFs from channel messages."""

import logging
import os
import sys
import json
import asyncio
import shutil
import traceback
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

from app.discord_util import parse_compile_command
from app.report_service import compile_report
from app.report_agent import run_report_agent, DateParseError, NoMessagesError, NoValidReportsError

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
    """Create a unique temporary subdirectory for a single report request."""
    tmp_base = _get_tmp_base()
    tmp_base.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_path = tmp_base / f"report_{timestamp}_{message_id}"
    temp_path.mkdir(parents=True, exist_ok=True)
    return temp_path


def format_attachment(attachment):
    """Extract metadata from a Discord attachment into a serializable dict."""
    return {
        "id": attachment.id,
        "filename": attachment.filename,
        "url": attachment.url,
        "proxy_url": attachment.proxy_url,
        "content_type": attachment.content_type,
        "size": attachment.size,
        "width": attachment.width,
        "height": attachment.height,
    }


def format_message_payload(message):
    """Extract relevant fields from a Discord message into a serializable dict."""
    return {
        "message_id": message.id,
        "content": message.content,
        "timestamp": message.created_at.isoformat() if message.created_at else None,
        "author": {
            "id": message.author.id,
            "username": message.author.name,
            "display_name": getattr(message.author, "display_name", None),
            "bot": message.author.bot,
        },
        "channel": {
            "id": message.channel.id,
            "name": getattr(message.channel, "name", None),
            "type": str(message.channel.type),
        },
        "guild": {
            "id": message.guild.id if message.guild else None,
            "name": message.guild.name if message.guild else None,
        },
        "attachments": [format_attachment(att) for att in message.attachments],
    }


def print_message(payload):
    """Pretty-print the message payload to the console."""
    print("=" * 60)
    print(f"[DISCORD MESSAGE RECEIVED] {datetime.now().isoformat()}")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print("=" * 60)


def _is_nl_report_request(content: str) -> bool:
    """Detect if the message is a natural language report request."""
    text = content.lower()
    keywords = ["report", "laporan", "bikin", "buatkan", "tolong"]
    return any(kw in text for kw in keywords)


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


async def _handle_nl_report_command(message):
    """Handle natural language report requests via the agent."""
    ack_message = await message.reply("perintah diterima, sedang memproses laporan...")
    temp_path = None

    try:
        temp_path = _create_temp_dir(message.id)
        pdf_paths = await run_report_agent(
            channel=message.channel,
            user_query=message.content,
            temp_dir=temp_path,
        )

        # Upload all PDFs
        files = [discord.File(path) for path in pdf_paths]
        await message.reply(files=files)

        # Update ack message
        await ack_message.edit(
            content=f"✅ {len(pdf_paths)} laporan berhasil dibuat!"
        )

    except DateParseError as e:
        logger.error("DateParseError: %s", e.message)
        await ack_message.edit(content=e.message)
    except NoMessagesError as e:
        logger.error("NoMessagesError: %s", e.message)
        await ack_message.edit(content=e.message)
    except NoValidReportsError as e:
        logger.error("NoValidReportsError: %s", e.message)
        await ack_message.edit(content=e.message)
    except Exception as e:
        logger.exception("Unexpected error in NL report agent: %s", e)
        await ack_message.edit(
            content="Gagal membuat laporan secara otomatis, silakan buat laporan secara manual."
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

        # Try to parse the compile command first
        dates = parse_compile_command(message.content)
        if dates is not None:
            start_date, end_date = dates
            await _handle_compile_command(message, start_date, end_date)
            return

        # Try natural language report request
        if _is_nl_report_request(message.content):
            await _handle_nl_report_command(message)
            return

    return bot


async def _handle_compile_command(message, start_date, end_date):
    """
    Handle the compile command: acknowledge, compile, and upload PDFs.
    """
    # Acknowledge
    ack_message = await message.reply("perintah diterima, compiling reports...")
    temp_path = None

    try:
        temp_path = _create_temp_dir(message.id)
        pdf_paths = await compile_report(
            message.channel,
            start_date,
            end_date,
            temp_path,
        )

        if not pdf_paths:
            await ack_message.edit(content="tidak ada chat tentang laporan proyek")
            return

        # Upload all PDFs
        files = [discord.File(path) for path in pdf_paths]
        await message.reply(files=files)

        # Update ack message
        await ack_message.edit(
            content=f"✅ {len(pdf_paths)} laporan berhasil dibuat!"
        )

    except Exception as e:
        print(f"❌ Error compiling report: {e}")
        await ack_message.edit(content="terjadi kesalahan saat membuat laporan. coba lagi nanti.")
    finally:
        if temp_path and temp_path.exists():
            try:
                shutil.rmtree(temp_path)
                logger.info("Cleaned up temp directory: %s", temp_path)
            except Exception:
                logger.warning("Failed to clean up temp directory: %s", temp_path)


if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN or DISCORD_BOT_TOKEN == "your_bot_token_here":
        print("❌ Error: DISCORD_BOT_TOKEN not set in .env file")
        exit(1)

    bot = create_bot()
    bot.run(DISCORD_BOT_TOKEN)
