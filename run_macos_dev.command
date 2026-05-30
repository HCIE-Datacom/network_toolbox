#!/bin/zsh
set -e

cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
  exec python3 network_toolbox.py
fi

echo "python3 not found"
read -r "?Press Enter to close..."
