#!/bin/bash

FOLDER="/home/bihac-danas/web-scraper/facebook_ready_posts"
MODEL="deepseek-chat"
API_URL="https://api.deepseek.com/v1/chat/completions"

# Load API key from secure config file
CONFIG_FILE="/home/bihac-danas/web-scraper/.deepseek_config"
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
else
    echo "ERROR: Config file not found at $CONFIG_FILE"
    exit 1
fi

if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "ERROR: DEEPSEEK_API_KEY not set in config file"
    exit 1
fi

API_KEY="$DEEPSEEK_API_KEY"

for file in "$FOLDER"/*.json; do
    echo "Checking: $file"

    # Skip if already processed
    if jq -e '.title_rewritten' "$file" >/dev/null; then
        echo "  → Already processed, skipping."
        continue
    fi

    # Extract title and content
    title=$(jq -r '.title' "$file")
    content=$(jq -r '.content' "$file")

    echo "  → Rewriting title..."

    # Build prompt
    prompt=$(jq -n --arg t "$title" --arg c "$content" \
        '{
            model: "deepseek-chat",
            messages: [
                {role: "system", content: "Rewrite news titles to be short, catchy, and accurate and please offer only one possibility. All in Bosnian or Croatian language."},
                {role: "user", content: ("Rewrite this title using the article content:\nTitle: " + $t + "\nContent: " + $c)}
            ]
        }'
    )

    # Call DeepSeek API
    rewritten=$(curl -s "$API_URL" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $API_KEY" \
    -d "$prompt" | jq -r '
        .choices[0].message.content //
        .choices[0].delta.content //
        .choices[0].text //
        empty
    ')

    # Update JSON file
    jq --arg rt "$rewritten" '. + {title_rewritten: $rt}' "$file" > "$file.tmp" && mv "$file.tmp" "$file"

    echo "  → New title: $rewritten"
done

