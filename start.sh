#!/usr/bin/env bash
#
# Aptitude launcher (Linux / macOS).
#
# Creates a local virtual environment on first run, installs Aptitude into it,
# then runs the CLI. Any arguments you pass are forwarded to `aptitude`.
#
# Examples:
#   ./start.sh                     # show help
#   ./start.sh providers           # list providers and which have credentials
#   ./start.sh create -p "Build a GDPR privacy-policy skill" -i law.pdf --provider ollama
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
venv="$root/.venv"
python="$venv/bin/python"

if [ ! -x "$python" ]; then
  echo "Setting up Aptitude (first run)..."
  python3 -m venv "$venv"
  "$python" -m pip install --upgrade pip
  "$python" -m pip install -e "$root"
fi

if [ "$#" -eq 0 ]; then
  exec "$python" -m aptitude --help
else
  exec "$python" -m aptitude "$@"
fi
