#!/bin/bash
# Facebook Post Preview - FIXED VERSION
# Sends HTML email preview of new posts

# Configuration
READY_DIR="facebook_ready_posts"
POSTED_DIR="facebook_posted"
LOG_FILE="preview_posts.log"
EMAIL_RECIPIENTS=("hare.de@gmail.com" "danasbihac@gmail.com")

# Colors for console
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Create directories if needed
mkdir -p "$READY_DIR"
mkdir -p "$POSTED_DIR"

log_message() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

# Get already posted files
get_posted_files() {
    local posted_files=()
    if [ -d "$POSTED_DIR" ]; then
        for file in "$POSTED_DIR"/*.json; do
            [ -e "$file" ] || continue
            filename=$(basename "$file")
            posted_files+=("$filename")
        done
    fi
    echo "${posted_files[@]}"
}

# Generate HTML preview from JSON
generate_html_preview() {
    local json_file="$1"
    local filename=$(basename "$json_file")
    
    # Check if jq is available
    if ! command -v jq >/dev/null 2>&1; then
        echo "<p>Error: jq not installed. Install with: sudo apt install jq</p>"
        return
    fi
    
    # Extract data from JSON
    local title=$(jq -r '.title // "No Title"' "$json_file" 2>/dev/null)
    local content=$(jq -r '.content // ""' "$json_file" 2>/dev/null)
    local date=$(jq -r '.date // "No Date"' "$json_file" 2>/dev/null)
    local url=$(jq -r '.url // "#"' "$json_file" 2>/dev/null)
    local source=$(jq -r '.source // "Unknown"' "$json_file" 2>/dev/null)
    local scraped_at=$(jq -r '.scraped_at // ""' "$json_file" 2>/dev/null)
    
    # Clean HTML special characters
    title=$(echo "$title" | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g; s/"/\&quot;/g')
    content=$(echo "$content" | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g; s/"/\&quot;/g')
    
    # Format date for display
    local display_date=$(echo "$date" | sed 's/T/ /; s/\..*//')
    
    # Generate HTML preview block
    cat <<EOF
<div style="margin: 20px 0; padding: 15px; border: 1px solid #e1e8ed; border-radius: 8px; background: #fff; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
        <h3 style="margin: 0; color: #1d2129; font-size: 18px; line-height: 1.4;">${title}</h3>
        <span style="background: #4267B2; color: white; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: bold; white-space: nowrap;">${source}</span>
    </div>
    
    <div style="color: #65676b; font-size: 13px; margin-bottom: 12px; display: flex; align-items: center; gap: 15px;">
        <span style="display: flex; align-items: center; gap: 4px;">
            📅 <span style="font-weight: 500;">${display_date}</span>
        </span>
        <span style="display: flex; align-items: center; gap: 4px;">
            📄 <span style="font-family: 'Courier New', monospace; font-size: 12px;">${filename}</span>
        </span>
    </div>
    
    <div style="background: #f0f2f5; padding: 15px; border-radius: 6px; border-left: 4px solid #4267B2; margin-bottom: 12px; font-size: 14px; line-height: 1.5; color: #1c1e21;">
        $(echo "$content" | sed 's/\\n/\n/g' | while IFS= read -r line; do
            if [ -n "$line" ]; then
                echo "<p style='margin: 8px 0;'>${line}</p>"
            else
                echo "<br>"
            fi
        done)
    </div>
    
    <div style="font-size: 12px; color: #8a8d91; border-top: 1px solid #e4e6eb; padding-top: 10px; display: flex; justify-content: space-between; align-items: center;">
        <span>
            🔗 <a href="${url}" style="color: #216fdb; text-decoration: none; font-weight: 500;">View Source</a>
        </span>
        <span style="display: flex; align-items: center; gap: 4px;">
            ⏰ <span style="font-family: monospace;">${scraped_at:0:19}</span>
        </span>
    </div>
</div>
EOF
}

# Generate complete HTML email
generate_html_email() {
    local new_files_count="$1"
    local new_files_list="$2"
    local html_content="$3"
    local total_files=$(ls -1 "$READY_DIR"/*.json 2>/dev/null | wc -l)
    
    # Process file list for HTML - FIXED HERE
    local file_list_html=""
    while IFS= read -r file; do
        [ -n "$file" ] || continue
        file_list_html+="                • $file<br>"
    done <<< "$new_files_list"
    
    cat <<EOF
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Facebook Post Preview</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #1c1e21;
            background: #f5f6f8;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 700px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }
        .header {
            background: linear-gradient(135deg, #4267B2 0%, #29487d 100%);
            color: white;
            padding: 25px;
            text-align: center;
        }
        .stats-box {
            background: #f0f2f5;
            padding: 20px;
            margin: 20px;
            border-radius: 8px;
            border-left: 4px solid #42b72a;
        }
        .warning-box {
            background: #fff4e6;
            border: 1px solid #ffcc80;
            color: #e65100;
            padding: 15px;
            margin: 20px;
            border-radius: 8px;
            font-size: 14px;
        }
        .success-box {
            background: #e8f5e9;
            border: 1px solid #a5d6a7;
            color: #2e7d32;
            padding: 15px;
            margin: 20px;
            border-radius: 8px;
            font-size: 14px;
        }
        .file-list {
            background: #f8f9fa;
            padding: 15px;
            margin: 20px;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            line-height: 1.8;
        }
        .content-section {
            padding: 0 20px;
        }
        .footer {
            text-align: center;
            padding: 20px;
            color: #8a8d91;
            font-size: 12px;
            border-top: 1px solid #e4e6eb;
            background: #f0f2f5;
        }
        h1 { margin: 0; font-size: 24px; font-weight: 600; }
        h2 { margin: 25px 0 15px 0; color: #1d2129; font-size: 20px; }
        h3 { margin: 20px 0 10px 0; color: #1d2129; }
        .stat-number {
            font-size: 32px;
            font-weight: 700;
            color: #42b72a;
            margin-right: 10px;
        }
        .stat-label {
            font-size: 14px;
            color: #65676b;
        }
        code {
            background: #f1f3f4;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            color: #d93025;
        }
        a {
            color: #216fdb;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📢 Facebook Post Preview</h1>
            <p style="margin: 8px 0 0 0; opacity: 0.9; font-size: 15px;">Review new posts before they go live on Facebook</p>
        </div>
        
        <div class="stats-box">
            <div style="display: flex; align-items: center; margin-bottom: 10px;">
                <span class="stat-number">${new_files_count}</span>
                <span class="stat-label">new posts ready for publishing</span>
            </div>
            <div style="font-size: 13px; color: #65676b;">
                📊 Total in system: ${total_files} files | 📅 Generated: $(date '+%Y-%m-%d %H:%M:%S')
            </div>
        </div>
        
        <div class="warning-box">
            <strong>⚠️ IMPORTANT:</strong> This is a <strong>PREVIEW ONLY</strong>.<br>
            These posts have <strong>NOT</strong> been published to Facebook yet. Review content below before publishing.
        </div>
        
        <div class="content-section">
            <h2>📁 Files Ready for Publishing</h2>
            <div class="file-list">
${file_list_html}
            </div>
            
            <h2>📝 Post Previews</h2>
            <p style="color: #65676b; font-size: 14px; margin-bottom: 20px;">
                Below is how each post will appear on Facebook:
            </p>
            
            ${html_content}
        </div>
        
        <div class="success-box">
            <h3 style="margin-top: 0; color: #2e7d32;">✅ Next Steps</h3>
            <ol style="margin: 10px 0 0 0; padding-left: 20px;">
                <li><strong>Review</strong> all posts above for accuracy</li>
                <li><strong>Edit</strong> JSON files if changes are needed</li>
                <li><strong>Publish</strong> by running: <code>./facebook_poster.sh</code></li>
                <li><strong>Monitor</strong> results in the log files</li>
            </ol>
            <div style="margin-top: 15px; padding-top: 15px; border-top: 1px dashed #a5d6a7;">
                <strong>Quick Commands:</strong><br>
                <code style="display: inline-block; margin-top: 5px;">./preview_posts.sh</code> - Regenerate this preview<br>
                <code style="display: inline-block; margin-top: 5px;">tail -f facebook_poster.log</code> - Monitor posting process
            </div>
        </div>
        
        <div class="footer">
            <p style="margin: 0 0 8px 0;">
                <strong>Facebook Auto-Poster System</strong><br>
                Directory: $(realpath "$READY_DIR")
            </p>
            <p style="margin: 0; font-size: 11px; color: #a0a4a8;">
                This email was generated automatically. Reply to this email if you need assistance.
            </p>
        </div>
    </div>
</body>
</html>
EOF
}

# Send HTML email using mail command with proper headers
send_html_email() {
    local subject="$1"
    local html_body="$2"
    
    # Create email with proper headers for HTML
    local email_content="
From: Facebook Auto-Poster <noreply@$(hostname)>
To: $(IFS=,; echo "${EMAIL_RECIPIENTS[*]}")
Subject: $subject
MIME-Version: 1.0
Content-Type: text/html; charset=UTF-8
Content-Transfer-Encoding: quoted-printable

$html_body
"
    
    # Send to each recipient
    for recipient in "${EMAIL_RECIPIENTS[@]}"; do
        log_message "Sending HTML email to $recipient..."
        
        # Try using mail command with sendmail
        if command -v mail >/dev/null 2>&1; then
            echo "$html_body" | mail -s "$subject" -a "Content-Type: text/html; charset=UTF-8" "$recipient"
            
            if [ $? -eq 0 ]; then
                log_message "✓ HTML email sent to $recipient"
            else
                log_message "✗ Failed to send via mail command, trying sendmail..." "WARNING"
                # Try sendmail as fallback
                (
                    echo "To: $recipient"
                    echo "Subject: $subject"
                    echo "Content-Type: text/html; charset=UTF-8"
                    echo "MIME-Version: 1.0"
                    echo ""
                    echo "$html_body"
                ) | sendmail "$recipient" && log_message "✓ Email sent via sendmail" || log_message "✗ All email methods failed" "ERROR"
            fi
            
        elif command -v mutt >/dev/null 2>&1; then
            # Use mutt with HTML support
            echo "$html_body" | mutt -e "set content_type=text/html" -s "$subject" "$recipient"
            [ $? -eq 0 ] && log_message "✓ HTML email sent via mutt" || log_message "✗ mutt failed" "ERROR"
            
        else
            log_message "✗ No email client found (install mail or mutt)" "ERROR"
            return 1
        fi
    done
    
    return 0
}

# Main function
main() {
    log_message "Starting Facebook Post Preview"
    log_message "Ready directory: $(realpath "$READY_DIR")"
    
    # Check if directory exists
    if [ ! -d "$READY_DIR" ]; then
        log_message "ERROR: Ready directory not found!"
        exit 1
    fi
    
    # Get already posted files
    posted_files=$(get_posted_files)
    
    # Find new files
    new_files=()
    new_files_list=""
    html_content=""
    new_count=0
    
    log_message "Scanning for new files..."
    
    for file in "$READY_DIR"/*.json; do
        [ -e "$file" ] || continue
        
        filename=$(basename "$file")
        
        # Check if already posted
        already_posted=false
        for posted in $posted_files; do
            if [ "$posted" = "$filename" ]; then
                already_posted=true
                break
            fi
        done
        
        if ! $already_posted; then
            new_files+=("$file")
            new_files_list+="${filename}"$'\n'
            new_count=$((new_count + 1))
            
            # Generate HTML preview for this file
            log_message "  Found new: $filename"
            html_content+=$(generate_html_preview "$file")
        fi
    done
    
    log_message "Found $new_count new posts"
    
    if [ $new_count -eq 0 ]; then
        # Generate "no new posts" HTML
        html_body="<!DOCTYPE html>
        <html><body style='font-family: Arial, sans-serif; padding: 20px;'>
            <h2 style='color: #4267B2;'>📭 No New Posts Found</h2>
            <p>There are no new posts ready for Facebook publishing.</p>
            <p><strong>Last checked:</strong> $(date '+%Y-%m-%d %H:%M:%S')</p>
            <p><strong>Directory:</strong> $(realpath "$READY_DIR")</p>
            <p><strong>Total files:</strong> $(ls -1 "$READY_DIR"/*.json 2>/dev/null | wc -l)</p>
        </body></html>"
        
        subject="📭 Facebook Preview: No New Posts"
    else
        # Generate full HTML email with previews
        html_body=$(generate_html_email "$new_count" "$new_files_list" "$html_content")
        subject="📢 Facebook Preview: $new_count New Posts Ready"
    fi
    
    # Send email
    send_html_email "$subject" "$html_body"
    
    # Also save HTML to file for reference
    local preview_file="post_preview_$(date +%Y%m%d_%H%M%S).html"
    echo "$html_body" > "$preview_file"
    log_message "Preview saved to: $preview_file"
    
    # Console summary
    echo ""
    echo "╔══════════════════════════════════════════════════════╗"
    echo "║                PREVIEW COMPLETE                     ║"
    echo "╚══════════════════════════════════════════════════════╝"
    echo ""
    echo "┌──────────────────────────────────────────────────────┐"
    echo "│  Summary                                             │"
    echo "├──────────────────────────────────────────────────────┤"
    printf "│  New posts found:    %-30s │\n" "$new_count"
    printf "│  Email sent to:      %-30s │\n" "$(echo "${EMAIL_RECIPIENTS[@]}" | cut -c1-30)"
    printf "│  Preview file:       %-30s │\n" "$preview_file"
    printf "│  Ready directory:    %-30s │\n" "$(basename "$(realpath "$READY_DIR")")"
    printf "│  Posted directory:   %-30s │\n" "$(basename "$(realpath "$POSTED_DIR")")"
    echo "└──────────────────────────────────────────────────────┘"
    echo ""
    
    if [ $new_count -gt 0 ]; then
        echo "📋 Files ready for publishing:"
        echo "$new_files_list" | while IFS= read -r file; do
            [ -n "$file" ] || continue
            echo "  • $file"
        done
        echo ""
        echo "🚀 To publish these posts to Facebook, run:"
        echo "   ./facebook_poster.sh"
        echo ""
        echo "🔄 To regenerate this preview, run:"
        echo "   ./preview_posts.sh"
    fi
    
    echo ""
    echo "========================================================"
}

# Check dependencies
check_dependencies() {
    local missing=()
    
    if ! command -v jq >/dev/null 2>&1; then
        missing+=("jq - for JSON processing")
    fi
    
    if ! command -v mail >/dev/null 2>&1 && ! command -v mutt >/dev/null 2>&1; then
        missing+=("mail or mutt - for sending email")
    fi
    
    if [ ${#missing[@]} -gt 0 ]; then
        echo -e "${RED}❌ Missing dependencies:${NC}"
        for dep in "${missing[@]}"; do
            echo "   - $dep"
        done
        echo ""
        echo "📦 Install with:"
        echo "   sudo apt update && sudo apt install jq mailutils"
        echo ""
        echo -n "Continue anyway? (y/N): "
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Show help
show_help() {
    echo -e "${BLUE}Facebook Post Preview Script${NC}"
    echo "====================================="
    echo "Sends HTML email preview of new Facebook posts."
    echo ""
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  -f, --force    Force preview even if no new posts"
    echo ""
    echo "Files are considered 'new' if they don't exist in:"
    echo "  $POSTED_DIR"
    echo ""
    echo "Email will be sent to:"
    for recipient in "${EMAIL_RECIPIENTS[@]}"; do
        echo "  • $recipient"
    done
}

# Parse arguments
FORCE_PREVIEW=false
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -f|--force)
            FORCE_PREVIEW=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Display banner
echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      FACEBOOK POST PREVIEW SYSTEM              ║${NC}"
echo -e "${BLUE}║      HTML Email Preview Generator              ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# Check dependencies
check_dependencies

# Run main function
main
