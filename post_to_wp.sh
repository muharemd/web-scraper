#!/bin/bash
shopt -s nullglob

AUTH="bihacdanas:H4mn ykhF HOz1 EzLO 7iAJ RseZ"
BASE="https://bihacdanas.ba/wp-json/wp/v2"

TITLE="Test Post sa slikama"
CONTENT="<p>Tekst vijesti ovdje...</p>"
CATEGORY=36
FOLDER="facebook_ready_posts/attachments/usk_szz_oglasi/3818"

IMG_HTML=""
FIRST_ID=""

echo "➡ Tražim slike u: $FOLDER"
echo ""

FILES=("$FOLDER"/*.jpg "$FOLDER"/*.jpeg "$FOLDER"/*.png)

if [ ${#FILES[@]} -eq 0 ]; then
    echo "❌ Nema slika u folderu!"
    exit 1
fi

json_escape() {
    echo -n "$1" | jq -Rsa .
}

for FOTO in "${FILES[@]}"; do
    FILENAME=$(basename "$FOTO")
    EXT="${FILENAME##*.}"

    case "$EXT" in
        png)  CTYPE="image/png" ;;
        jpg|jpeg) CTYPE="image/jpeg" ;;
        *) continue ;;
    esac

    echo "Uploadujem: $FILENAME"

    RESPONSE=$(curl -s -X POST "$BASE/media" \
        -u "$AUTH" \
        -H "Content-Disposition: attachment; filename=$FILENAME" \
        -H "Content-Type: $CTYPE" \
        --data-binary "@$FOTO")

    ID=$(echo "$RESPONSE" | jq -r '.id')
    URL=$(echo "$RESPONSE" | jq -r '.source_url')

    echo "  → ID: $ID | URL: $URL"

    if [ -z "$FIRST_ID" ]; then
        FIRST_ID=$ID
    fi

    IMG_HTML="${IMG_HTML}<figure class=\"wp-block-image size-full\"><img src=\"${URL}\" /></figure>"
done

echo ""
echo "➡ Kreiram WordPress post..."

ESC_CONTENT=$(json_escape "$CONTENT $IMG_HTML")

if [ -n "$FIRST_ID" ]; then
    FEATURED="\"featured_media\": $FIRST_ID,"
else
    FEATURED=""
fi

JSON_DATA=$(cat <<EOF
{
    "title": "$TITLE",
    "content": $ESC_CONTENT,
    "status": "publish",
    "categories": [$CATEGORY],
    $FEATURED
    "comment_status": "closed"
}
EOF
)

RESULT=$(curl -s -X POST "$BASE/posts" \
    -u "$AUTH" \
    -H "Content-Type: application/json" \
    -d "$JSON_DATA")

POST_ID=$(echo "$RESULT" | jq -r '.id')
LINK=$(echo "$RESULT" | jq -r '.link')

echo ""
echo "✓ Post ID: $POST_ID"
echo "✓ URL: $LINK"
echo ""

