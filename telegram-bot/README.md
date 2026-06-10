# Telegram Webhook Receiver

A minimal FastAPI server that receives Telegram bot messages via webhook and prints the payload.

## Setup

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and add your TELEGRAM_BOT_TOKEN
   ```

3. **Run the server**
   ```bash
   uvicorn app.main:app --reload
   ```
   The server will start on `http://localhost:8000`.

## Local Testing (without Telegram)

Test the webhook endpoint with `curl` using a sample payload:

```bash
curl -X POST http://localhost:8000/webhook/YOUR_BOT_TOKEN \
  -H "Content-Type: application/json" \
  -d '{
    "update_id": 123456789,
    "message": {
      "message_id": 1,
      "date": 1700000000,
      "from": {
        "id": 987654321,
        "is_bot": false,
        "first_name": "Test",
        "username": "testuser"
      },
      "chat": {
        "id": 987654321,
        "type": "private",
        "first_name": "Test",
        "username": "testuser"
      },
      "text": "Hello bot!"
    }
  }'
```

You should see the pretty-printed JSON payload in the server console.

## Connect with Telegram (Webhook)

### Option 1: Automated (Recommended)

Use the provided automation script that handles everything:

```bash
python scripts/start_tunnel.py
```

This script will:
1. Start ngrok to expose your local server
2. Capture the ngrok URL
3. Register the webhook with Telegram automatically
4. Keep ngrok running
5. Clean up on exit (optionally delete the webhook)

**Prerequisites:**
- Install `ngrok`:
  ```bash
  # macOS
  brew install ngrok
  
  # Linux
  # Download from: https://ngrok.com/download
  
  # Windows
  # Download from: https://ngrok.com/download
  ```

- Sign up for a free ngrok account at https://ngrok.com and get your authtoken
- Configure your authtoken:
  ```bash
  ngrok config add-authtoken YOUR_AUTHTOKEN
  ```

### Option 2: Manual

#### 1. Expose your local server

Use **ngrok** (recommended):

```bash
ngrok http 8000
```

Copy the HTTPS URL (e.g., `https://abc123.ngrok-free.app`).

> **Note:** Free ngrok URLs are random and expire after a few hours. You need to re-register the webhook each time you restart ngrok.

#### 2. Register the webhook with Telegram

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -d "url=https://abc123.ngrok-free.app/webhook/<YOUR_BOT_TOKEN>"
```

> **Note:** Re-registering the webhook **automatically replaces** the old one. Telegram only keeps one webhook URL per bot.

#### 3. Test

Send a message to your bot in Telegram. The payload will be printed in your server console.

#### 4. Remove webhook (when done)

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/deleteWebhook"
```

## Important Notes

- **Random Subdomains:** Each time you restart `ngrok http 8000`, you get a **new random URL**. You must **re-register the webhook** with the new URL.
- **Webhook Replacement:** Calling `setWebhook` again with a new URL **overwrites** the previous registration. You don't need to manually delete the old one.
- **Security:** The webhook endpoint validates the token in the URL path (`/webhook/{token}`). Invalid tokens return `401 Unauthorized`.
- **Response:** The server returns `200 OK` for all valid requests so Telegram knows the message was received.
- **No outgoing calls:** This is a strictly print-only receiver — no outgoing Telegram API calls are made.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/webhook/{token}` | Receives Telegram updates |
| `GET` | `/health` | Health check |
| `GET` | `/` | Service info |

## Project Structure

```
telegram-bot/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app & webhook endpoint
│   └── schemas.py       # Pydantic models for Telegram Update
├── scripts/
│   └── start_tunnel.py  # Automation script for tunnel + webhook setup
├── .env                 # Environment variables
├── .env.example         # Example env file
├── requirements.txt     # Python dependencies
└── README.md            # This file
```

## Troubleshooting

**Server not receiving messages?**
- Check if ngrok is running: `ngrok http 8000`
- Verify the webhook URL is registered: `curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo`
- Make sure the token in the URL matches your `.env` file

**Want a fixed URL?**
Sign up for a paid ngrok plan or deploy to a hosting service with a permanent domain.

## Alternative: Cloudflare Tunnel

If you prefer, you can use **Cloudflare Tunnel** (`cloudflared`) instead of ngrok:

```bash
cloudflared tunnel --url http://localhost:8000
```

However, quick tunnels can be unreliable on some networks. Use a named tunnel with a Cloudflare account for better reliability.
