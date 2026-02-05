#!/bin/bash
# Simple script to check for new JSON files and email

OUTPUT_DIR="/home/bihac-danas/web-scraper/facebook_ready_posts"
EMAILS=("hare.de@gmail.com" "danasbihac@gmail.com")
TODAY=$(date '+%Y%m%d')

# Find new JSON files from today
NEW_FILES=()
for file in "$OUTPUT_DIR"/*"$TODAY"*.json; do
    if [ -f "$file" ] && [ $(find "$file" -mmin -240) ]; then  # Last 4 hours
        NEW_FILES+=("$(basename "$file")")
    fi
done

# Send email if new files found
if [ ${#NEW_FILES[@]} -gt 0 ]; then
    SUBJECT="📰 ${#NEW_FILES[@]} New Articles Found ($TODAY)"
    BODY="New articles found:\n\n"
    
    for file in "${NEW_FILES[@]}"; do
        BODY+="• $file\n"
    done
    
    BODY+="\nLocation: $OUTPUT_DIR\nTime: $(date)"
    
    for email in "${EMAILS[@]}"; do
        echo -e "$BODY" | mutt -s "$SUBJECT" "$email"
    done
fi
