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

sanitize_apify_output() {
    # Redact token query values when forwarding API error output to logs.
    sed -E 's/(token=)[^&[:space:]]+/\1***REDACTED***/g'
}

if APIFY_OUTPUT=$("$PYTHON_BIN" "$BASE_DIR/apify_facebook_import.py" 2>&1); then
    if [ -n "$APIFY_OUTPUT" ]; then
        printf '%s\n' "$APIFY_OUTPUT" | sanitize_apify_output
    fi
    exit 0
fi

APIFY_EXIT=$?

if printf '%s\n' "$APIFY_OUTPUT" | grep -qi "402 Client Error: Payment Required"; then
    echo "WARN: Apify API returned HTTP 402 (Payment Required). Skipping Facebook import for this run."
    exit 0
fi

printf '%s\n' "$APIFY_OUTPUT" | sanitize_apify_output >&2
exit "$APIFY_EXIT"
