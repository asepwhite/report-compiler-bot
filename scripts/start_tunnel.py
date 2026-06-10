#!/usr/bin/env python3
"""
Automation script to start ngrok and register Telegram webhook.

Usage:
    python scripts/start_tunnel.py

This script will:
1. Start ngrok to expose localhost:8000
2. Capture the ngrok URL via the API
3. Register the webhook with Telegram
4. Keep ngrok running
5. Clean up on exit (optionally delete the webhook)
"""

import subprocess
import time
import os
import sys
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
LOCAL_PORT = os.getenv("LOCAL_PORT", "8000")

if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_bot_token_here":
    print("❌ Error: TELEGRAM_BOT_TOKEN not set in .env file")
    print("Please set it in your .env file and try again.")
    sys.exit(1)


def register_webhook(tunnel_url: str) -> bool:
    """Register the webhook URL with Telegram."""
    webhook_url = f"{tunnel_url}/webhook/{TELEGRAM_BOT_TOKEN}"
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
    
    print(f"\n📡 Registering webhook: {webhook_url}")
    
    try:
        import requests
        response = requests.post(api_url, data={"url": webhook_url})
        result = response.json()
        
        if result.get("ok"):
            print("✅ Webhook registered successfully!")
            print(f"📨 Telegram will now send messages to: {webhook_url}")
            return True
        else:
            print(f"❌ Failed to register webhook: {result.get('description', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ Error registering webhook: {e}")
        print(f"\nYou can manually register it with:")
        print(f"curl -X POST \"{api_url}\" -d \"url={webhook_url}\"")
        return False


def get_ngrok_tunnel_url() -> str:
    """Get the ngrok tunnel URL from the API."""
    import requests
    max_retries = 15
    
    for i in range(max_retries):
        try:
            response = requests.get("http://127.0.0.1:4040/api/tunnels")
            if response.status_code == 200:
                data = response.json()
                tunnels = data.get("tunnels", [])
                if tunnels:
                    # Get the HTTPS tunnel URL
                    for tunnel in tunnels:
                        if tunnel.get("public_url", "").startswith("https://"):
                            return tunnel["public_url"]
                    # Fallback to first tunnel
                    return tunnels[0]["public_url"]
        except requests.exceptions.ConnectionError:
            pass
        
        print(f"⏳ Waiting for ngrok tunnel to be ready... ({i+1}/{max_retries})")
        time.sleep(1)
    
    return None


def start_tunnel():
    """Start ngrok tunnel and capture the URL."""
    print("🚀 Starting ngrok...")
    print(f"🔗 Exposing http://localhost:{LOCAL_PORT}")
    print("⏳ Waiting for tunnel URL...\n")
    
    # Start ngrok process
    cmd = ["ngrok", "http", LOCAL_PORT, "--log", "stdout"]
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    
    tunnel_url = None
    
    try:
        # Give ngrok a moment to start
        time.sleep(3)
        
        # Get the tunnel URL from the ngrok API
        tunnel_url = get_ngrok_tunnel_url()
        
        if tunnel_url:
            print(f"\n🎉 Tunnel URL captured: {tunnel_url}")
            
            # Register webhook
            if register_webhook(tunnel_url):
                print("\n" + "=" * 60)
                print("✅ Setup complete!")
                print("📝 Your webhook is ready to receive messages.")
                print("📱 Send a message to your bot in Telegram.")
                print("=" * 60)
            else:
                print("\n⚠️  Webhook registration failed, but tunnel is running.")
                print("   You can manually register it later.")
        else:
            print("\n❌ Failed to capture tunnel URL from ngrok API")
            print("   Check if ngrok is running properly.")
        
        if tunnel_url:
            print("\n🟢 Tunnel is running. Press Ctrl+C to stop.\n")
            # Keep the process running
            try:
                while True:
                    line = process.stdout.readline()
                    if line:
                        print(f"[ngrok] {line.strip()}")
                    else:
                        time.sleep(0.1)
            except KeyboardInterrupt:
                print("\n\n🛑 Stopping ngrok...")
        else:
            print("\n❌ Failed to capture tunnel URL")
            
    finally:
        # Clean up process
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        
        print("👋 Tunnel stopped.")
        
        # Optionally delete webhook
        print("\n🧹 Do you want to delete the webhook from Telegram? (y/N): ", end="")
        try:
            response = input().strip().lower()
            if response == 'y':
                delete_webhook()
        except (EOFError, KeyboardInterrupt):
            pass


def delete_webhook():
    """Delete the webhook from Telegram."""
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook"
    try:
        import requests
        response = requests.post(api_url)
        result = response.json()
        if result.get("ok"):
            print("✅ Webhook deleted successfully.")
        else:
            print(f"❌ Failed to delete webhook: {result.get('description', 'Unknown error')}")
    except Exception as e:
        print(f"❌ Error: {e}")


def check_ngrok():
    """Check if ngrok is installed."""
    try:
        subprocess.run(["ngrok", "version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("🤖 Telegram Bot Webhook Setup")
    print("=" * 60)
    
    # Check if ngrok is installed
    if not check_ngrok():
        print("❌ Error: ngrok is not installed.")
        print("\nPlease install it first:")
        print("  macOS:    brew install ngrok")
        print("  Linux:    curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null && echo \"deb https://ngrok-agent.s3.amazonaws.com buster main\" | sudo tee /etc/apt/sources.list.d/ngrok.list && sudo apt update && sudo apt install ngrok")
        print("  Windows:  Download from https://ngrok.com/download")
        print("\nThen sign up at https://ngrok.com and run:")
        print("  ngrok config add-authtoken YOUR_AUTHTOKEN")
        sys.exit(1)
    
    # Check if requests is installed
    try:
        import requests
    except ImportError:
        print("❌ Error: requests library not installed.")
        print("Run: pip install requests")
        sys.exit(1)
    
    # Start the tunnel
    start_tunnel()
