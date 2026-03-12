#!/bin/bash

# Cleanup script for Bihać Scrapers System
# Removes temporary files, cache, and unused data

echo "🧹 Starting cleanup of Bihać Scrapers System..."
echo "=============================================="

# 1. Find and remove temporary Python files
echo "1. Cleaning Python temporary files..."
find /home/bihac-danas/web-scraper -name "*.pyc" -delete 2>/dev/null
find /home/bihac-danas/web-scraper -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
find /home/bihac-danas/web-scraper -name "*.py~" -delete 2>/dev/null
find /home/bihac-danas/web-scraper -name "*.py.bak" -delete 2>/dev/null
echo "   ✓ Python cache cleaned"

# 2. Clean log files (keep recent entries)
echo "2. Rotating log files..."

# Large activity logs - keep last 5000 lines
LARGE_LOGS=(
    "/home/bihac-danas/web-scraper/scraper_log.txt"
    "/home/bihac-danas/web-scraper/scraper_cron.log"
    "/home/bihac-danas/web-scraper/dashboard_access.log"
    "/home/bihac-danas/web-scraper/dashboard_activity.log"
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
    "/home/bihac-danas/web-scraper/dashboard.log"
    "/home/bihac-danas/web-scraper/email_sent.log"
    "/home/bihac-danas/web-scraper/failed_logins.log"
)

for log_file in "${SMALL_LOGS[@]}"; do
    if [ -f "$log_file" ]; then
        # Keep last 1000 lines for small logs
        tail -1000 "$log_file" > "${log_file}.tmp" && mv "${log_file}.tmp" "$log_file"
        echo "   ✓ Rotated: $(basename "$log_file")"
    fi
done

# 3. Clean old JSON files (keep last 1 day)
echo "3. Cleaning old JSON files..."
JSON_DIR="/home/bihac-danas/web-scraper/facebook_ready_posts"
if [ -d "$JSON_DIR" ]; then
    # Count before cleanup
    COUNT_BEFORE=$(find "$JSON_DIR" -name "*.json" | wc -l)

    # Remove JSON files older than 1 day
    find "$JSON_DIR" -name "*.json" -mtime +1 -delete 2>/dev/null

    # Count after cleanup
    COUNT_AFTER=$(find "$JSON_DIR" -name "*.json" | wc -l)
    REMOVED=$((COUNT_BEFORE - COUNT_AFTER))

    # FIXED: Use quotes and escape parentheses
    echo "   ✓ Removed $REMOVED old JSON files (kept $COUNT_AFTER)"
fi

# 3b. Clean old attachment files/photos (default: keep last 2 days)
echo "3b. Cleaning old attachment files..."
ATTACHMENTS_DIR="/home/bihac-danas/web-scraper/facebook_ready_posts/attachments"
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

# 4. Clean old backup files (keep last 7 days)
echo "4. Cleaning backup files..."
find /home/bihac-danas/web-scraper -name "*.bak" -mtime +7 -delete 2>/dev/null
find /home/bihac-danas/web-scraper -name "*.backup" -mtime +7 -delete 2>/dev/null
echo "   ✓ Old backup files cleaned"

# 5. Clean temporary email files
echo "5. Cleaning temporary email files..."
find /tmp -name "mutt-*" -delete 2>/dev/null
find /tmp -name "mail-*" -delete 2>/dev/null
find /home/bihac-danas/web-scraper -name "*.eml" -delete 2>/dev/null
echo "   ✓ Temporary email files cleaned"

# 6. Clean browser cache from scrapers
echo "6. Cleaning browser cache..."
find /home/bihac-danas/web-scraper -type d -name ".cache" -exec rm -rf {} + 2>/dev/null
echo "   ✓ Browser cache cleaned"

# 7. Check disk space
echo "7. Checking disk space..."
echo "   Current disk usage:"
df -h /home/bihac-danas/web-scraper | tail -1

# 8. List largest files
echo "8. Largest files in /home/bihac-danas/web-scraper:"
LARGE_FILES=$(find /home/bihac-danas/web-scraper -type f -size +10M -exec ls -lh {} + 2>/dev/null | head -10)
if [ -n "$LARGE_FILES" ]; then
    echo "$LARGE_FILES"
else
    echo "   No files larger than 10MB found"
fi

# 9. Clean empty directories
echo "9. Cleaning empty directories..."
find /home/bihac-danas/web-scraper -type d -empty -delete 2>/dev/null
echo "   ✓ Empty directories removed"

echo ""
echo "=============================================="
echo "✅ Cleanup completed!"
echo ""
echo "To automate cleanup, add to crontab:"
echo "0 2 * * * /home/bihac-danas/web-scraper/cleanup_script.sh >> /home/bihac-danas/web-scraper/cleanup.log 2>&1"
echo ""
echo "This will run cleanup daily at 2 AM"
echo "=============================================="
