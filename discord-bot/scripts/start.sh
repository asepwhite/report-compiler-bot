#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV="$BOT_DIR/.venv"

if [[ ! -d "$VENV" ]]; then
  echo "❌ .venv not found. Run: ./scripts/setup.sh" >&2
  exit 1
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"
cd "$BOT_DIR"
exec python app/main.py
