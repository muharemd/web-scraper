#!/bin/bash

# Master Scraper Runner
# Sends email notifications when new articles are found

# Use Python from virtual environment
PYTHON="/home/bihac-danas/web-scraper/scraper-env/bin/python3"

# Configuration
SCRAPERS=(
    #"dzbinac.py"
    "vladausk.py"
    "kbbihac.py"
    "kcbihac.py"
    "rtvusk.py"
    "radiobihac.py"
    "vodovod-bihac.py"
    "usnkrajina.py"
    #"komrad-bihac.py"
    "bihac-org.py"
    #"klix_feed.py"
    "bihamk-rss.py"
    "prostornobihac.py"
    "grad-cazin.py"
    "opcina-buzim.py"
    "sanski-most.py"
    "crt_ba.py"
    "pufbih.py"
    "uino.py"
    "ussume.py"
    "zzousk.py"
    "cesteusk.py"
    #"antikorupcijausk.py"
    "pravosudje.py"
    "radiovkladusa.py"
    #"sanartv.py"
    "npuna.py"
    "fena_rss.py"
    #"oslobodjenje_feed.py"
)

EMAILS=("hare.de@gmail.com" "danasbihac@gmail.com")
LOG_FILE="/home/bihac-danas/web-scraper/scraper_log.txt"
OUTPUT_DIR="/home/bihac-danas/web-scraper/facebook_ready_posts"
EMAIL_LOG="/home/bihac-danas/web-scraper/email_sent.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Create timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
echo "============================================================" | tee -a "$LOG_FILE"
echo "🚀 BIHAC SCRAPERS MASTER RUN - $TIMESTAMP" | tee -a "$LOG_FILE"
echo "============================================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Count existing JSON files before running
COUNT_BEFORE=$(find "$OUTPUT_DIR" -name "*.json" 2>/dev/null | wc -l)
echo "📊 JSON files before: $COUNT_BEFORE" | tee -a "$LOG_FILE"

# Track results
declare -A RESULTS
TOTAL_NEW=0
NEW_FILES=()
NEW_FILES_INFO=()  # Array to store file info with URLs and original article URLs
FAILED_SCRAPERS=()

# Run each scraper
for scraper in "${SCRAPERS[@]}"; do
    echo -e "\n${BLUE}▶ Running: $scraper${NC}" | tee -a "$LOG_FILE"

    if [ ! -f "$scraper" ]; then
        echo -e "  ${RED}✗ Scraper not found${NC}" | tee -a "$LOG_FILE"
        FAILED_SCRAPERS+=("$scraper")
        continue
    fi

    # Run the scraper with virtual environment Python
    START_TIME=$(date +%s)
    $PYTHON "$scraper" 2>&1 | tee -a "$LOG_FILE"
    SCRAPER_EXIT=${PIPESTATUS[0]}
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    if [ $SCRAPER_EXIT -eq 0 ]; then
        RESULTS["$scraper"]="success"
        echo -e "  ${GREEN}✓ Completed successfully (${DURATION}s)${NC}" | tee -a "$LOG_FILE"
    else
        RESULTS["$scraper"]="failed"
        FAILED_SCRAPERS+=("$scraper")
        echo -e "  ${RED}✗ Failed with exit code $SCRAPER_EXIT (${DURATION}s)${NC}" | tee -a "$LOG_FILE"
    fi
done

# Count JSON files after running
COUNT_AFTER=$(find "$OUTPUT_DIR" -name "*.json" 2>/dev/null | wc -l)
NEW_COUNT=$((COUNT_AFTER - COUNT_BEFORE))
echo -e "\n${GREEN}📊 RESUME:${NC}" | tee -a "$LOG_FILE"
echo "  JSON files before: $COUNT_BEFORE" | tee -a "$LOG_FILE"
echo "  JSON files after:  $COUNT_AFTER" | tee -a "$LOG_FILE"
echo -e "  ${GREEN}New files created: $NEW_COUNT${NC}" | tee -a "$LOG_FILE"

# Find new JSON files created in this run
echo -e "\n${BLUE}🔍 Looking for new JSON files...${NC}" | tee -a "$LOG_FILE"
TODAY=$(date '+%Y%m%d')
LAST_15_MIN=$(date -d '15 minutes ago' +%s)

# Get server IP for dashboard link only
SERVER_IP=$(hostname -I | awk '{print $1}')
if [ -z "$SERVER_IP" ] || [ "$SERVER_IP" = "127.0.0.1" ]; then
    SERVER_IP=$(ip route get 1 2>/dev/null | awk '{print $7; exit}')
fi
if [ -z "$SERVER_IP" ]; then
    SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || echo "localhost")
fi

BASE_URL="http://$SERVER_IP:8080"

# More reliable way to find new files - using Python for all JSON parsing
for file in "$OUTPUT_DIR"/*.json; do
    if [ -f "$file" ]; then
        FILENAME=$(basename "$file")
        FILE_MOD_TIME=$(stat -c %Y "$file" 2>/dev/null || stat -f %m "$file" 2>/dev/null)

        # Check if file was modified in the last 15 minutes
        if [ -n "$FILE_MOD_TIME" ] && [ "$FILE_MOD_TIME" -ge "$LAST_15_MIN" ]; then
            NEW_FILES+=("$FILENAME")
            
            # Use Python to properly parse JSON (reliable method)
            JSON_INFO=$($PYTHON -c "
import json, sys, os
try:
    with open('$file', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Get URL - try multiple field names
    url_fields = ['url', 'link', 'original_url', 'article_url', 'source_url', 'page_url']
    url = None
    for field in url_fields:
        if field in data and data[field]:
            url = str(data[field])
            break
    
    # Get title - try multiple field names
    title_fields = ['title', 'name', 'heading', 'headline']
    title = None
    for field in title_fields:
        if field in data and data[field]:
            title = str(data[field])
            break
    
    # Clean title - remove newlines and extra spaces
    if title:
        title = ' '.join(title.split())
    else:
        title = '$FILENAME'
    
    # Output in a parseable format
    print(f'TITLE:{title}')
    if url:
        print(f'URL:{url}')
    else:
        print('URL:NOT_FOUND')
        
except Exception as e:
    # If JSON parsing fails, just use filename
    print(f'TITLE:$FILENAME')
    print('URL:NOT_FOUND')
")
            
            # Parse the Python output
            TITLE="$FILENAME"  # Default
            ORIGINAL_URL=""
            
            while IFS= read -r line; do
                if [[ "$line" == TITLE:* ]]; then
                    TITLE="${line#TITLE:}"
                elif [[ "$line" == URL:* ]]; then
                    ORIGINAL_URL="${line#URL:}"
                fi
            done <<< "$JSON_INFO"
            
            # Clean URL value
            if [ "$ORIGINAL_URL" = "NOT_FOUND" ] || [ "$ORIGINAL_URL" = "null" ] || [ -z "$ORIGINAL_URL" ]; then
                ORIGINAL_URL=""
            fi

            # Store file info
            NEW_FILES_INFO+=("{\"filename\":\"$FILENAME\",\"title\":\"$TITLE\",\"url\":\"$ORIGINAL_URL\"}")

            echo "  Found new: $FILENAME" | tee -a "$LOG_FILE"
            echo "    Title: $TITLE" | tee -a "$LOG_FILE"
            if [ -n "$ORIGINAL_URL" ] && [ "$ORIGINAL_URL" != "" ]; then
                echo "    Original URL: $ORIGINAL_URL" | tee -a "$LOG_FILE"
            else
                echo "    ⚠️  No original URL found in JSON" | tee -a "$LOG_FILE"
            fi
        fi
    fi
done

# Create detailed log entry
LOG_ENTRY="$TIMESTAMP | Before: $COUNT_BEFORE | After: $COUNT_AFTER | New: $NEW_COUNT | Files: ${NEW_FILES[*]} | Failed: ${#FAILED_SCRAPERS[@]} scrapers"
echo "$LOG_ENTRY" >> "$LOG_FILE"

# Send email notification if new files found
if [ ${#NEW_FILES[@]} -gt 0 ]; then
    echo -e "\n${YELLOW}📧 Sending email notifications...${NC}" | tee -a "$LOG_FILE"

    DASHBOARD_URL="http://$SERVER_IP:8080"
    echo "  Dashboard URL: $DASHBOARD_URL" | tee -a "$LOG_FILE"

    EMAIL_SUBJECT="🚀 $NEW_COUNT New Articles Found - Bihać Scrapers ($TODAY)"

    # Create HTML email content
    EMAIL_HTML=$(cat << HTMLEND
<html>
    <body style='font-family: Arial, sans-serif; line-height: 1.6;'>
        <div style='max-width: 700px; margin: 0 auto; padding: 20px; background-color: #f9f9f9;'>
            <h1 style='color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px;'>
                🚀 Bihać Scrapers Report - $TODAY
            </h1>

            <div style='background-color: white; padding: 20px; border-radius: 5px; margin: 20px 0; box-shadow: 0 2px 5px rgba(0,0,0,0.1);'>
                <h2 style='color: #27ae60;'>📊 Summary</h2>
                <ul style='list-style-type: none; padding-left: 0;'>
                    <li style='margin-bottom: 8px;'><strong style='color: #2c3e50;'>New Articles Found:</strong> <span style='color: #27ae60; font-weight: bold;'>$NEW_COUNT</span></li>
                    <li style='margin-bottom: 8px;'><strong style='color: #2c3e50;'>Total Files Now:</strong> $COUNT_AFTER</li>
                    <li style='margin-bottom: 8px;'><strong style='color: #2c3e50;'>Run Time:</strong> $TIMESTAMP</li>
                    <li style='margin-bottom: 8px;'><strong style='color: #2c3e50;'>Dashboard:</strong> <a href='$DASHBOARD_URL' style='color: #3498db; text-decoration: none;'>$DASHBOARD_URL</a></li>
                </ul>

                <h2 style='color: #2980b9; margin-top: 25px;'>📁 New Articles (with original links)</h2>
                <div style='background-color: #f8f9fa; padding: 15px; border-radius: 3px; border-left: 4px solid #3498db;'>
HTMLEND
)

    # Add each new file
    for file_info in "${NEW_FILES_INFO[@]}"; do
        FILENAME=$(echo "$file_info" | grep -o '"filename":"[^"]*"' | cut -d'"' -f4)
        TITLE=$(echo "$file_info" | grep -o '"title":"[^"]*"' | cut -d'"' -f4)
        ORIGINAL_URL=$(echo "$file_info" | grep -o '"url":"[^"]*"' | cut -d'"' -f4)
        
        # Clean up title - handle escaped characters
        CLEAN_TITLE=$(echo "$TITLE" | sed 's/\\//g; s/&amp;/\&/g; s/&lt;/</g; s/&gt;/>/g; s/&quot;/"/g; s/&#39;/'"'"'/g')
        
        if [ -n "$ORIGINAL_URL" ] && [ "$ORIGINAL_URL" != "null" ] && [ "$ORIGINAL_URL" != "" ]; then
            EMAIL_HTML="${EMAIL_HTML}
                    <div style='margin-bottom: 12px; padding: 10px; background-color: white; border: 1px solid #e1e1e1; border-radius: 3px;'>
                        <div style='font-family: Arial, sans-serif; font-size: 14px; color: #2c3e50; margin-bottom: 5px; font-weight: bold;'>
                            📰 $CLEAN_TITLE
                        </div>
                        <div style='font-family: monospace; font-size: 11px; color: #7f8c8d; margin-bottom: 5px;'>
                            📄 File: $FILENAME
                        </div>
                        <div style='font-size: 12px;'>
                            🔗 <a href='$ORIGINAL_URL' style='color: #3498db; text-decoration: none; word-break: break-all;'>
                                $ORIGINAL_URL
                            </a>
                        </div>
                    </div>"
        else
            EMAIL_HTML="${EMAIL_HTML}
                    <div style='margin-bottom: 12px; padding: 10px; background-color: white; border: 1px solid #e1e1e1; border-radius: 3px;'>
                        <div style='font-family: Arial, sans-serif; font-size: 14px; color: #2c3e50; margin-bottom: 5px; font-weight: bold;'>
                            📰 $CLEAN_TITLE
                        </div>
                        <div style='font-family: monospace; font-size: 11px; color: #7f8c8d; margin-bottom: 5px;'>
                            📄 File: $FILENAME
                        </div>
                        <div style='font-size: 12px; color: #e74c3c;'>
                            ⚠️ No original URL found in JSON file
                        </div>
                    </div>"
        fi
    done

    # Add the rest of the HTML
    EMAIL_HTML="${EMAIL_HTML}
                </div>

                <h2 style='color: #8e44ad; margin-top: 25px;'>📁 Dashboard Access</h2>
                <p style='background-color: #f8f9fa; padding: 10px; border-radius: 3px;'>
                    <a href='${DASHBOARD_URL}'
                       style='color: #3498db; text-decoration: none; font-weight: bold;'>
                        📊 View All JSON Files in Dashboard
                    </a>
                </p>

                <h2 style='color: #e74c3c; margin-top: 25px;'>⚠️ Issues</h2>
                <div style='background-color: #fff5f5; padding: 15px; border-radius: 3px; border-left: 4px solid #e74c3c;'>
                    <p><strong>Failed scrapers:</strong> ${#FAILED_SCRAPERS[@]}</p>"

    if [ ${#FAILED_SCRAPERS[@]} -gt 0 ]; then
        EMAIL_HTML="${EMAIL_HTML}<ul style='color: #c0392b;'>"
        for scraper in "${FAILED_SCRAPERS[@]}"; do
            EMAIL_HTML="${EMAIL_HTML}<li>$scraper</li>"
        done
        EMAIL_HTML="${EMAIL_HTML}</ul>"
    else
        EMAIL_HTML="${EMAIL_HTML}<p style='color: #27ae60;'>✅ None - All scrapers completed successfully!</p>"
    fi

    EMAIL_HTML="${EMAIL_HTML}
                </div>
            </div>

            <div style='margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; color: #7f8c8d; font-size: 12px;'>
                <p>This is an automated email from Bihać Scrapers system.</p>
                <p><strong>Server:</strong> $SERVER_IP | <strong>Time:</strong> $TIMESTAMP</p>
                <p><strong>Files location:</strong> $OUTPUT_DIR/</p>
            </div>
        </div>
    </body>
</html>"

    # Create a temporary file for email content
    TEMP_EMAIL=$(mktemp)
    echo "$EMAIL_HTML" > "$TEMP_EMAIL"

    # Try sending email
    EMAIL_SENT=false

    if command -v mail &> /dev/null; then
        echo "  Trying to send with 'mail' command..." | tee -a "$LOG_FILE"
        for email in "${EMAILS[@]}"; do
            echo "$EMAIL_HTML" | mail -s "$EMAIL_SUBJECT" -a "Content-Type: text/html" "$email" 2>&1 | tee -a "$LOG_FILE"
            if [ $? -eq 0 ]; then
                EMAIL_SENT=true
                echo "  ✓ Email sent to $email" | tee -a "$LOG_FILE"
            else
                echo "  ✗ Failed to send to $email with mail command" | tee -a "$LOG_FILE"
            fi
        done
    fi

    # Method 2: Using mutt (keep only if mutt is installed)
    if ! $EMAIL_SENT && command -v mutt &> /dev/null; then
        echo "  Trying to send with 'mutt'..." | tee -a "$LOG_FILE"
        for email in "${EMAILS[@]}"; do
            echo "$EMAIL_HTML" | mutt -e "set content_type=text/html" -s "$EMAIL_SUBJECT" "$email" 2>&1 | tee -a "$LOG_FILE"
            if [ $? -eq 0 ]; then
                EMAIL_SENT=true
                echo "  ✓ Email sent to $email with mutt" | tee -a "$LOG_FILE"
            fi
        done
    fi

    # Log email attempt
    if $EMAIL_SENT; then
        echo "$TIMESTAMP - Email sent to ${EMAILS[*]} - New: $NEW_COUNT files" >> "$EMAIL_LOG"
        echo -e "  ${GREEN}✓ Email notification sent successfully${NC}" | tee -a "$LOG_FILE"
    else
        echo "$TIMESTAMP - Email FAILED to send - Check email configuration" >> "$EMAIL_LOG"
        echo -e "  ${RED}✗ Could not send email - no mail client found${NC}" | tee -a "$LOG_FILE"
        echo "  Install mail or mutt: sudo apt-get install mailutils" | tee -a "$LOG_FILE"
    fi

    # Clean up temp file
    rm -f "$TEMP_EMAIL"

else
    echo -e "\n${YELLOW}ℹ️  No new articles found, skipping email${NC}" | tee -a "$LOG_FILE"
fi

echo -e "\n${GREEN}============================================================${NC}" | tee -a "$LOG_FILE"
echo -e "${GREEN}✅ ALL SCRAPERS COMPLETED${NC}" | tee -a "$LOG_FILE"
echo -e "${GREEN}============================================================${NC}" | tee -a "$LOG_FILE"