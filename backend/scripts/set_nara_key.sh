#!/bin/bash
# Stores a NaraRouter key in backend/.env and verifies it.
#
#   ./backend/scripts/set_nara_key.sh
#
# The key is read without echo and never leaves this machine.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$ROOT/backend/.env"

if [ ! -f "$ENV_FILE" ]; then
  cp "$ROOT/backend/.env.example" "$ENV_FILE"
  echo "Created backend/.env from the example template."
fi

read -r -s -p "NaraRouter API key (sk-nry-...): " KEY
echo

if [ -z "$KEY" ]; then
  echo "No key entered. Nothing changed."
  exit 1
fi

if ! printf '%s' "$KEY" | grep -qE '^sk-nry-[A-Za-z0-9_-]+$'; then
  echo "That does not look like a NaraRouter key (expected sk-nry-...). Aborting."
  exit 1
fi

if grep -q '^NARA_API_KEY=' "$ENV_FILE"; then
  sed -i '' "s|^NARA_API_KEY=.*|NARA_API_KEY=$KEY|" "$ENV_FILE"
else
  printf '\nNARA_API_KEY=%s\n' "$KEY" >> "$ENV_FILE"
fi

echo "Key stored in backend/.env"
echo

cd "$ROOT/backend"
venv/bin/python scripts/check_nara.py --models
