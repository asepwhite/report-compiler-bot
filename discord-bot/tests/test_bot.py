import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


def test_format_message_payload():
    """Test that message payload is formatted correctly with all fields."""
    from app.main import format_message_payload

    msg = MagicMock()
    msg.id = 123456789
    msg.content = "Hello bot!"
    msg.created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    msg.author = MagicMock()
    msg.author.id = 987654321
    msg.author.name = "testuser"
    msg.author.display_name = "TestUser"
    msg.author.bot = False

    msg.channel = MagicMock()
    msg.channel.id = 111222333
    msg.channel.name = "general"
    msg.channel.type = MagicMock()
    msg.channel.type.__str__ = lambda self: "text"

    msg.guild = MagicMock()
    msg.guild.id = 444555666
    msg.guild.name = "Test Server"

    payload = format_message_payload(msg)

    assert payload["message_id"] == 123456789
    assert payload["content"] == "Hello bot!"
    assert payload["timestamp"] == "2024-01-01T12:00:00+00:00"
    assert payload["author"]["id"] == 987654321
    assert payload["author"]["username"] == "testuser"
    assert payload["author"]["display_name"] == "TestUser"
    assert payload["author"]["bot"] is False
    assert payload["channel"]["id"] == 111222333
    assert payload["channel"]["name"] == "general"
    assert payload["channel"]["type"] == "text"
    assert payload["guild"]["id"] == 444555666
    assert payload["guild"]["name"] == "Test Server"


def test_format_message_payload_no_guild():
    """Test that DM messages (no guild) are handled gracefully."""
    from app.main import format_message_payload

    msg = MagicMock()
    msg.id = 123
    msg.content = "Direct message"
    msg.created_at = None

    msg.author = MagicMock()
    msg.author.id = 456
    msg.author.name = "dmuser"
    msg.author.display_name = "DMUser"
    msg.author.bot = False

    msg.channel = MagicMock()
    msg.channel.id = 789
    msg.channel.name = None
    msg.channel.type = MagicMock()
    msg.channel.type.__str__ = lambda self: "private"

    msg.guild = None

    payload = format_message_payload(msg)

    assert payload["guild"]["id"] is None
    assert payload["guild"]["name"] is None
    assert payload["channel"]["name"] is None
    assert payload["timestamp"] is None


def test_format_message_payload_bot_message():
    """Test that bot messages include the bot flag."""
    from app.main import format_message_payload

    msg = MagicMock()
    msg.id = 999
    msg.content = "Bot response"
    msg.created_at = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)

    msg.author = MagicMock()
    msg.author.id = 111
    msg.author.name = "botuser"
    msg.author.display_name = "BotUser"
    msg.author.bot = True

    msg.channel = MagicMock()
    msg.channel.id = 222
    msg.channel.name = "commands"
    msg.channel.type = MagicMock()
    msg.channel.type.__str__ = lambda self: "text"

    msg.guild = MagicMock()
    msg.guild.id = 333
    msg.guild.name = "Server"

    payload = format_message_payload(msg)
    assert payload["author"]["bot"] is True


def test_create_bot_returns_bot_instance():
    """Test that create_bot returns a bot object with message_content intent enabled."""
    from app.main import create_bot

    bot = create_bot()
    assert bot is not None
    # In py-cord, the intent flags are accessible via bot.intents
    assert bot.intents.message_content is True


def test_env_token_loaded():
    """Test that DISCORD_BOT_TOKEN is loaded from the environment."""
    from app.main import DISCORD_BOT_TOKEN
    # The .env file should have a token set
    assert DISCORD_BOT_TOKEN is not None
    assert len(DISCORD_BOT_TOKEN) > 0
    assert DISCORD_BOT_TOKEN != "your_bot_token_here"


def test_format_message_payload_no_attachments():
    """Test that messages without attachments have an empty attachments list."""
    from app.main import format_message_payload

    msg = MagicMock()
    msg.id = 100
    msg.content = "Just text"
    msg.created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    msg.attachments = []

    msg.author = MagicMock()
    msg.author.id = 1
    msg.author.name = "user"
    msg.author.display_name = "User"
    msg.author.bot = False

    msg.channel = MagicMock()
    msg.channel.id = 2
    msg.channel.name = "general"
    msg.channel.type = MagicMock()
    msg.channel.type.__str__ = lambda self: "text"

    msg.guild = MagicMock()
    msg.guild.id = 3
    msg.guild.name = "Server"

    payload = format_message_payload(msg)
    assert payload["attachments"] == []


def test_format_message_payload_with_single_attachment():
    """Test that a message with one image attachment includes its metadata."""
    from app.main import format_message_payload

    msg = MagicMock()
    msg.id = 200
    msg.content = "Check this out!"
    msg.created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    att = MagicMock()
    att.id = 111222333
    att.filename = "meme.png"
    att.url = "https://cdn.discordapp.com/attachments/111/222/meme.png"
    att.proxy_url = "https://media.discordapp.net/attachments/111/222/meme.png"
    att.content_type = "image/png"
    att.size = 12345
    att.width = 800
    att.height = 600

    msg.attachments = [att]

    msg.author = MagicMock()
    msg.author.id = 1
    msg.author.name = "user"
    msg.author.display_name = "User"
    msg.author.bot = False

    msg.channel = MagicMock()
    msg.channel.id = 2
    msg.channel.name = "general"
    msg.channel.type = MagicMock()
    msg.channel.type.__str__ = lambda self: "text"

    msg.guild = MagicMock()
    msg.guild.id = 3
    msg.guild.name = "Server"

    payload = format_message_payload(msg)
    assert len(payload["attachments"]) == 1
    att_payload = payload["attachments"][0]
    assert att_payload["id"] == 111222333
    assert att_payload["filename"] == "meme.png"
    assert att_payload["url"] == "https://cdn.discordapp.com/attachments/111/222/meme.png"
    assert att_payload["proxy_url"] == "https://media.discordapp.net/attachments/111/222/meme.png"
    assert att_payload["content_type"] == "image/png"
    assert att_payload["size"] == 12345
    assert att_payload["width"] == 800
    assert att_payload["height"] == 600


def test_format_message_payload_with_multiple_attachments():
    """Test that a message with multiple attachments includes all of them."""
    from app.main import format_message_payload

    msg = MagicMock()
    msg.id = 300
    msg.content = ""
    msg.created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    att1 = MagicMock()
    att1.id = 1
    att1.filename = "a.png"
    att1.url = "https://cdn.discordapp.com/a.png"
    att1.proxy_url = "https://media.discordapp.net/a.png"
    att1.content_type = "image/png"
    att1.size = 100
    att1.width = 100
    att1.height = 100

    att2 = MagicMock()
    att2.id = 2
    att2.filename = "b.jpg"
    att2.url = "https://cdn.discordapp.com/b.jpg"
    att2.proxy_url = "https://media.discordapp.net/b.jpg"
    att2.content_type = "image/jpeg"
    att2.size = 200
    att2.width = 200
    att2.height = 200

    msg.attachments = [att1, att2]

    msg.author = MagicMock()
    msg.author.id = 1
    msg.author.name = "user"
    msg.author.display_name = "User"
    msg.author.bot = False

    msg.channel = MagicMock()
    msg.channel.id = 2
    msg.channel.name = "general"
    msg.channel.type = MagicMock()
    msg.channel.type.__str__ = lambda self: "text"

    msg.guild = MagicMock()
    msg.guild.id = 3
    msg.guild.name = "Server"

    payload = format_message_payload(msg)
    assert len(payload["attachments"]) == 2
    assert payload["attachments"][0]["filename"] == "a.png"
    assert payload["attachments"][1]["filename"] == "b.jpg"
