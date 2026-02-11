#!/bin/bash

FOLDER="web-scraper/facebook_ready_posts"
API_KEY="$OPENAI_API_KEY"
MODEL="gpt-4o-mini"

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
            model: "gpt-4o-mini",
            messages: [
                {role: "system", content: "Rewrite news titles to be short, catchy, and accurate."},
                {role: "user", content: ("Rewrite this title using the article content:\nTitle: " + $t + "\nContent: " + $c)}
            ]
        }'
    )

    # Call the API
    rewritten=$(curl -s https://api.openai.com/v1/chat/completions \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer '"$API_KEY"'" \
        -d "$prompt" | jq -r '.choices[0].message.content')

    # Update JSON file
    jq --arg rt "$rewritten" '. + {title_rewritten: $rt}' "$file" > "$file.tmp" && mv "$file.tmp" "$file"

    echo "  → New title: $rewritten"
done

