#!/bin/bash

# Cleanup script for Bihać Scrapers System
# Removes temporary files, cache, and unused data
#
# IMPORTANT: This script NEVER touches the Python virtualenv
# (scraper-env / .venv / venv) or other critical/protected directories.

set -u  # error on undefined variables (safer than set -e for a cleanup script)

BASE_DIR="/home/bihac-danas/web-scraper"

echo "🧹 Starting cleanup of Bihać Scrapers System..."
echo "=============================================="

# ------------------------------------------------------------------
# Protected paths — NEVER traversed for deletion.
# These will be pruned from every recursive find below.
# ------------------------------------------------------------------
PROTECTED_DIRS=(
    "scraper-env"     # Python virtualenv (site-packages, .so, bin, etc.)
    ".venv"
    "venv"
    "env"
    ".git"
    "node_modules"
    "site-packages"
)

# Run a find command with protected dirs excluded, deleting matching files.
# Usage: safe_find_delete <extra find predicates...>
# Deletes files that match the predicates, skipping PROTECTED_DIRS entirely.
safe_find_delete() {
    find "$BASE_DIR" \
        \( -name "scraper-env" -o -name ".venv" -o -name "venv" -o -name "env" \) -prune -o \
        \( -name ".git" -o -name "node_modules" -o -name "site-packages" \) -prune -o \
        \( "$@" \) -type f -print -delete 2>/dev/null
}

# --------------------------------------------------------------
# 1. Remove temporary Python files (OUTSIDE the virtualenv)
# --------------------------------------------------------------
echo "1. Cleaning Python temporary files..."
safe_find_delete -name "*.pyc"
safe_find_delete -name "*.py~"
safe_find_delete -name "*.py.bak"

# Remove __pycache__ dirs, but never inside the venv / site-packages
find "$BASE_DIR" \
    \( -name "scraper-env" -o -name ".venv" -o -name "venv" -o -name "env" \) -prune -o \
    \( -name ".git" -o -name "node_modules" -o -name "site-packages" \) -prune -o \
    -type d -name "__pycache__" -print -exec rm -rf {} + 2>/dev/null
echo "   ✓ Python cache cleaned (venv preserved)"

# --------------------------------------------------------------
# 2. Clean log files (keep recent entries)
# --------------------------------------------------------------
echo "2. Rotating log files..."

# Large activity logs - keep last 5000 lines
LARGE_LOGS=(
    "$BASE_DIR/scraper_log"
    "$BASE_DIR/scraper_cron.log"
    "$BASE_DIR/dashboard_access.log"
    "$BASE_DIR/dashboard_activity.log"
)

for log_file in "${LARGE_LOGS[@]}"; do
    if [ -f "$log_file" ]; then
        # Keep last 5000 lines for large logs
        tail -5000 "$log_file" > "${log_file}.tmp" && mv "${log_file}.tmp" "$log_file"
        echo "   ✓ Rotated: $(basename "$log_file")"
    fi
done

# Small logs - keep last 1000 lines
SMALL_LOGS=(
    "$BASE_DIR/dashboard.log"
    "$BASE_DIR/email_sent.log"
    "$BASE_DIR/failed_logins.log"
)

for log_file in "${SMALL_LOGS[@]}"; do
    if [ -f "$log_file" ]; then
        # Keep last 1000 lines for small logs
        tail -1000 "$log_file" > "${log_file}.tmp" && mv "${log_file}.tmp" "$log_file"
        echo "   ✓ Rotated: $(basename "$log_file")"
    fi
done

# --------------------------------------------------------------
# 3. Clean old JSON files (keep last N days, default 1)
# --------------------------------------------------------------
echo "3. Cleaning old JSON files..."
JSON_DIR="$BASE_DIR/facebook_ready_posts"
JSON_RETENTION_DAYS="${JSON_RETENTION_DAYS:-1}"
# Guard: retention must be a positive integer >= 1
case "$JSON_RETENTION_DAYS" in
    ''|*[!0-9]*) JSON_RETENTION_DAYS=1 ;;
esac
if [ "$JSON_RETENTION_DAYS" -lt 1 ]; then
    JSON_RETENTION_DAYS=1
fi
if [ -d "$JSON_DIR" ]; then
    COUNT_BEFORE=$(find "$JSON_DIR" -name "*.json" | wc -l)

    # Remove JSON files older than JSON_RETENTION_DAYS days.
    # (-mtime +N is exclusive: +0 => older than ~24h, matching "1 day".)
    find "$JSON_DIR" -name "*.json" -mtime +"$((JSON_RETENTION_DAYS - 1))" -delete 2>/dev/null

    COUNT_AFTER=$(find "$JSON_DIR" -name "*.json" | wc -l)
    REMOVED=$((COUNT_BEFORE - COUNT_AFTER))

    echo "   ✓ Removed $REMOVED old JSON files (kept $COUNT_AFTER, retention ${JSON_RETENTION_DAYS} days)"
fi

# --------------------------------------------------------------
# 3b. Clean old attachment files/photos (default: keep last 2 days)
# --------------------------------------------------------------
echo "3b. Cleaning old attachment files..."
ATTACHMENTS_DIR="$BASE_DIR/facebook_ready_posts/attachments"
ATTACHMENT_RETENTION_DAYS="${ATTACHMENT_RETENTION_DAYS:-2}"
if [ -d "$ATTACHMENTS_DIR" ]; then
    COUNT_ATTACH_BEFORE=$(find "$ATTACHMENTS_DIR" -type f | wc -l)

    # Remove attachment files older than ATTACHMENT_RETENTION_DAYS days.
    find "$ATTACHMENTS_DIR" -type f -mtime +"$ATTACHMENT_RETENTION_DAYS" -delete 2>/dev/null

    COUNT_ATTACH_AFTER=$(find "$ATTACHMENTS_DIR" -type f | wc -l)
    REMOVED_ATTACH=$((COUNT_ATTACH_BEFORE - COUNT_ATTACH_AFTER))

    # Clean up empty attachment subdirectories after file deletion.
    find "$ATTACHMENTS_DIR" -type d -empty -delete 2>/dev/null

    echo "   ✓ Removed $REMOVED_ATTACH old attachment files (kept $COUNT_ATTACH_AFTER, retention ${ATTACHMENT_RETENTION_DAYS} days)"
else
    echo "   ✓ No attachments directory found"
fi

# --------------------------------------------------------------
# 4. Clean old backup files (keep last 7 days) — outside venv
# --------------------------------------------------------------
echo "4. Cleaning backup files..."
safe_find_delete -name "*.bak" -mtime +7
safe_find_delete -name "*.backup" -mtime +7
echo "   ✓ Old backup files cleaned (venv preserved)"

# --------------------------------------------------------------
# 5. Clean temporary email files
# --------------------------------------------------------------
echo "5. Cleaning temporary email files..."
find /tmp -name "mutt-*" -delete 2>/dev/null
find /tmp -name "mail-*" -delete 2>/dev/null
safe_find_delete -name "*.eml"
echo "   ✓ Temporary email files cleaned"

# --------------------------------------------------------------
# 6. Clean browser cache from scrapers (outside venv)
# --------------------------------------------------------------
echo "6. Cleaning browser cache..."
find "$BASE_DIR" \
    \( -name "scraper-env" -o -name ".venv" -o -name "venv" -o -name "env" \) -prune -o \
    \( -name ".git" -o -name "node_modules" -o -name "site-packages" \) -prune -o \
    -type d -name ".cache" -print -exec rm -rf {} + 2>/dev/null
echo "   ✓ Browser cache cleaned (venv preserved)"

# --------------------------------------------------------------
# 7. Check disk space
# --------------------------------------------------------------
echo "7. Checking disk space..."
echo "   Current disk usage:"
df -h "$BASE_DIR" | tail -1

# --------------------------------------------------------------
# 8. List largest files (informational only — never deletes anything)
# --------------------------------------------------------------
echo "8. Largest files in $BASE_DIR:"
LARGE_FILES=$(find "$BASE_DIR" -type f -size +10M -exec ls -lh {} + 2>/dev/null | head -10)
if [ -n "$LARGE_FILES" ]; then
    echo "$LARGE_FILES"
else
    echo "   No files larger than 10MB found"
fi

# --------------------------------------------------------------
# 9. Clean empty directories (outside venv)
# --------------------------------------------------------------
echo "9. Cleaning empty directories..."
find "$BASE_DIR" \
    \( -name "scraper-env" -o -name ".venv" -o -name "venv" -o -name "env" \) -prune -o \
    \( -name ".git" -o -name "node_modules" -o -name "site-packages" \) -prune -o \
    -type d -empty -print -delete 2>/dev/null
echo "   ✓ Empty directories removed (venv preserved)"

echo ""
echo "=============================================="
echo "✅ Cleanup completed!"
echo ""
echo "Protected from deletion:"
echo "   scraper-env, .venv, venv, env, .git, node_modules, site-packages"
echo ""
echo "To automate cleanup, add to crontab:"
echo "0 2 * * * $BASE_DIR/cleanup_script.sh >> $BASE_DIR/cleanup.log 2>&1"
echo ""
echo "This will run cleanup daily at 2 AM"
echo "=============================================="
