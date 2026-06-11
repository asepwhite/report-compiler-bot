import os
import json
from datetime import datetime
from dotenv import load_dotenv
import discord

# Load environment variables from .env file
load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")


def format_attachment(attachment):
    """
    Extract metadata from a Discord attachment into a serializable dict.
    """
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
    """
    Extract relevant fields from a Discord message into a serializable dict.
    """
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
    """
    Pretty-print the message payload to the console.
    """
    print("=" * 60)
    print(f"[DISCORD MESSAGE RECEIVED] {datetime.now().isoformat()}")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print("=" * 60)


def create_bot():
    """
    Create and configure the Discord bot instance.
    """
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

    return bot


if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN or DISCORD_BOT_TOKEN == "your_bot_token_here":
        print("❌ Error: DISCORD_BOT_TOKEN not set in .env file")
        exit(1)

    bot = create_bot()
    bot.run(DISCORD_BOT_TOKEN)
