import os
import json
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from .schemas import Update

# Load environment variables from .env file
load_dotenv()

app = FastAPI(
    title="Telegram Webhook Receiver",
    description="Minimal FastAPI server to receive Telegram bot messages via webhook.",
    version="1.0.0",
)

# Load token from environment
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")


@app.post("/webhook/{token}")
async def receive_webhook(token: str, update: Update):
    """
    Receive a Telegram webhook update.
    
    - Validates the token in the URL path
    - Prints the payload as pretty-printed JSON
    - Returns 200 OK so Telegram knows it was received
    """
    # Verify token
    if not TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="Server not configured with TELEGRAM_BOT_TOKEN")
    
    if token != TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid bot token")
    
    # Pretty-print the payload
    payload = update.model_dump(mode="json", exclude_none=True)
    print("=" * 60)
    print(f"[WEBHOOK RECEIVED] {datetime.now().isoformat()}")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print("=" * 60)
    
    return {"status": "ok"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/")
async def root():
    """Info endpoint."""
    return {
        "service": "Telegram Webhook Receiver",
        "version": "1.0.0",
        "webhook_url": f"/webhook/<TELEGRAM_BOT_TOKEN>",
    }
