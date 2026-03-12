#!/bin/bash
set -euo pipefail

BASE_DIR="/home/bihac-danas/web-scraper"
CONFIG_FILE="$BASE_DIR/.apify_config"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Config file not found at $CONFIG_FILE"
    echo "Create it from .apify_config.example and set APIFY_TOKEN."
    exit 1
fi

# Export variables from local hidden config
set -a
# shellcheck disable=SC1090
source "$CONFIG_FILE"
set +a

if [ -z "${APIFY_TOKEN:-}" ]; then
    echo "ERROR: APIFY_TOKEN not set in $CONFIG_FILE"
    exit 1
fi

cd "$BASE_DIR"
"$PYTHON_BIN" "$BASE_DIR/apify_facebook_import.py"
