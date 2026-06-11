# Discord Bot

A minimal Discord bot that listens to messages in servers and prints them to the console.

## Setup

### 1. Get a Discord Bot Token

1. Go to the **Discord Developer Portal**: https://discord.com/developers/applications
2. Click **"New Application"** and give it a name
3. Go to the **"Bot"** tab on the left sidebar
4. Click **"Add Bot"**
5. Under **Token**, click **"Reset Token"** and copy it
6. **Enable Privileged Intents** — scroll down to "Privileged Gateway Intents" and toggle **ON**:
   - `MESSAGE CONTENT INTENT` (required to read message text)

### 2. Invite the Bot to Your Server

1. Go to the **"OAuth2"** tab → **"URL Generator"**
2. Under **Scopes**, select **"bot"**
3. Under **Bot Permissions**, select:
   - `Send Messages`
   - `Read Message History`
   - `View Channels`
4. Copy the generated URL and paste it in your browser
5. Choose a server you own and authorize the bot

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your DISCORD_BOT_TOKEN
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Run the Bot

```bash
python app/main.py
```

You should see:
```
✅ Bot is online! Logged in as YourBotName (ID: 123456789)
```

## Test the Bot

Send a message in any channel where the bot is present. The bot will print the message payload to the console:

```
============================================================
[DISCORD MESSAGE RECEIVED] 2024-06-10T12:00:00
{
  "message_id": 123456789,
  "content": "Hello bot!",
  "timestamp": "2024-06-10T12:00:00+00:00",
  "author": {
    "id": 987654321,
    "username": "testuser",
    "display_name": "TestUser",
    "bot": false
  },
  "channel": {
    "id": 111222333,
    "name": "general",
    "type": "text"
  },
  "guild": {
    "id": 444555666,
    "name": "My Server"
  }
}
============================================================
```

## Important Notes

- **No outgoing calls:** This is a strictly print-only receiver — no replies are sent to Discord.
- **Skips bot messages:** The bot ignores messages from other bots to avoid loops.
- **Direct messages (DMs):** The bot will also print DMs if it has the `message_content` intent.
- **Image attachments:** When a message includes images, the bot prints the attachment metadata (filename, URL, dimensions, etc.) in the payload.

## Project Structure

```
discord-bot/
├── app/
│   ├── __init__.py
│   └── main.py          # Bot client & message listener
├── tests/
│   ├── __init__.py
│   └── test_bot.py      # Unit tests
├── .env                 # Environment variables (not tracked)
├── .env.example         # Example env file
├── requirements.txt     # Python dependencies
└── README.md            # This file
```

## Run Tests

```bash
python -m pytest tests/ -v
```

## Troubleshooting

**Bot not receiving messages?**
- Verify the bot has the `MESSAGE CONTENT INTENT` enabled in the Developer Portal
- Check that the bot is invited to the server with `View Channels` and `Read Message History` permissions
- Make sure the bot has access to the specific channel you're testing in

**Token not loading?**
- Ensure `.env` is in the `discord-bot/` directory
- The token should not be wrapped in quotes
