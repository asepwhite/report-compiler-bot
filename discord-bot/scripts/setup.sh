#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV="$BOT_DIR/.venv"

python3 -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install --upgrade pip
pip install -r "$BOT_DIR/requirements.txt"

echo "✅ Setup complete. Run: ./scripts/start.sh"
