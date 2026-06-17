"""Discord bot for compiling project report PDFs from channel messages."""

import os
import sys
import json
import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import discord

# Add parent directory to path so `app` package can be imported when running
# `python app/main.py` directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.parser import parse_compile_command
from app.report_service import compile_report

# Load environment variables from .env file
load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")


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


def create_bot():
    """Create and configure the Discord bot instance."""
    intents = discord.Intents.default()
    intents.message_content = True

    bot = discord.Bot(intents=intents)

    @bot.event
    async def on_ready():
        """Triggered when the bot successfully connects to Discord."""
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

        # Check if the bot is mentioned
        if bot.user not in message.mentions:
            return

        # Try to parse the compile command
        dates = parse_compile_command(message.content)
        if dates is None:
            return

        start_date, end_date = dates
        await _handle_compile_command(message, start_date, end_date)

    return bot


async def _handle_compile_command(message, start_date, end_date):
    """
    Handle the compile command: acknowledge, compile, and upload PDFs.
    """
    # Acknowledge
    ack_message = await message.reply("perintah diterima, compiling reports...")

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir)
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


if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN or DISCORD_BOT_TOKEN == "your_bot_token_here":
        print("❌ Error: DISCORD_BOT_TOKEN not set in .env file")
        exit(1)

    bot = create_bot()
    bot.run(DISCORD_BOT_TOKEN)
