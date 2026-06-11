# Discord Report Compiler Bot

A Discord bot that compiles project report PDFs from channel messages containing images and structured metadata.

## Features

- **Mention-based command**: `@reporting-bot compile {start-date} {end-date}` (yyyy-mm-dd, GMT+7, inclusive)
- **Acknowledgment**: Bot replies "perintah diterima, compiling reports..." upon receiving the command
- **Message filtering**: Only processes messages with image attachments and the format:
  ```
  id: {tower-id}
  sub-id: {tower-section}
  tanggal: {yyyy-mm-dd}
  ```
- **PDF generation**: Creates a PDF per `tower-id` with:
  - Title: `Progress report {id} - {start date} - {end date}`
  - Sections per `sub-id` with images in a grid layout (3 columns)
  - Filename: `report-{id}-{start date}-{end date}.pdf`
- **Output**: Uploads all generated PDFs back to the Discord channel

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
   - `Attach Files` (required to upload PDFs)
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

## Usage

Send a message in any channel where the bot is present:

```
@reporting-bot compile 2026-06-10 2026-06-11
```

The bot will:
1. Reply with "perintah diterima, compiling reports..."
2. Scan all messages in that channel from 2026-06-10 to 2026-06-11 (GMT+7, inclusive)
3. Filter messages with image attachments and valid `id`, `sub-id`, `tanggal` format
4. Generate PDFs per `tower-id`
5. Upload the PDFs back to the channel

If no matching messages are found, the bot will reply:
```
tidak ada chat tentang laporan proyek
```

## Project Structure

```
discord-bot/
├── app/
│   ├── __init__.py
│   ├── main.py              # Bot client & message listener
│   ├── parser.py            # Command parsing & date conversion
│   ├── message_filter.py    # Message fetching & validation
│   ├── pdf_generator.py     # PDF generation with grid layout
│   └── report_service.py    # Orchestration layer
├── tests/
│   ├── __init__.py
│   ├── test_bot.py          # Unit tests for main.py
│   ├── test_parser.py       # Unit tests for parser.py
│   ├── test_message_filter.py  # Unit tests for message_filter.py
│   ├── test_pdf_generator.py  # Unit tests for pdf_generator.py
│   └── test_report_service.py # Unit tests for report_service.py
├── .env                     # Environment variables (not tracked)
├── .env.example             # Example env file
├── requirements.txt         # Python dependencies
└── README.md                # This file
```

## Run Tests

```bash
python -m pytest tests/ -v
```

## Important Notes

- **Date format**: All dates must be in `yyyy-mm-dd` format
- **Timezone**: Dates are interpreted in GMT+7 (WIB)
- **Inclusive range**: Both start and end dates are included
- **Image attachments**: Only messages with image attachments are processed
- **Message format**: Messages must contain `id:`, `sub-id:`, and `tanggal:` fields
- **Skips bot messages**: The bot ignores messages from other bots to avoid loops
- **Direct messages (DMs)**: The bot will also process DMs if it has the `message_content` intent
