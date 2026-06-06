#!/usr/bin/env bash
# Wrapper to run the seeder script, loading environment secrets automatically.
set -e

# Load environment variables from .env and .env.local
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi
if [ -f .env.local ]; then
  # Use grep and sed to safely extract and export vars (ignoring comments and handling quotes)
  while IFS= read -r line; do
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ -z "$line" ]] && continue
    # Strip quotes if present
    key=$(echo "$line" | cut -d'=' -f1)
    val=$(echo "$line" | cut -d'=' -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
    export "$key=$val"
  done < .env.local
fi

# Set default API base if not set
export LYRICSTATS_API_BASE=${LYRICSTATS_API_BASE:-"https://lyricstats-api.vercel.app"}

if [ $# -eq 0 ]; then
  echo "Usage: ./seed.sh \"Artist Name\" [--songs N]"
  echo "Example: ./seed.sh \"Jala Brat\" --songs 500"
  exit 1
fi

uv run python scripts/seed.py "$@"
